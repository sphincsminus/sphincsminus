"""Test: keygen, sign, verify using the backend's verify path."""
import sys, os
HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "api"))

from _sphincs_minus import (
    sphincs_keygen, sphincs_sign, SphincsParams,
    pack_pubkey, pack_privkey, unpack_pubkey,
)
from sign import (
    DOMAIN, keccak256, hexstr_to_bytes,
    verify_sphincs_signature,
)
import struct as _struct


def pack_signature(params, R, ctr, fv, fa, ws, ap) -> bytes:
    """Match unpacking format used in sphincs_cli_sign_hex."""
    out = R + ctr
    out += _struct.pack('<I', len(fv))
    for v in fv:
        out += _struct.pack('<I', len(v)) + v
    out += _struct.pack('<I', len(fa))
    for tree in fa:
        out += _struct.pack('<I', len(tree))
        for s in tree:
            out += _struct.pack('<I', len(s)) + s
    out += _struct.pack('<I', len(ws))
    for s in ws:
        out += _struct.pack('<I', len(s)) + s
    out += _struct.pack('<I', len(ap))
    for s in ap:
        out += _struct.pack('<I', len(s)) + s
    return out


def main():
    # Example recipient
    recipient = bytes.fromhex("Cf28f6e251CFC47aAd38a6D63B40444C5f3fd3F7")
    assert len(recipient) == 20

    # Generate keys
    params = SphincsParams(n=16, h=4, d=2, a=3, k=3, w=16)
    sk_seed, sk_prf, pk_seed, pk_root, fors_keys = sphincs_keygen(params)
    pk_bytes = pack_pubkey(params, pk_seed, pk_root, fors_keys)
    print(f"pk size: {len(pk_bytes)} bytes")

    # Build the message
    pk_hash = keccak256(pk_bytes)
    msg = DOMAIN + pk_hash + recipient
    assert len(msg) == 32 + 32 + 20

    # Sign
    R, ctr, fv, fa, ws, ap = sphincs_sign(
        params, sk_seed, sk_prf, pk_seed, pk_root, msg, fors_keys)
    sig_bytes = pack_signature(params, R, ctr, fv, fa, ws, ap)
    print(f"sig size: {len(sig_bytes)} bytes")

    # Verify via the backend code path
    ok = verify_sphincs_signature(pk_bytes, sig_bytes, msg)
    print("verify:", "OK" if ok else "FAIL")
    assert ok

    # Tamper test 1: modify message
    bad_msg = msg[:-1] + bytes([msg[-1] ^ 1])
    ok2 = verify_sphincs_signature(pk_bytes, sig_bytes, bad_msg)
    print("tamper msg:", "correctly rejected" if not ok2 else "WRONGLY ACCEPTED")
    assert not ok2

    # Tamper test 2: modify signature
    sig2 = bytearray(sig_bytes)
    sig2[100] ^= 1
    ok3 = verify_sphincs_signature(pk_bytes, bytes(sig2), msg)
    print("tamper sig:", "correctly rejected" if not ok3 else "WRONGLY ACCEPTED")
    assert not ok3

    print("\nAll backend verify tests PASSED")


if __name__ == "__main__":
    main()
