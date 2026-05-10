"""POST /api/sign-and-attest

Body: { sk, pk, recipient, deadlineSec? }

Steps:
  1. Run SPHINCS- sign + verify (server-side, demo mode).
  2. If valid, sign an EIP-712 attestation with SIGNER_PRIVATE_KEY.
  3. Return { ok, pkHash, recipient, deadline, v, r, s, mintTo, mintValue }
     -- the frontend can hand this directly to wallet.writeContract
        on MintGateV2.mint().

This endpoint replaces the Merkle-batching flow. No on-chain post-root cron
is needed. The user broadcasts ONE transaction to mint.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import time
import struct as _struct

sys.path.insert(0, os.path.dirname(__file__))
from _sphincs_minus import (
    sphincs_sign, unpack_pubkey, unpack_privkey,
)
from sign import (
    DOMAIN, keccak256, hexstr_to_bytes,
    kv_set_nx, kv_get, upstash_request, verify_sphincs_signature,
)


def kv_set(key: str, value: str) -> None:
    upstash_request("POST", "/", body=["SET", key, value])


def pack_signature(R, ctr, fv, fa, ws, ap) -> bytes:
    out = R + ctr
    out += _struct.pack('<I', len(fv))
    for v in fv: out += _struct.pack('<I', len(v)) + v
    out += _struct.pack('<I', len(fa))
    for tree in fa:
        out += _struct.pack('<I', len(tree))
        for s in tree: out += _struct.pack('<I', len(s)) + s
    out += _struct.pack('<I', len(ws))
    for s in ws: out += _struct.pack('<I', len(s)) + s
    out += _struct.pack('<I', len(ap))
    for s in ap: out += _struct.pack('<I', len(s)) + s
    return out


# ─── EIP-712 helpers ─────────────────────────────────────────────────────────

EIP712_TYPE = "MintAttestation(bytes32 pkHash,address recipient,uint256 deadline)"
TYPEHASH = keccak256(EIP712_TYPE.encode())

def domain_separator(chain_id: int, contract: bytes) -> bytes:
    domain_type_hash = keccak256(
        b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    )
    return keccak256(
        domain_type_hash
        + keccak256(b"SphincsMinus")
        + keccak256(b"2")
        + chain_id.to_bytes(32, 'big')
        + b"\x00" * 12 + contract  # left-pad address to 32 bytes
    )


def sign_attestation(signer_pk_hex: str, contract_addr_hex: str, chain_id: int,
                     pk_hash: bytes, recipient: bytes, deadline: int):
    """Produce ECDSA (v, r, s) over the EIP-712 digest."""
    from eth_keys import keys
    sk_bytes = bytes.fromhex(signer_pk_hex.removeprefix("0x"))
    contract = bytes.fromhex(contract_addr_hex.removeprefix("0x").lower())
    assert len(contract) == 20

    struct_hash = keccak256(
        TYPEHASH
        + pk_hash
        + b"\x00" * 12 + recipient
        + deadline.to_bytes(32, 'big')
    )
    digest = keccak256(b"\x19\x01" + domain_separator(chain_id, contract) + struct_hash)
    pk = keys.PrivateKey(sk_bytes)
    sig = pk.sign_msg_hash(digest)
    return sig.v + 27, sig.r.to_bytes(32, 'big'), sig.s.to_bytes(32, 'big'), digest


CHAIN_ID = 1
GATE_ADDR = os.environ.get("MINTGATEV2_ADDRESS", "0x615771e3510a5898b38ab46da2f5b4ef67a2f077")


class handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
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
            sk = hexstr_to_bytes(data["sk"])
            pk = hexstr_to_bytes(data["pk"])
            rcpt_hex = data["recipient"].lower()
            rcpt = hexstr_to_bytes(rcpt_hex)
            assert len(rcpt) == 20
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"bad input: {e}"})

        params, pk_seed, pk_root, fors_keys = unpack_pubkey(pk)
        sk_seed, sk_prf = unpack_privkey(sk)

        pk_hash = keccak256(pk)
        msg = DOMAIN + pk_hash + rcpt
        pk_hash_hex = "0x" + pk_hash.hex()

        # Idempotency: if same (pk, recipient) seen before, return same attestation.
        # We re-sign rather than caching the raw v/r/s so we always honour the
        # current deadline window.
        existing = kv_get(f"sphx:pk:{pk_hash_hex}")
        if existing is not None and existing != rcpt_hex:
            return self._json(409, {
                "ok": False,
                "error": f"pk already attested for different recipient ({existing})",
            })

        # SPHINCS- sign + self-verify
        R, ctr, fv, fa, ws, ap = sphincs_sign(
            params, sk_seed, sk_prf, pk_seed, pk_root, msg, fors_keys)
        sig_bytes = pack_signature(R, ctr, fv, fa, ws, ap)
        if not verify_sphincs_signature(pk, sig_bytes, msg):
            return self._json(500, {"ok": False, "error": "self-verify failed"})

        # ECDSA attestation
        signer_pk = os.environ.get("SIGNER_PRIVATE_KEY")
        if not signer_pk:
            return self._json(500, {"ok": False, "error": "SIGNER_PRIVATE_KEY missing"})
        deadline = int(time.time()) + int(data.get("deadlineSec", 3600))
        v, r, s, _digest = sign_attestation(
            signer_pk, GATE_ADDR, CHAIN_ID, pk_hash, rcpt, deadline)

        # Mark seen (best-effort; not used for security, just for analytics)
        kv_set_nx(f"sphx:pk:{pk_hash_hex}", rcpt_hex)

        response = {
            "ok": True,
            "mintGate":  GATE_ADDR,
            "pkHash":    pk_hash_hex,
            "recipient": rcpt_hex,
            "deadline":  deadline,
            "v": v,
            "r": "0x" + r.hex(),
            "s": "0x" + s.hex(),
            "mintValueWei": "2500000000000000",
            "sphincsSig":   "0x" + sig_bytes.hex(),
        }

        # Persist the full (pk, sig, attestation) tuple keyed by pkHash so
        # /api/proof can look it up later for independent verification.
        proof_record = {
            **{k: v for k, v in response.items() if k != "ok"},
            "pk":         "0x" + pk.hex(),
            "msg":        "0x" + msg.hex(),
            "issuedAt":   int(time.time()),
        }
        kv_set(f"sphx:proof:{pk_hash_hex}", json.dumps(proof_record))

        return self._json(200, response)
