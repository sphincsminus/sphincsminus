"""POST /api/sign-and-submit
Body: { sk, pk, recipient }

Convenience endpoint that signs server-side. Same caveat as /api/keygen:
real production should sign in the browser. This unblocks the demo flow.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import struct as _struct

sys.path.insert(0, os.path.dirname(__file__))
from _sphincs_minus import (
    SphincsParams, sphincs_sign, unpack_pubkey, unpack_privkey,
)
from sign import (
    DOMAIN, keccak256, hexstr_to_bytes,
    kv_set_nx, kv_rpush, kv_get, verify_sphincs_signature,
)


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


class handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
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

        # Lock pk_hash before signing so we can short-circuit duplicates fast.
        # Idempotency: if the SAME (pk, recipient) has already been submitted
        # (e.g. browser double-click, Vercel retry, React StrictMode), treat
        # it as success rather than 409.
        pk_hash_hex = "0x" + pk_hash.hex()
        if not kv_set_nx(f"sphx:pk:{pk_hash_hex}", rcpt_hex):
            existing = kv_get(f"sphx:pk:{pk_hash_hex}")
            if existing == rcpt_hex:
                return self._json(200, {
                    "ok": True, "pkHash": pk_hash_hex,
                    "queuePosition": -1, "note": "already in queue",
                })
            return self._json(409, {
                "ok": False,
                "error": f"pk already submitted with different recipient ({existing})",
            })

        R, ctr, fv, fa, ws, ap = sphincs_sign(
            params, sk_seed, sk_prf, pk_seed, pk_root, msg, fors_keys)
        sig_bytes = pack_signature(R, ctr, fv, fa, ws, ap)

        # Sanity-check our own work before pushing to queue.
        if not verify_sphincs_signature(pk, sig_bytes, msg):
            return self._json(500, {"ok": False, "error": "self-verify failed"})

        entry = json.dumps({"pkHash": pk_hash_hex, "recipient": rcpt_hex})
        position = kv_rpush("sphx:pending", entry)
        return self._json(200, {
            "ok": True, "pkHash": pk_hash_hex, "queuePosition": position,
        })
