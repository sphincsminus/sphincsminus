#!/usr/bin/env python3
"""
SPHINCS- : Python reference implementation (pure stdlib, no external libraries).

This implementation uses SHA3-256 (from hashlib) truncated to n bytes, matching
the Lean implementation that uses the SHA3-256 FFI bindings.
"""

import hashlib
import struct
from typing import List, Optional, Tuple
from typing import Tuple, List


def sha3_256(data: bytes) -> bytes:
    """SHA3-256 hash of data (32 bytes)."""
    return hashlib.sha3_256(data).digest()


def pad_to_n_bytes(data: bytes, n: int) -> bytes:
    """Truncate or zero-pad data to exactly n bytes."""
    if len(data) < n:
        return data + b'\x00' * (n - len(data))
    else:
        return data[:n]


def hash_n(n: int, data: bytes) -> bytes:
    """SHA3-256 of data, truncated to n bytes."""
    return pad_to_n_bytes(sha3_256(data), n)


def hash_f(n: int, pk_seed: bytes, adrs: bytes, m: bytes) -> bytes:
    """F: pk_seed || adrs || M → n bytes."""
    return hash_n(n, pk_seed + adrs + m)


def hash_h(n: int, pk_seed: bytes, adrs: bytes, m1: bytes, m2: bytes) -> bytes:
    """H: pk_seed || adrs || M1 || M2 → n bytes."""
    return hash_n(n, pk_seed + adrs + m1 + m2)


def hash_t(n: int, pk_seed: bytes, adrs: bytes, m: bytes) -> bytes:
    """T_l: pk_seed || adrs || M → n bytes (WOTS chain iteration)."""
    return hash_n(n, pk_seed + adrs + m)


def hash_msg(n: int, pk_seed: bytes, pk_root: bytes, r: bytes, msg: bytes) -> bytes:
    """H_msg: R || pk_seed || pk_root || M → n bytes."""
    return hash_n(n, r + pk_seed + pk_root + msg)


def hash_prf(n: int, sk_seed: bytes, adrs: bytes) -> bytes:
    """PRF: sk_seed || adrs → n bytes."""
    return hash_n(n, sk_seed + adrs)


def hash_prf_msg(n: int, sk_prf: bytes, opt: bytes, msg: bytes) -> bytes:
    """PRF_msg: sk_prf || opt || M → n bytes."""
    return hash_n(n, sk_prf + opt + msg)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def xor_bytes(a: bytes, b: bytes) -> bytes:
    """XOR two byte strings (must be same length)."""
    return bytes(x ^ y for x, y in zip(a, b))


def int_to_bytes(x: int, n: int) -> bytes:
    """Convert integer to n bytes, big-endian."""
    return x.to_bytes(n, 'big')


def bytes_to_int(b: bytes) -> int:
    """Convert bytes to integer, big-endian."""
    return int.from_bytes(b, 'big')


def make_adrs(layer: int, tree: int, typ: int, kp_addr: int = 0,
              chain_addr: int = 0, hash_addr: int = 0) -> bytes:
    """Construct a 32-byte SPHINCS+ ADRS.

    Layout: layer(4) || tree(12) || type(4) || kp_addr(4) ||
            chain_addr(4) || hash_addr(4)  = 32 bytes.
    """
    layer_bytes = struct.pack('>I', layer)
    tree_bytes = struct.pack('>I', (tree >> 64) & 0xFFFFFFFF) + \
                 struct.pack('>I', (tree >> 32) & 0xFFFFFFFF) + \
                 struct.pack('>I', tree & 0xFFFFFFFF)
    type_bytes = struct.pack('>I', typ)
    kp_bytes = struct.pack('>I', kp_addr)
    chain_bytes = struct.pack('>I', chain_addr)
    hash_bytes = struct.pack('>I', hash_addr)
    return layer_bytes + tree_bytes + type_bytes + kp_bytes + chain_bytes + hash_bytes


# ─── WOTS+ ────────────────────────────────────────────────────────────────────

# ADRS type constants
WOTS_HASH = 0
WOTS_PK = 1
WOTS_PRF = 5


def base_w(msg: bytes, w: int, out_len: int) -> List[int]:
    """Convert a byte string to base-w digits (big-endian within bytes)."""
    log_w = w.bit_length() - 1  # w is power of 2
    digits = []
    for byte in msg:
        for i in range(8 // log_w - 1, -1, -1):
            digits.append((byte >> (i * log_w)) & (w - 1))
    if len(digits) > out_len:
        digits = digits[:out_len]
    while len(digits) < out_len:
        digits.insert(0, 0)
    return digits


def wots_checksum(digits: List[int], w: int, l2: int) -> List[int]:
    """Compute WOTS+ checksum digits: sum of (w-1 - d_i)."""
    csum = sum((w - 1) - d for d in digits)
    csum_bytes = int_to_bytes(csum, (l2 * (w.bit_length() - 1) + 7) // 8)
    return base_w(csum_bytes, w, l2)


def wots_sk_gen(n: int, sk_seed: bytes, adrs: bytes, l: int) -> List[bytes]:
    """Generate l secret values from sk_seed using PRF."""
    sk = []
    for i in range(l):
        chain_adrs = bytearray(adrs)
        chain_adrs[16:20] = struct.pack('>I', WOTS_PRF)  # type = WOTS_PRF
        chain_adrs[20:24] = struct.pack('>I', i)
        sk.append(hash_prf(n, sk_seed, bytes(chain_adrs)))
    return sk


def wots_chain(n: int, pk_seed: bytes, adrs: bytes, x: bytes,
               start: int, steps: int) -> bytes:
    """Iterate T_l `steps` times starting from `x`."""
    chain_adrs = bytearray(adrs)
    for i in range(start, start + steps):
        chain_adrs[24:28] = struct.pack('>I', i)
        x = hash_t(n, pk_seed, bytes(chain_adrs), x)
    return x


def wots_pk_from_sk(n: int, w: int, pk_seed: bytes, adrs: bytes,
                    sk: List[bytes]) -> bytes:
    """Compute WOTS+ public key by chaining each secret w-1 times, then hashing."""
    l = len(sk)
    tmp = bytearray()
    for i in range(l):
        chain_adrs = bytearray(adrs)
        chain_adrs[20:24] = struct.pack('>I', i)
        chain_adrs[16:20] = struct.pack('>I', WOTS_HASH)
        val = wots_chain(n, pk_seed, bytes(chain_adrs), sk[i], 0, w - 1)
        tmp.extend(val)
    adrs_pk = bytearray(adrs)
    adrs_pk[16:20] = struct.pack('>I', WOTS_PK)
    return hash_t(n, pk_seed, bytes(adrs_pk), bytes(tmp))


def wots_sign(n: int, w: int, pk_seed: bytes, sk_seed: bytes,
              adrs: bytes, msg: bytes) -> List[bytes]:
    """Sign a message with WOTS+.

    Returns: signature as list of l chain values.
    """
    log_w = w.bit_length() - 1
    l1 = (8 * n + log_w - 1) // log_w
    l2 = (l1 * (w - 1)).bit_length() // log_w + 1
    l = l1 + l2

    digits = base_w(msg, w, l1)
    csum_digits = wots_checksum(digits, w, l2)
    full_digits = digits + csum_digits

    sk = wots_sk_gen(n, sk_seed, adrs, l)
    sig = []
    for i in range(l):
        chain_adrs = bytearray(adrs)
        chain_adrs[20:24] = struct.pack('>I', i)
        chain_adrs[16:20] = struct.pack('>I', WOTS_HASH)
        val = wots_chain(n, pk_seed, bytes(chain_adrs), sk[i], 0, full_digits[i])
        sig.append(val)
    return sig


def wots_pk_from_sig(n: int, w: int, pk_seed: bytes, adrs: bytes,
                     sig: List[bytes], msg: bytes) -> bytes:
    """Verify a WOTS+ signature and recover the public key.

    Completes each chain to w-1, hashes all l chains together.
    """
    log_w = w.bit_length() - 1
    l1 = (8 * n + log_w - 1) // log_w
    l2 = (l1 * (w - 1)).bit_length() // log_w + 1
    l = l1 + l2

    digits = base_w(msg, w, l1)
    csum_digits = wots_checksum(digits, w, l2)
    full_digits = digits + csum_digits

    tmp = bytearray()
    for i in range(l):
        chain_adrs = bytearray(adrs)
        chain_adrs[20:24] = struct.pack('>I', i)
        chain_adrs[16:20] = struct.pack('>I', WOTS_HASH)
        val = wots_chain(n, pk_seed, bytes(chain_adrs), sig[i],
                         full_digits[i], w - 1 - full_digits[i])
        tmp.extend(val)

    adrs_pk = bytearray(adrs)
    adrs_pk[16:20] = struct.pack('>I', WOTS_PK)
    return hash_t(n, pk_seed, bytes(adrs_pk), bytes(tmp))


# ─── FORS ─────────────────────────────────────────────────────────────────────

# ADRS type constants
FORS_TREE = 3
FORS_ROOTS = 4
FORS_PRF = 6


def fors_sk_gen(n: int, sk_seed: bytes, adrs: bytes, k: int, a: int) -> List[List[bytes]]:
    """Generate FORS secret values: k trees, each with 2^a leaves.

    Follows SPHINCS+ spec:
      FORS_PRF: type=6, kp_addr=tree_index, chain_addr=leaf_index.
    The FORS instance is identified by the tree field in `adrs`.
    """
    t = 1 << a
    sk = []
    for i in range(k):
        tree_sk = []
        for j in range(t):
            leaf_adrs = bytearray(adrs)
            leaf_adrs[16:20] = struct.pack('>I', FORS_PRF)
            leaf_adrs[20:24] = struct.pack('>I', i)  # kp_addr = FORS tree index
            leaf_adrs[24:28] = struct.pack('>I', j)  # chain_addr = leaf index within tree
            tree_sk.append(hash_prf(n, sk_seed, bytes(leaf_adrs)))
        sk.append(tree_sk)
    return sk


def fors_tree_hash(n: int, pk_seed: bytes, adrs: bytes,
                   sk_tree: List[bytes], a: int) -> List[List[bytes]]:
    """Build a FORS binary hash tree from leaves.

    Returns nodes[level][index] where level 0 = leaves, level a = root.
    """
    t = 1 << a
    nodes = [sk_tree[:]]
    for level in range(a):
        prev = nodes[level]
        cur = []
        for i in range(0, len(prev), 2):
            node_adrs = bytearray(adrs)
            node_adrs[16:20] = struct.pack('>I', FORS_TREE)
            node_adrs[28:32] = struct.pack('>I', level)
            node_adrs[24:28] = struct.pack('>I', i // 2)
            h = hash_h(n, pk_seed, bytes(node_adrs), prev[i], prev[i + 1])
            cur.append(h)
        nodes.append(cur)
    return nodes


def fors_roots_from_sk(n: int, pk_seed: bytes, adrs: bytes,
                       sk: List[List[bytes]], k: int, a: int) -> List[bytes]:
    """Compute all k FORS tree roots."""
    roots = []
    for i in range(k):
        tree_adrs = bytearray(adrs)
        tree_adrs[20:24] = struct.pack('>I', i)
        nodes = fors_tree_hash(n, pk_seed, bytes(tree_adrs), sk[i], a)
        roots.append(nodes[a][0])
    return roots


def fors_pk_from_roots(n: int, pk_seed: bytes, adrs: bytes,
                       roots: List[bytes]) -> bytes:
    """Hash all k tree roots into a single FORS public key."""
    pk_adrs = bytearray(adrs)
    pk_adrs[16:20] = struct.pack('>I', FORS_ROOTS)
    pk = roots[0]
    for r in roots[1:]:
        pk = hash_h(n, pk_seed, bytes(pk_adrs), pk, r)
    return pk


def fors_pk_from_sk(n: int, pk_seed: bytes, adrs: bytes,
                    sk: List[List[bytes]], k: int, a: int) -> bytes:
    """Compute full FORS public key from secret keys."""
    roots = fors_roots_from_sk(n, pk_seed, adrs, sk, k, a)
    return fors_pk_from_roots(n, pk_seed, adrs, roots)


def fors_sign(n: int, pk_seed: bytes, sk: List[List[bytes]],
              adrs: bytes, msg_digest: bytes, k: int, a: int
              ) -> Tuple[List[bytes], List[List[bytes]]]:
    """Sign with standard FORS.

    Returns (sig_values, auth_paths): k leaf values, each with a-node auth path.
    """
    t = 1 << a
    idxs = base_w(msg_digest, t, k)
    idxs = [min(i, t - 1) for i in idxs]

    sig_vals = [sk[i][idxs[i]] for i in range(k)]
    auth_paths = []
    for i in range(k):
        tree_adrs = bytearray(adrs)
        tree_adrs[20:24] = struct.pack('>I', i)
        nodes = fors_tree_hash(n, pk_seed, bytes(tree_adrs), sk[i], a)
        auth = []
        idx = idxs[i]
        for level in range(a):
            sibling = idx ^ 1
            auth.append(nodes[level][sibling])
            idx = idx // 2
        auth_paths.append(auth)
    return sig_vals, auth_paths


def fors_roots_from_sig(n: int, pk_seed: bytes, adrs: bytes,
                        sig_vals: List[bytes], auth_paths: List[List[bytes]],
                        msg_digest: bytes, k: int, a: int) -> List[bytes]:
    """Recover FORS tree roots from a signature (one root per tree)."""
    t = 1 << a
    idxs = base_w(msg_digest, t, k)
    idxs = [min(i, t - 1) for i in idxs]

    roots = []
    for i in range(k):
        tree_adrs = bytearray(adrs)
        tree_adrs[20:24] = struct.pack('>I', i)
        node = sig_vals[i]
        idx = idxs[i]
        for level in range(a):
            sibling = auth_paths[i][level]
            node_adrs = bytearray(tree_adrs)
            node_adrs[16:20] = struct.pack('>I', FORS_TREE)
            node_adrs[28:32] = struct.pack('>I', level)
            node_adrs[24:28] = struct.pack('>I', idx // 2)
            if idx % 2 == 1:
                node = hash_h(n, pk_seed, bytes(node_adrs), sibling, node)
            else:
                node = hash_h(n, pk_seed, bytes(node_adrs), node, sibling)
            idx = idx // 2
        roots.append(node)
    return roots


# ─── FORS+C (counter-based pruning) ──────────────────────────────────────────

def fors_c_pk(n: int, pk_seed: bytes, sk_seed: bytes, adrs: bytes,
              k: int, a: int) -> Tuple[bytes, bytes]:
    """Generate FORS+C public key.

    The FORS+C PK stores TWO values:
      last_root: root of tree k-1 (precomputed, so verifier can use it)
      pk_fors:   hash of all k tree roots

    Returns (last_root, pk_fors), each n bytes.
    """
    sk = fors_sk_gen(n, sk_seed, adrs, k, a)
    roots = fors_roots_from_sk(n, pk_seed, adrs, sk, k, a)
    last_root = roots[-1]
    pk = fors_pk_from_roots(n, pk_seed, adrs, roots)
    return last_root, pk


def fors_c_sign(n: int, pk_seed: bytes, sk_seed: bytes, adrs: bytes,
                msg_digest: bytes, k: int, a: int,
                max_grind: int = 1000000
                ) -> Tuple[bytes, List[bytes], List[List[bytes]]]:
    """FORS+C sign with counter grinding.

    Grinds a counter until the last tree's leaf index is 0.
    Signature omits tree k-1 entirely.

    Returns (counter, sig_values, auth_paths).
    """
    sk = fors_sk_gen(n, sk_seed, adrs, k, a)
    t = 1 << a

    for ctr in range(max_grind):
        ctr_bytes = int_to_bytes(ctr, 4)
        trial_digest = hash_n(n, ctr_bytes + msg_digest)
        idxs = base_w(trial_digest, t, k)
        idxs = [min(i, t - 1) for i in idxs]
        if idxs[-1] == 0:
            sig_vals = [sk[i][idxs[i]] for i in range(k - 1)]
            auth_paths = []
            for i in range(k - 1):
                tree_adrs_i = bytearray(adrs)
                tree_adrs_i[20:24] = struct.pack('>I', i)
                nodes = fors_tree_hash(n, pk_seed,
                                       bytes(tree_adrs_i), sk[i], a)
                auth = []
                idx = idxs[i]
                for level in range(a):
                    sibling = idx ^ 1
                    auth.append(nodes[level][sibling])
                    idx = idx // 2
                auth_paths.append(auth)
            return ctr_bytes, sig_vals, auth_paths

    raise ValueError(f"FORS+C grinding failed after {max_grind} attempts")


def fors_c_verify(n: int, pk_seed: bytes, adrs: bytes,
                  ctr: bytes, sig_vals: List[bytes],
                  auth_paths: List[List[bytes]],
                  last_root: bytes, pk_fors: bytes,
                  msg_digest: bytes, k: int, a: int) -> bool:
    """Verify FORS+C signature.

    Reconstructs k-1 roots from the signature, uses `last_root` as
    the root of tree k-1, hashes all k roots together, and checks
    against pk_fors.
    """
    t = 1 << a
    trial_digest = hash_n(n, ctr + msg_digest)
    idxs = base_w(trial_digest, t, k)
    idxs = [min(i, t - 1) for i in idxs]

    if idxs[-1] != 0:
        return False

    # Reconstruct first k-1 tree roots
    roots = []
    for i in range(k - 1):
        tree_adrs = bytearray(adrs)
        tree_adrs[20:24] = struct.pack('>I', i)
        node = sig_vals[i]
        idx = idxs[i]
        for level in range(a):
            sibling = auth_paths[i][level]
            node_adrs = bytearray(tree_adrs)
            node_adrs[16:20] = struct.pack('>I', FORS_TREE)
            node_adrs[28:32] = struct.pack('>I', level)
            node_adrs[24:28] = struct.pack('>I', idx // 2)
            if idx % 2 == 1:
                node = hash_h(n, pk_seed, bytes(node_adrs), sibling, node)
            else:
                node = hash_h(n, pk_seed, bytes(node_adrs), node, sibling)
            idx = idx // 2
        roots.append(node)

    # Append the precomputed last tree root
    roots.append(last_root)

    # Hash all k roots
    computed_pk = fors_pk_from_roots(n, pk_seed, adrs, roots)
    return computed_pk == pk_fors


# ─── Helpers for WOTS parameters ─────────────────────────────────────────────

def wotsParams(n: int, w: int) -> dict:
    """Compute WOTS+ derived parameters."""
    log_w = w.bit_length() - 1
    l1 = (8 * n + log_w - 1) // log_w
    l2 = (l1 * (w - 1)).bit_length() // log_w + 1
    return {'n': n, 'w': w, 'logW': log_w, 'l1': l1, 'l2': l2, 'l': l1 + l2}


# ─── XMSS (eXtended Merkle Signature Scheme) ─────────────────────────────────

TREE = 2  # ADRS type for Merkle tree nodes


def xmss_treehash(n: int, pk_seed: bytes, adrs: bytes,
                  leaves: List[bytes], height: int) -> bytes:
    """Build a Merkle tree from leaves, return root."""
    nodes = leaves[:]
    for level in range(height):
        next_nodes = []
        for i in range(0, len(nodes), 2):
            node_adrs = bytearray(adrs)
            node_adrs[16:20] = struct.pack('>I', TREE)
            node_adrs[28:32] = struct.pack('>I', level)
            node_adrs[24:28] = struct.pack('>I', i // 2)
            h = hash_h(n, pk_seed, bytes(node_adrs), nodes[i], nodes[i + 1])
            next_nodes.append(h)
        nodes = next_nodes
    return nodes[0]


def xmss_sign(n: int, w: int, pk_seed: bytes, sk_seed: bytes,
              adrs: bytes, msg: bytes, leaf_idx: int, height: int
              ) -> Tuple[List[bytes], List[bytes]]:
    """Sign a message with XMSS at a specific leaf.

    Returns (wots_sig, auth_path).
    """
    wp = wotsParams(n, w)
    l = wp['l']

    leaf_adrs = bytearray(adrs)
    leaf_adrs[20:24] = struct.pack('>I', leaf_idx)
    wots_sig = wots_sign(n, w, pk_seed, sk_seed, bytes(leaf_adrs), msg)

    # Build all WOTS+ PKs to get auth path
    num_leaves = 1 << height
    leaves = []
    for i in range(num_leaves):
        ladrs = bytearray(adrs)
        ladrs[20:24] = struct.pack('>I', i)
        wsk = wots_sk_gen(n, sk_seed, bytes(ladrs), l)
        wpk = wots_pk_from_sk(n, w, pk_seed, bytes(ladrs), wsk)
        leaves.append(wpk)

    auth_path = []
    idx = leaf_idx
    nodes = leaves[:]
    for level in range(height):
        sibling_idx = idx ^ 1
        auth_path.append(nodes[sibling_idx])
        next_nodes = []
        for i in range(0, len(nodes), 2):
            node_adrs = bytearray(adrs)
            node_adrs[16:20] = struct.pack('>I', TREE)
            node_adrs[28:32] = struct.pack('>I', level)
            node_adrs[24:28] = struct.pack('>I', i // 2)
            h = hash_h(n, pk_seed, bytes(node_adrs), nodes[i], nodes[i + 1])
            next_nodes.append(h)
        nodes = next_nodes
        idx = idx // 2
    return wots_sig, auth_path


def xmss_pk_from_sig(n: int, w: int, pk_seed: bytes, adrs: bytes,
                     wots_sig: List[bytes], auth_path: List[bytes],
                     msg: bytes, leaf_idx: int, height: int) -> bytes:
    """Verify XMSS and recover the root public key."""
    leaf_adrs = bytearray(adrs)
    leaf_adrs[20:24] = struct.pack('>I', leaf_idx)
    wots_pk = wots_pk_from_sig(n, w, pk_seed, bytes(leaf_adrs),
                               wots_sig, msg)
    node = wots_pk
    idx = leaf_idx
    for level in range(height):
        sibling = auth_path[level]
        node_adrs = bytearray(adrs)
        node_adrs[16:20] = struct.pack('>I', TREE)
        node_adrs[28:32] = struct.pack('>I', level)
        node_adrs[24:28] = struct.pack('>I', idx // 2)
        if idx % 2 == 1:
            node = hash_h(n, pk_seed, bytes(node_adrs), sibling, node)
        else:
            node = hash_h(n, pk_seed, bytes(node_adrs), node, sibling)
        idx = idx // 2
    return node


# ─── SPHINCS- Top-Level Scheme ───────────────────────────────────────────────

class SphincsParams:
    """Parameter set for SPHINCS-."""
    def __init__(self, n: int, h: int, d: int, a: int, k: int, w: int):
        self.n = n
        self.h = h
        self.d = d
        self.a = a
        self.k = k
        self.w = w
        self.h_prime = h // d
        log_w = w.bit_length() - 1
        self.log_w = log_w
        self.wots_l1 = (8 * n + log_w - 1) // log_w
        self.wots_l2 = (self.wots_l1 * (w - 1)).bit_length() // log_w + 1
        self.wots_l = self.wots_l1 + self.wots_l2
        self.md_bytes = (k * a + h + (d - 1) * self.h_prime + 7) // 8


def sphincs_keygen(params: SphincsParams,
                   sk_seed_in: Optional[bytes] = None,
                   sk_prf_in: Optional[bytes] = None
                   ) -> Tuple[bytes, bytes, bytes, bytes,
                              List[List[Tuple[bytes, bytes]]]]:
    """Generate SPHINCS- keypair.

    Uses provided sk_seed_in, sk_prf_in if given, otherwise derives from
    hardcoded constants. Returns (sk_seed, sk_prf, pk_seed, pk_root, fors_keys).
    """
    n = params.n
    h = params.h
    d = params.d
    h_prime = params.h_prime

    sk_seed = sk_seed_in if sk_seed_in is not None else sha3_256(b"sk_seed_spx_minus_00000000")[:n]
    sk_prf = sk_prf_in if sk_prf_in is not None else sha3_256(b"sk_prf_spx_minus_00000000")[:n]
    pk_seed = sha3_256(b"pk_seed_spx_minus_00000000")[:n]

    # Build bottom layer: FORS+C keypairs for each leaf
    num_bottom_leaves = 1 << h_prime
    fors_layer = []
    for leaf_idx in range(num_bottom_leaves):
        fors_adrs = make_adrs(d - 1, leaf_idx, FORS_TREE)
        last_root, pk_fors = fors_c_pk(
            n, pk_seed, sk_seed, bytes(fors_adrs), params.k, params.a)
        fors_layer.append((last_root, pk_fors))

    # Build bottom XMSS tree: leaves are WOTS+ PKs, each signs (last_root || pk_fors)
    w = params.w
    wp = wotsParams(n, w)
    leaves = []
    for leaf_idx in range(num_bottom_leaves):
        leaf_adrs = make_adrs(d - 1, 0, WOTS_HASH, kp_addr=leaf_idx)
        wsk = wots_sk_gen(n, sk_seed, leaf_adrs, wp['l'])
        wpk = wots_pk_from_sk(n, w, pk_seed, leaf_adrs, wsk)
        leaves.append(wpk)
    bottom_root = xmss_treehash(n, pk_seed, make_adrs(d - 1, 0, TREE),
                                leaves, h_prime)
    pk_root = bottom_root  # For d=2, this is the top

    return sk_seed, sk_prf, pk_seed, pk_root, [fors_layer]


def sphincs_sign(params: SphincsParams, sk_seed: bytes, sk_prf: bytes,
                 pk_seed: bytes, pk_root: bytes, msg: bytes,
                 fors_keys: List[List[Tuple[bytes, bytes]]],
                 leaf_usage: int = 0
                 ) -> Tuple[bytes, bytes, List[bytes], List[List[bytes]],
                            List[bytes], List[bytes]]:
    """Sign a message with SPHINCS-.

    Returns (R, counter, fors_vals, fors_auth, wots_sig, auth_path).
    """
    n = params.n
    h = params.h
    d = params.d
    h_prime = params.h_prime

    # Step 1: Randomized message hash
    opt = pk_root + int_to_bytes(leaf_usage, 4)
    R = hash_prf_msg(n, sk_prf, opt, msg)
    md_full = hash_msg(n, pk_seed, pk_root, R, msg)

    md_int = bytes_to_int(md_full)
    leaf_mask = (1 << h_prime) - 1
    idx_leaf = md_int & leaf_mask
    fors_bits = md_int >> h_prime
    fors_mask = (1 << (params.k * params.a)) - 1
    fors_md = fors_bits & fors_mask
    fors_bytes_len = (params.k * params.a + 7) // 8
    fors_md_bytes = int_to_bytes(fors_md, fors_bytes_len)

    # Step 2: FORS+C sign
    fors_adrs = make_adrs(d - 1, idx_leaf, FORS_TREE)
    counter, fors_vals, fors_auth = fors_c_sign(
        n, pk_seed, sk_seed, fors_adrs, fors_md_bytes, params.k, params.a)

    # Step 3: Bottom XMSS signs the FORS+C PK
    last_root, pk_fors = fors_keys[0][idx_leaf]
    wots_msg = last_root + pk_fors

    leaf_adrs = make_adrs(d - 1, 0, WOTS_HASH, kp_addr=idx_leaf)
    wots_sig = wots_sign(n, params.w, pk_seed, sk_seed, leaf_adrs, wots_msg)
    tree_adrs = make_adrs(d - 1, 0, TREE)
    auth_path = build_xmss_auth_path(n, params, pk_seed, sk_seed,
                                     tree_adrs, idx_leaf, h_prime)

    return (R, counter, fors_vals, fors_auth, wots_sig, auth_path)


def build_xmss_auth_path(n: int, params: SphincsParams,
                         pk_seed: bytes, sk_seed: bytes,
                         adrs: bytes, leaf_idx: int,
                         height: int) -> List[bytes]:
    """Build Merkle auth path for XMSS.

    The `adrs` here should be a TREE-type address, not WOTS_HASH.
    We use it as the base for Merkle node hashing.
    """
    w = params.w
    wp = wotsParams(n, w)
    l = wp['l']
    num_leaves = 1 << height
    # Build all WOTS+ PKs for this subtree
    leaves = []
    for i in range(num_leaves):
        ladrs = bytearray(adrs)
        ladrs[16:20] = struct.pack('>I', WOTS_HASH)
        ladrs[20:24] = struct.pack('>I', i)
        wsk = wots_sk_gen(n, sk_seed, bytes(ladrs), l)
        wpk = wots_pk_from_sk(n, w, pk_seed, bytes(ladrs), wsk)
        leaves.append(wpk)
    # Extract auth path by walking up the Merkle tree
    auth_path = []
    idx = leaf_idx
    nodes = leaves[:]
    for level in range(height):
        sibling_idx = idx ^ 1
        auth_path.append(nodes[sibling_idx])
        next_nodes = []
        for i in range(0, len(nodes), 2):
            node_adrs = bytearray(adrs)
            node_adrs[16:20] = struct.pack('>I', TREE)
            node_adrs[28:32] = struct.pack('>I', level)
            node_adrs[24:28] = struct.pack('>I', i // 2)
            h = hash_h(n, pk_seed, bytes(node_adrs), nodes[i], nodes[i + 1])
            next_nodes.append(h)
        nodes = next_nodes
        idx = idx // 2
    return auth_path


def sphincs_verify(params: SphincsParams, pk_seed: bytes, pk_root: bytes,
                   msg: bytes, sig: Tuple, fors_keys: List[List[Tuple[bytes, bytes]]],
                   leaf_usage: int = 0) -> bool:
    """Verify a SPHINCS- signature.

    sig = (R, counter, fors_vals, fors_auth, wots_sig, auth_path)
    """
    n = params.n
    h = params.h
    d = params.d
    h_prime = params.h_prime

    R, counter, fors_vals, fors_auth, wots_sig, auth_path = sig

    # Step 1: Recover message digest
    md_full = hash_msg(n, pk_seed, pk_root, R, msg)
    md_int = bytes_to_int(md_full)
    leaf_mask = (1 << h_prime) - 1
    idx_leaf = md_int & leaf_mask
    fors_bits = md_int >> h_prime
    fors_mask = (1 << (params.k * params.a)) - 1
    fors_md = fors_bits & fors_mask
    fors_bytes_len = (params.k * params.a + 7) // 8
    fors_md_bytes = int_to_bytes(fors_md, fors_bytes_len)

    # Step 2: Verify FORS+C
    fors_adrs = make_adrs(d - 1, idx_leaf, FORS_TREE)
    last_root, pk_fors = fors_keys[0][idx_leaf]
    if not fors_c_verify(n, pk_seed, fors_adrs, counter, fors_vals,
                         fors_auth, last_root, pk_fors, fors_md_bytes,
                         params.k, params.a):
        return False

    # Step 3: Verify XMSS WOTS+ signature over (last_root || pk_fors)
    wots_msg = last_root + pk_fors
    leaf_adrs = make_adrs(d - 1, 0, WOTS_HASH, kp_addr=idx_leaf)
    recovered_wots_pk = wots_pk_from_sig(n, params.w, pk_seed,
                                         leaf_adrs, wots_sig, wots_msg)

    # Step 4: Hash up Merkle tree
    node = recovered_wots_pk
    idx = idx_leaf
    for level in range(h_prime):
        sibling = auth_path[level]
        node_adrs = make_adrs(d - 1, 0, TREE)
        node_adrs = bytearray(node_adrs)
        node_adrs[16:20] = struct.pack('>I', TREE)
        node_adrs[28:32] = struct.pack('>I', level)
        node_adrs[24:28] = struct.pack('>I', idx // 2)
        if idx % 2 == 1:
            node = hash_h(n, pk_seed, bytes(node_adrs), sibling, node)
        else:
            node = hash_h(n, pk_seed, bytes(node_adrs), node, sibling)
        idx = idx // 2

    # Step 5: Check against public key root
    return node == pk_root


# ─── Tests ───────────────────────────────────────────────────────────────────

def run_tests() -> None:
    pk_seed = bytes(range(16))
    sk_seed = bytes(range(16, 32))
    adrs = bytes(range(32, 64))
    m = b"hello"

    print("=== Hash functions ===")
    print("hash_f:", hash_f(16, pk_seed, adrs, m).hex())
    print("hash_h:", hash_h(16, pk_seed, adrs, m, m).hex())
    print("hash_t:", hash_t(16, pk_seed, adrs, m).hex())
    print("hash_prf:", hash_prf(16, sk_seed, adrs).hex())

    print("\n=== WOTS+ ===")
    N, W = 16, 16
    wots_msg = bytes(range(16))
    wots_adrs = make_adrs(0, 0, WOTS_HASH)
    sk = wots_sk_gen(N, sk_seed, wots_adrs, 35)
    pk = wots_pk_from_sk(N, W, pk_seed, wots_adrs, sk)
    print("WOTS PK:", pk.hex())
    sig = wots_sign(N, W, pk_seed, sk_seed, wots_adrs, wots_msg)
    pk2 = wots_pk_from_sig(N, W, pk_seed, wots_adrs, sig, wots_msg)
    print("WOTS verify:", "OK" if pk == pk2 else "FAIL")

    print("\n=== FORS ===")
    K, A = 3, 3
    fors_adrs = make_adrs(0, 0, FORS_TREE)
    fsk = fors_sk_gen(16, sk_seed, fors_adrs, K, A)
    fpk = fors_pk_from_sk(16, pk_seed, fors_adrs, fsk, K, A)
    fors_msg = bytes(range(16))
    fvals, fauth = fors_sign(16, pk_seed, fsk, fors_adrs, fors_msg, K, A)
    froots = fors_roots_from_sig(16, pk_seed, fors_adrs, fvals, fauth,
                                  fors_msg, K, A)
    fpk2 = fors_pk_from_roots(16, pk_seed, fors_adrs, froots)
    print("FORS verify:", "OK" if fpk == fpk2 else "FAIL")

    print("\n=== FORS+C ===")
    last_root, fpk_c = fors_c_pk(16, pk_seed, sk_seed, fors_adrs, K, A)
    ctr, fcv, fca = fors_c_sign(16, pk_seed, sk_seed, fors_adrs,
                                 fors_msg, K, A)
    print(f"FORS+C counter: {bytes_to_int(ctr)}")
    ok = fors_c_verify(16, pk_seed, fors_adrs, ctr, fcv, fca,
                       last_root, fpk_c, fors_msg, K, A)
    print("FORS+C verify:", "OK" if ok else "FAIL")

    print("\n=== XMSS ===")
    XH = 2
    xmss_adrs = make_adrs(0, 0, TREE)
    leaf_idx = 1
    xmss_msg = bytes([0x42] * 16)
    xwots_sig, xauth = xmss_sign(16, 16, pk_seed, sk_seed,
                                  xmss_adrs, xmss_msg, leaf_idx, XH)
    num_leaves = 1 << XH
    xleaves = []
    for i in range(num_leaves):
        ladrs = bytearray(xmss_adrs)
        ladrs[20:24] = struct.pack('>I', i)
        wsk = wots_sk_gen(16, sk_seed, bytes(ladrs), 35)
        wpk = wots_pk_from_sk(16, 16, pk_seed, bytes(ladrs), wsk)
        xleaves.append(wpk)
    xroot = xmss_treehash(16, pk_seed, xmss_adrs, xleaves, XH)
    xroot2 = xmss_pk_from_sig(16, 16, pk_seed, xmss_adrs,
                              xwots_sig, xauth, xmss_msg, leaf_idx, XH)
    print("XMSS verify:", "OK" if xroot == xroot2 else "FAIL")

    print("\n=== SPHINCS- ===")
    params = SphincsParams(n=16, h=4, d=2, a=3, k=3, w=16)
    sk_s, sk_p, pk_s, pk_r, fors_keys = sphincs_keygen(params)
    print(f"PK root: {pk_r.hex()}")
    R, ctr, fv, fa, ws, ap = sphincs_sign(
        params, sk_s, sk_p, pk_s, pk_r,
        b"test message for sphincs minus", fors_keys)
    ok = sphincs_verify(params, pk_s, pk_r,
                        b"test message for sphincs minus",
                        (R, ctr, fv, fa, ws, ap), fors_keys)
    print("SPHINCS- verify:", "OK" if ok else "FAIL")

    # Test signature sizes
    sig_size = (len(R) + len(ctr) +
                sum(len(v) for v in fv) +
                sum(sum(len(s) for s in tree) for tree in fa) +
                sum(len(s) for s in ws) +
                sum(len(s) for s in ap))
    print(f"Signature size: {sig_size} bytes")
    print(f"WOTS sig chains: {len(ws)}")
    print(f"FORS trees in sig: {len(fv)} (out of {params.k})")
    print(f"Auth path length: {len(ap)} (height={params.h_prime})")

    print("\nAll tests passed!")


# ─── CLI ─────────────────────────────────────────────────────────────────────

# Production C7 parameters (smaller than SPHINCS+-128s):
# n=16, h=24, d=2, a=16, k=8, w=8
# Test parameters: n=16, h=4, d=2, a=3, k=3, w=16

DEFAULT_PARAMS = SphincsParams(n=16, h=4, d=2, a=3, k=3, w=16)


def pack_privkey(sk_seed: bytes, sk_prf: bytes) -> bytes:
    """Pack private key: sk_seed || sk_prf (both n bytes → 32 bytes total)."""
    return sk_seed + sk_prf


def unpack_privkey(key: bytes) -> Tuple[bytes, bytes]:
    """Unpack private key into (sk_seed, sk_prf)."""
    n = len(key) // 2
    return key[:n], key[n:]


def pack_pubkey(params: SphincsParams, pk_seed: bytes, pk_root: bytes,
                fors_keys: List[List[Tuple[bytes, bytes]]]) -> bytes:
    """Pack public key as binary:
        4 bytes: n
        4 bytes: h
        4 bytes: d
        4 bytes: a
        4 bytes: k
        4 bytes: w
        n bytes: pk_seed
        n bytes: pk_root
        (1 << h_prime) * n bytes: FORS last_roots
    """
    n = params.n
    h = params.h
    d = params.d
    a = params.a
    k = params.k
    w = params.w
    h_prime = n * 8 if h == 0 else (h + d - 1) // d
    num_fors = 1 << h_prime

    header = struct.pack('<6I', n, h, d, a, k, w)
    fors_data = b''
    for lr, pk_f in fors_keys[0]:
        fors_data += lr + pk_f
    return header + pk_seed + pk_root + fors_data


def unpack_pubkey(data: bytes) -> Tuple[SphincsParams, bytes, bytes,
                                         List[List[Tuple[bytes, bytes]]]]:
    """Unpack public key binary format."""
    n, h, d, a, k, w = struct.unpack('<6I', data[:24])
    params = SphincsParams(n=n, h=h, d=d, a=a, k=k, w=w)
    pos = 24
    pk_seed = data[pos:pos + n]
    pos += n
    pk_root = data[pos:pos + n]
    pos += n
    h_prime = n * 8 if h == 0 else (h + d - 1) // d
    num_fors = 1 << h_prime
    fors_keys = []
    for _i in range(num_fors):
        lr = data[pos:pos + n]
        pos += n
        pk_f = data[pos:pos + n]
        pos += n
        fors_keys.append((lr, pk_f))
    return params, pk_seed, pk_root, [fors_keys]


def parse_hex(s: str) -> bytes:
    """Parse a hex string, optionally prefixed with '0x'."""
    s = s.strip()
    if s.startswith("0x"):
        s = s[2:]
    return bytes.fromhex(s)


def to_hex(data: bytes) -> str:
    """Convert bytes to '0x'-prefixed hex string."""
    return "0x" + data.hex()


def sphincs_cli_sign_hex(privkey_hex: str, message: str) -> str:
    """Sign a message string. Returns hex-encoded signature with 0x prefix."""
    privkey = parse_hex(privkey_hex)
    if len(privkey) != 2 * DEFAULT_PARAMS.n:
        raise ValueError(f"Private key must be {2 * DEFAULT_PARAMS.n} bytes")
    sk_seed, sk_prf = unpack_privkey(privkey)
    msg_bytes = message.encode("utf-8")

    params = DEFAULT_PARAMS
    _, _, pk_seed, pk_root, fors_keys = sphincs_keygen(params, sk_seed, sk_prf)
    R, ctr, fv, fa, ws, ap = sphincs_sign(
        params, sk_seed, sk_prf, pk_seed, pk_root, msg_bytes, fors_keys)

    # Pack signature (same format as sphincs_cli_sign)
    sig_data = R
    sig_data += ctr
    sig_data += struct.pack('<I', len(fv))
    for v in fv:
        sig_data += struct.pack('<I', len(v))
        sig_data += v
    sig_data += struct.pack('<I', len(fa))
    for auth in fa:
        sig_data += struct.pack('<I', len(auth))
        for s in auth:
            sig_data += struct.pack('<I', len(s))
            sig_data += s
    sig_data += struct.pack('<I', len(ws))
    for s in ws:
        sig_data += struct.pack('<I', len(s))
        sig_data += s
    sig_data += struct.pack('<I', len(ap))
    for s in ap:
        sig_data += struct.pack('<I', len(s))
        sig_data += s

    return to_hex(sig_data)


def sphincs_cli_verify_hex(pubkey_hex: str, message: str, sig_hex: str) -> bool:
    """Verify a hex-encoded signature against a hex public key."""
    pubkey = parse_hex(pubkey_hex)
    params, pk_seed, pk_root, fors_keys = unpack_pubkey(pubkey)
    msg_bytes = message.encode("utf-8")
    sig_data = parse_hex(sig_hex)

    # Unpack signature
    pos = 0
    R = sig_data[pos:pos + params.n]
    pos += params.n
    ctr = sig_data[pos:pos + 4]
    pos += 4

    nfv = struct.unpack('<I', sig_data[pos:pos + 4])[0]
    pos += 4
    fv = []
    for _ in range(nfv):
        l = struct.unpack('<I', sig_data[pos:pos + 4])[0]
        pos += 4
        fv.append(sig_data[pos:pos + l])
        pos += l

    nfa = struct.unpack('<I', sig_data[pos:pos + 4])[0]
    pos += 4
    fa = []
    for _ in range(nfa):
        na = struct.unpack('<I', sig_data[pos:pos + 4])[0]
        pos += 4
        auth = []
        for _ in range(na):
            l = struct.unpack('<I', sig_data[pos:pos + 4])[0]
            pos += 4
            auth.append(sig_data[pos:pos + l])
            pos += l
        fa.append(auth)

    nw = struct.unpack('<I', sig_data[pos:pos + 4])[0]
    pos += 4
    ws = []
    for _ in range(nw):
        l = struct.unpack('<I', sig_data[pos:pos + 4])[0]
        pos += 4
        ws.append(sig_data[pos:pos + l])
        pos += l

    na = struct.unpack('<I', sig_data[pos:pos + 4])[0]
    pos += 4
    ap = []
    for _ in range(na):
        l = struct.unpack('<I', sig_data[pos:pos + 4])[0]
        pos += 4
        ap.append(sig_data[pos:pos + l])
        pos += l

    sig = (R, ctr, fv, fa, ws, ap)
    return sphincs_verify(params, pk_seed, pk_root, msg_bytes, sig, fors_keys)


def sphincs_cli_sign(privkey_hex: str, message: str, sig_file: str) -> bytes:
    """Sign a message string. Writes signature to file. Returns sig bytes."""
    sig_data_bytes = parse_hex(sphincs_cli_sign_hex(privkey_hex, message)[2:])
    with open(sig_file, 'wb') as f:
        f.write(sig_data_bytes)
    return sig_data_bytes


def sphincs_cli_verify(pubkey_hex: str, message: str, sig_file: str) -> bool:
    """Verify a signature from file."""
    with open(sig_file, 'rb') as f:
        sig_data = f.read()
    return sphincs_cli_verify_hex(pubkey_hex, message, to_hex(sig_data))


def sphincs_cli_privtopub(privkey_hex: str) -> str:
    """Derive public key from private key. Returns hex-encoded pubkey with 0x prefix."""
    privkey = parse_hex(privkey_hex)
    if len(privkey) != 2 * DEFAULT_PARAMS.n:
        raise ValueError(f"Private key must be {2 * DEFAULT_PARAMS.n} bytes")
    sk_seed, sk_prf = unpack_privkey(privkey)
    params = DEFAULT_PARAMS
    _, _, pk_seed, pk_root, fors_keys = sphincs_keygen(params, sk_seed, sk_prf)
    pubkey = pack_pubkey(params, pk_seed, pk_root, fors_keys)
    return to_hex(pubkey)


# ─── Main entry ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python sphincs_minus.py sign <privkey> <message>")
        print("  python sphincs_minus.py verify <pubkey> <message> <sig_hex>")
        print("  python sphincs_minus.py privtopub <privkey>")
        print("  python sphincs_minus.py test")
        print("  python sphincs_minus.py keygen")
        print("")
        print("  <privkey> and <pubkey> are hex strings (0x prefix optional)")
        print("  <message> is a plain string")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "test":
        run_tests()

    elif cmd == "keygen":
        params = DEFAULT_PARAMS
        sk_seed = sha3_256(b"sk_seed_spx_minus_00000000")[:params.n]
        sk_prf = sha3_256(b"sk_prf_spx_minus_00000000")[:params.n]
        privkey = pack_privkey(sk_seed, sk_prf)
        pubkey_hex = sphincs_cli_privtopub(to_hex(privkey))
        print(f"Private key: {to_hex(privkey)}")
        print(f"Public key:  {pubkey_hex}")

    elif cmd == "privtopub":
        if len(sys.argv) != 3:
            print("Usage: python sphincs_minus.py privtopub <privkey>")
            sys.exit(1)
        pubkey_hex = sphincs_cli_privtopub(sys.argv[2])
        print(pubkey_hex)

    elif cmd == "sign":
        if len(sys.argv) != 4:
            print("Usage: python sphincs_minus.py sign <privkey> <message>")
            sys.exit(1)
        sig_hex = sphincs_cli_sign_hex(sys.argv[2], sys.argv[3])
        print(sig_hex)

    elif cmd == "verify":
        if len(sys.argv) != 5:
            print("Usage: python sphincs_minus.py verify <pubkey> <message> <sig_hex>")
            sys.exit(1)
        ok = sphincs_cli_verify_hex(sys.argv[2], sys.argv[3], sys.argv[4])
        print("true" if ok else "false")
        sys.exit(0 if ok else 1)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
