"""GET /api/keygen → {ok, pk, sk}

Convenience endpoint that runs SPHINCS- keygen on the server. For production
the keygen should run client-side (pyodide / wasm port) so the private key
never leaves the user's browser. This endpoint exists to bootstrap the demo
flow without shipping a wasm bundle.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _sphincs_minus import (
    sphincs_keygen, SphincsParams, pack_pubkey, pack_privkey,
)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = SphincsParams(n=16, h=4, d=2, a=3, k=3, w=16)
        # IMPORTANT: Vitalik's reference sphincs_keygen() uses HARDCODED
        # seeds when not given inputs. We MUST pass real CSPRNG seeds, or
        # every user gets the same keypair.
        sk_seed = os.urandom(params.n)
        sk_prf  = os.urandom(params.n)
        sk_s, sk_p, pk_seed, pk_root, fors_keys = sphincs_keygen(
            params, sk_seed_in=sk_seed, sk_prf_in=sk_prf)
        pk = pack_pubkey(params, pk_seed, pk_root, fors_keys)
        sk = pack_privkey(sk_s, sk_p)
        body = json.dumps({"ok": True, "pk": "0x" + pk.hex(), "sk": "0x" + sk.hex()}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
