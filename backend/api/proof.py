"""GET /api/proof?pkHash=0x...

Returns the full audit record for a previously-issued mint attestation:

  {
    ok: true,
    pkHash:        bytes32,
    pk:            full SPHINCS- public key (hex)
    sphincsSig:    full SPHINCS- signature (hex, ~944 bytes)
    msg:           the message that was signed (hex, 84 bytes = domain || pkHash || recipient)
    recipient:     address that received SPHINCS
    deadline:      unix timestamp
    v, r, s:       the ECDSA attestation signed by SIGNER
    mintGate:      contract address
    mintValueWei:  "2500000000000000"
    issuedAt:      unix timestamp the attestation was created
  }

Anyone can take {pk, sphincsSig, msg} and run vitalik's
`verify_test_vector.py` to confirm the SPHINCS- signature is real.
Anyone can take {v, r, s, pkHash, recipient, deadline} and run
ecrecover to confirm SIGNER signed the attestation.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))
from sign import upstash_request


def kv_get(key: str):
    res = upstash_request("POST", "/", body=["GET", key])
    return res.get("result")


class handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, s-maxage=60")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            pk_hash = (qs.get("pkHash", [""])[0] or "").lower()
            if not pk_hash.startswith("0x") or len(pk_hash) != 66:
                return self._json(400, {"ok": False, "error": "bad pkHash"})
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"bad query: {e}"})

        record = kv_get(f"sphx:proof:{pk_hash}")
        if not record:
            return self._json(404, {"ok": False, "error": "no proof for this pkHash"})

        try:
            data = json.loads(record) if isinstance(record, str) else record
        except Exception:
            return self._json(500, {"ok": False, "error": "corrupt record"})

        return self._json(200, {"ok": True, **data})
