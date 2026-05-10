---
title: "Sphincs Minus: A Post-Quantum Mint Token"
subtitle: "$SPHINCS · v1.0 · 2026"
author: "sphx.lol"
date: "2026"
geometry: "margin=1in"
fontsize: 11pt
mainfont: "Iowan Old Style"
monofont: "JetBrains Mono"
---

# Abstract

This paper specifies **Sphincs Minus**, an ERC-20 token whose entire public
mint allocation is gated behind valid **SPHINCS-** post-quantum signatures.
SPHINCS- is the hash-only signature scheme published by Vitalik Buterin
in `vbuterin/sphincsminus`, optimised for verification under the EVM execution
model.

The contract is immutable, the price is constant, and every minted slot is
provably the result of a real post-quantum signature. We use a Merkle
commitment to keep on-chain costs reasonable; the full batch of signatures
and public keys is published to IPFS and is independently verifiable with
Vitalik's reference Python implementation.

This is a meme coin. We are not pretending it is anything else. The novelty
is the gating mechanism: every $SPHINCS in circulation is, by construction,
a receipt for a successful SPHINCS- verification. If a quantum computer ever
breaks SECP256K1, $SPHINCS holders will be holding the only ERC-20 in
existence whose existence cannot be retroactively forged.

# 1. Background

## 1.1 The quantum threat

Bitcoin and Ethereum addresses derive from elliptic-curve public keys.
Shor's algorithm, when implemented on a sufficiently large fault-tolerant
quantum computer, recovers the private key from the public key in
polynomial time. For Bitcoin and Ethereum this means that any address
that has ever revealed a public key (i.e., any address that has ever sent
a transaction) is, in the post-quantum era, **publicly spendable**.

Estimates of "Q-day" range from 5 to 30 years. The exact date does not matter
for this paper; what matters is that every signature scheme currently used
to secure billions of dollars of crypto-assets is, in expectation,
*permanently* vulnerable.

## 1.2 SPHINCS+ and SPHINCS-

NIST standardised SPHINCS+ in 2024 as one of the few post-quantum
signature schemes whose security reduces purely to the security of a
cryptographic hash function. SPHINCS+ has no number-theoretic assumptions:
no lattices, no codes, no isogenies, no curves. If `SHA-256` (or `SHA3-256`)
is collision-resistant, SPHINCS+ is unforgeable.

Vitalik Buterin's repository `vbuterin/sphincsminus` (the **SPHINCS-**
variant) introduces three EVM-friendly modifications:

1. **Hash function**: SHA3-256 instead of SHA-256, so verification can use
   the EVM's `keccak256` opcode (with appropriate domain separation).
2. **FORS+C**: a *counter-based* trick that reduces signature size by
   replacing some FORS leaves with a verifiable counter.
3. **WOTS+C**: a *checksum-grinding* trick that shortens WOTS+ chains.
4. **d=2 hypertree**: a flat 2-level structure tuned for on-chain
   verification cost.

The `test` parameter set we use in this paper produces:

- **Public key**: 184 bytes
- **Signature**: 944 bytes (uncompressed, internal format)
- **Verification cost**: ≈ 300,000 gas on-chain (estimated)

# 2. Token Specification

## 2.1 Tokenomics

| | |
|---|---|
| Name | Sphincs Minus |
| Symbol | `SPHINCS` |
| Decimals | 18 |
| Hard cap | 21,000,000 |
| Public mint | 10,000,000 |
| LP reserve | 10,000,000 |
| Team reserve | 1,000,000 |
| Mint price | 0.0025 ETH |
| Tokens per mint | 500 |
| Total mint slots | 20,000 |
| Chain | Ethereum mainnet |

## 2.2 Allocation rationale

- **Public mint (10,000,000 = 47.6%)**: claimable through the SPHINCS- gate.
  Distributed as 20,000 slots × 500 tokens each.
- **LP reserve (10,000,000 = 47.6%)**: paired with raised ETH on Uniswap v4
  at the conclusion of the public mint. Held in a 2-of-3 multisig until
  paired.
- **Team reserve (1,000,000 = 4.8%)**: 6-month linear vesting from the
  date of public-mint completion.

## 2.3 Revenue projection

If the public mint reaches its cap, the protocol will have raised
**20,000 × 0.0025 = 50 ETH**. All ETH is forwarded to the dev wallet at the
moment of each mint; the contract never holds ETH.

# 3. Mint Mechanism

## 3.1 Trust model

The protocol involves three parties:

1. **User**: produces a SPHINCS- key pair, signs a message containing their
   recipient address, submits the signature.
2. **Signer service** ("backend"): verifies signatures off-chain, batches
   accepted entries into a Merkle tree, and submits the Merkle root
   on-chain at fixed intervals.
3. **MintGate contract**: verifies a Merkle proof, marks the public-key
   hash as used, mints 500 SPHINCS to the recipient, and forwards the fee.

The contract is the only trusted component for *correctness*. The signer
service is trusted only for *liveness*. Specifically:

- The signer **cannot mint to a wrong recipient**. The recipient address
  is committed inside the signed message; modifying it invalidates the
  SPHINCS- signature.
- The signer **cannot mint extra supply**. The contract enforces a hard
  cap of `MAX_MINTS = 20,000`.
- The signer **cannot rug fees**. The fee is forwarded inside the same
  transaction that mints; the contract holds no ETH.
- The signer **can DoS new mints**, by refusing to publish further roots.
  In that case, all already-published roots remain valid and existing
  proofs remain mintable forever.

## 3.2 Message format

Every SPHINCS- signature must commit to:

```
domain     = keccak256("sphincs-mint:v1")     // 32 bytes
pk_hash    = keccak256(public_key)            // 32 bytes
recipient  = recipient_address                // 20 bytes

msg = domain || pk_hash || recipient          // 84 bytes
```

This domain separation prevents a SPHINCS- signature produced for any
other purpose (or for any other contract) from being accepted as a mint
authorisation.

## 3.3 Merkle commitment

Each batch of accepted entries is hashed into a Merkle tree with leaves:

```
leaf_i = keccak256(abi.encode(pk_hash_i, recipient_i))
```

The Merkle tree uses **sorted-pair hashing**, identical to OpenZeppelin's
`MerkleProof.sol`. The root is posted on-chain by calling
`MintGate.postRoot(epoch, root, leaves)`. Epochs increase monotonically;
each epoch is final the moment its transaction is mined.

## 3.4 Claim flow

1. User obtains their Merkle proof from the backend (`GET /api/proof?pkHash=…`).
2. User calls
   `MintGate.mint(epoch, recipient, pk_hash, proof)` with `value = 0.0025 ETH`.
3. The contract:
   a. checks `msg.value == MINT_PRICE`,
   b. checks `mintsDone < MAX_MINTS`,
   c. checks `pkUsed[pk_hash] == false`,
   d. recomputes the leaf and verifies the Merkle proof against the
      stored epoch root,
   e. sets `pkUsed[pk_hash] = true` and increments `mintsDone`,
   f. mints 500 SPHINCS to `recipient`,
   g. forwards `msg.value` to `DEV`.

# 4. Security

## 4.1 Contract surface

The MintGate contract has exactly three external functions:

| Function | Caller | Effect |
|---|---|---|
| `postRoot(epoch, root, leaves)` | `SIGNER` | sets `roots[epoch] = root` |
| `mint(epoch, recipient, pk_hash, proof)` | anyone (paying 0.0025 ETH) | mints 500 SPHINCS, forwards fee |
| `slotsRemaining()` (view) | anyone | returns `MAX_MINTS - mintsDone` |

There is no `pause`, no `withdraw`, no `setOwner`, no `upgradeTo`, no
proxy, no admin, no timelock, no emergency switch. The bytecode is
final at deploy.

## 4.2 Threat model

| Threat | Mitigation |
|---|---|
| Replay across chains | `keccak256("sphincs-mint:v1")` domain tag bound into every signature |
| Replay within chain | `pkUsed[pk_hash]` mapping; one mint per public key |
| Recipient theft | recipient committed in signed message |
| Supply inflation | `MAX_MINTS` constant; LP and team allocations pre-minted in constructor |
| Backend rug of fees | fees forwarded in same tx; contract holds no ETH |
| Backend front-running | recipient bound; backend cannot redirect |
| Quantum-day | SPHINCS- signatures are post-quantum; keccak256-based |

## 4.3 Verifier correctness

The verifier is a direct copy of Vitalik's reference Python implementation
(`sphincs_minus.py`). The repository ships with a `verify_test_vector.py`
script and a `test_vector.json` containing reference vectors; we have
verified that the deployed verifier produces identical results.

A separate IPFS-hosted bundle for each epoch contains:

- the full list of `(public_key, signature, recipient)` triples,
- the expected leaf, the position in the Merkle tree, the proof,
- the Merkle root and on-chain transaction hash.

Anyone can rebuild the tree from this bundle and confirm that the on-chain
root matches.

# 5. Why off-chain verify

Verifying a SPHINCS- signature with the `test` parameters costs an
estimated 300,000 gas on Ethereum mainnet. At 5 gwei, that is about
0.0015 ETH per mint *purely for verification* — comparable to the entire
mint price.

We considered three options:

1. **Full on-chain verify**: educationally beautiful, economically suicidal.
2. **ZK-SNARK of verify**: defers cost to the prover; introduces a trusted
   setup or a STARK toolchain we are not equipped to ship safely on day 1.
3. **Off-chain verify + on-chain Merkle commitment + IPFS evidence**:
   pragmatic, falsifiable, simple to audit.

We chose option 3 with full disclosure. The contract states clearly that
the trust assumption for *liveness* is the signer service. The trust
assumption for *correctness* is the smart contract alone.

A v2 of this protocol may move to ZK-SNARK verification once the
ecosystem (Risc0, SP1, Jolt, Nexus) for KECCAK-heavy workloads matures.
The token contract is intentionally compatible with such an upgrade:
since `MintGate` is itself the minter, swapping `MintGate` for a v2 gate
requires *no migration* of token holders.

# 6. Roadmap

| Stage | Trigger | Action |
|---|---|---|
| 0 | T-0 | Deploy `MintGate` and `SphincsMinus`. LP and team reserves pre-minted. |
| 1 | first mint | Backend cron starts publishing Merkle roots every 5 minutes. |
| 2 | 50% mint | First IPFS audit bundle published; community can independently verify. |
| 3 | 100% mint | LP reserve paired with raised ETH on Uniswap v4. Team vesting begins. |
| 4 | T+6 months | Team vesting completes. Protocol is finished forever. |

# 7. Acknowledgements

Vitalik Buterin for `vbuterin/sphincsminus`. The SPHINCS+ team (Aumasson,
Bernstein, Dobraunig, Eichlseder, Fluhrer, Gazdag, Hülsing, Kampanakis,
Kölbl, Lange, Lauridsen, Mendel, Niederhagen, Rechberger, Rijneveld,
Schwabe, Westerbaan) for the original scheme. NIST for standardising
post-quantum cryptography.

This is a meme coin. Please do not use it as collateral, as a savings
vehicle, or as evidence in litigation.
