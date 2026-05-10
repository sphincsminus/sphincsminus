"""
POST /api/sign
Body JSON:
  {
    "pk":        "0x...",   # SPHINCS- public key (hex, ~184 bytes for test params)
    "sig":       "0x...",   # SPHINCS- signature (hex, ~740 bytes)
    "recipient": "0x..."    # ETH address that will receive minted SPHINCS
  }

The signed message is:
  domain || pk_hash || recipient
where:
  domain    = keccak256("sphincs-mint:v1")     -- matches MintGate.DOMAIN_TAG
  pk_hash   = keccak256(pk)                    -- 32 bytes
  recipient = 20-byte address

If verify passes, push entry into Redis pending list `sphx:pending`.
Return: { ok: true, pkHash, queuePosition } or { ok: false, error }.
"""
from http.server import BaseHTTPRequestHandler
from typing import Optional
import json
import os
import sys
import hashlib
import urllib.request
import urllib.parse

# Allow imports of sibling _sphincs_minus.py
sys.path.insert(0, os.path.dirname(__file__))
import struct as _struct
from _sphincs_minus import sphincs_verify, unpack_pubkey


def unpack_signature(params, sig_data: bytes):
    """Unpack a binary SPHINCS- signature into the tuple format that
    sphincs_verify expects. Mirrors the unpacking inside
    sphincs_cli_verify_hex from Vitalik's reference impl."""
    pos = 0
    R = sig_data[pos:pos + params.n]
    pos += params.n
    ctr = sig_data[pos:pos + 4]
    pos += 4

    nfv = _struct.unpack('<I', sig_data[pos:pos + 4])[0]
    pos += 4
    fv = []
    for _ in range(nfv):
        l = _struct.unpack('<I', sig_data[pos:pos + 4])[0]
        pos += 4
        fv.append(sig_data[pos:pos + l])
        pos += l

    nfa = _struct.unpack('<I', sig_data[pos:pos + 4])[0]
    pos += 4
    fa = []
    for _ in range(nfa):
        na = _struct.unpack('<I', sig_data[pos:pos + 4])[0]
        pos += 4
        auth = []
        for _ in range(na):
            l = _struct.unpack('<I', sig_data[pos:pos + 4])[0]
            pos += 4
            auth.append(sig_data[pos:pos + l])
            pos += l
        fa.append(auth)

    nw = _struct.unpack('<I', sig_data[pos:pos + 4])[0]
    pos += 4
    ws = []
    for _ in range(nw):
        l = _struct.unpack('<I', sig_data[pos:pos + 4])[0]
        pos += 4
        ws.append(sig_data[pos:pos + l])
        pos += l

    na = _struct.unpack('<I', sig_data[pos:pos + 4])[0]
    pos += 4
    ap = []
    for _ in range(na):
        l = _struct.unpack('<I', sig_data[pos:pos + 4])[0]
        pos += 4
        ap.append(sig_data[pos:pos + l])
        pos += l

    return (R, ctr, fv, fa, ws, ap)


def keccak256(data: bytes) -> bytes:
    # SHA3-256 in hashlib uses NIST SHA3 padding (0x06).
    # Ethereum keccak256 uses keccak padding (0x01). They are different.
    # We need real keccak256, so use pycryptodome's keccak.
    try:
        from Crypto.Hash import keccak as _keccak
    except ImportError:
        # Fallback: pysha3 module
        import sha3
        k = sha3.keccak_256()
        k.update(data)
        return k.digest()
    k = _keccak.new(digest_bits=256)
    k.update(data)
    return k.digest()


DOMAIN = keccak256(b"sphincs-mint:v1")  # 32 bytes


def hexstr_to_bytes(s: str) -> bytes:
    s = s.strip()
    if s.startswith("0x") or s.startswith("0X"):
        s = s[2:]
    return bytes.fromhex(s)


def upstash_request(method: str, path: str, body=None) -> dict:
    base = os.environ["UPSTASH_REDIS_REST_URL"].rstrip("/")
    token = os.environ["UPSTASH_REDIS_REST_TOKEN"]
    req = urllib.request.Request(
        base + path,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(body).encode() if body is not None else None,
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def kv_set_nx(key: str, value: str) -> bool:
    """Atomic SET if not exists. Returns True if set."""
    res = upstash_request("POST", "/", body=["SET", key, value, "NX"])
    return res.get("result") == "OK"


def kv_rpush(list_key: str, item: str) -> int:
    res = upstash_request("POST", "/", body=["RPUSH", list_key, item])
    return int(res.get("result", 0))


def kv_get(key: str) -> Optional[str]:
    res = upstash_request("POST", "/", body=["GET", key])
    return res.get("result")


def verify_sphincs_signature(pk_bytes: bytes, sig_bytes: bytes, msg: bytes) -> bool:
    """Run Vitalik's SPHINCS- verify. Returns True if signature is valid."""
    try:
        params, pk_seed, pk_root, fors_keys = unpack_pubkey(pk_bytes)
        sig_tuple = unpack_signature(params, sig_bytes)
        return sphincs_verify(params, pk_seed, pk_root, msg, sig_tuple, fors_keys)
    except Exception as e:
        print(f"verify error: {e}", file=sys.stderr)
        return False


class handler(BaseHTTPRequestHandler):

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length))
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"bad json: {e}"})

        try:
            pk = hexstr_to_bytes(data["pk"])
            sig = hexstr_to_bytes(data["sig"])
            recipient_hex = data["recipient"].lower()
            if not recipient_hex.startswith("0x") or len(recipient_hex) != 42:
                return self._json(400, {"ok": False, "error": "bad recipient"})
            recipient = hexstr_to_bytes(recipient_hex)
            if len(recipient) != 20:
                return self._json(400, {"ok": False, "error": "bad recipient len"})
        except KeyError as e:
            return self._json(400, {"ok": False, "error": f"missing field {e}"})
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"bad input: {e}"})

        # Build the message that should have been signed
        pk_hash = keccak256(pk)             # 32 bytes
        msg = DOMAIN + pk_hash + recipient  # 32 + 32 + 20 = 84 bytes

        # Reject if pk_hash already in queue (or already minted, but we don't check
        # the chain here — the contract enforces single-use).
        # Idempotency: same (pk, recipient) twice = success (browser retry).
        pk_hash_hex = "0x" + pk_hash.hex()
        if not kv_set_nx(f"sphx:pk:{pk_hash_hex}", recipient_hex):
            existing = kv_get(f"sphx:pk:{pk_hash_hex}")
            if existing == recipient_hex:
                return self._json(200, {
                    "ok": True, "pkHash": pk_hash_hex,
                    "queuePosition": -1, "note": "already in queue",
                })
            return self._json(409, {
                "ok": False,
                "error": f"pk already submitted with different recipient ({existing})",
            })

        if not verify_sphincs_signature(pk, sig, msg):
            # Note: we leave the kv:pk key set, so a bad attempt cannot retry.
            # If you'd prefer to allow retries on bad sigs, DEL the key here.
            return self._json(400, {"ok": False, "error": "sphincs verify failed"})

        # Append to pending list as JSON: {pkHash, recipient}
        entry = json.dumps({"pkHash": pk_hash_hex, "recipient": recipient_hex})
        position = kv_rpush("sphx:pending", entry)

        return self._json(200, {
            "ok": True,
            "pkHash": pk_hash_hex,
            "queuePosition": position,
        })
