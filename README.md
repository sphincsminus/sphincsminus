# Sphincs Minus · $SPHINCS

> the first meme coin minted with vitalik's post-quantum signature.
>
> sign once. claim forever. shor can't break us.

[![site](https://img.shields.io/badge/site-sphincs.fun-black)](https://sphincs.fun)
[![mintgate](https://img.shields.io/badge/MintGate-0x6157…f077-blue)](https://etherscan.io/address/0x615771e3510a5898b38ab46da2f5b4ef67a2f077)
[![token](https://img.shields.io/badge/SphincsMinus-0x04a4…b681-blue)](https://etherscan.io/address/0x04a4e420aaea469bbf8c2dc909f4d8a1f761b681)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Built on top of Vitalik Buterin's [SPHINCS- reference](https://github.com/ethereum/research/tree/master/sphincs_minus)
— a hash-only post-quantum signature scheme. Every mint slot is gated by a real
SPHINCS- signature. The signature is verified off-chain (~700-byte sigs are too
big for one mainnet tx), and the backend then signs an EIP-712 ECDSA
**attestation** that the user submits on-chain in a single mint transaction.
Every full audit record `(pk, sig, msg, attestation)` is publicly retrievable
from `/proof?pkHash=…` so anyone can re-verify with the original Python
reference.

## Live deployment (Ethereum mainnet)

| | |
|---|---|
| MintGate     | [`0x2b4496D1eD7367c7C6e830BdfbEd25F7c8fA0122`](https://etherscan.io/address/0x2b4496D1eD7367c7C6e830BdfbEd25F7c8fA0122) |
| SphincsMinus | [`0x86e4c0CA2bCfa5d3A4a89574dcb99122BDF30A4E`](https://etherscan.io/address/0x86e4c0CA2bCfa5d3A4a89574dcb99122BDF30A4E) |
| LP recipient | [`0xAA1a6703Ce598bd309FE296C7B7CE9dCd0697d88`](https://etherscan.io/address/0xAA1a6703Ce598bd309FE296C7B7CE9dCd0697d88) (holds 10M SPHINCS) |
| Team recipient | [`0x7870325c3AB734E8B0824e4aCf183F8e54AE4d2F`](https://etherscan.io/address/0x7870325c3AB734E8B0824e4aCf183F8e54AE4d2F) (holds 1M SPHINCS) |
| DEV / SIGNER | `0xCf28f6e251CFC47aAd38a6D63B40444C5f3fd3F7` |
| Source verified | Sourcify ✓ ([MintGate](https://repo.sourcify.dev/contracts/full_match/1/0x2b4496D1eD7367c7C6e830BdfbEd25F7c8fA0122/), [SphincsMinus](https://repo.sourcify.dev/contracts/full_match/1/0x86e4c0CA2bCfa5d3A4a89574dcb99122BDF30A4E/)) |

## Numbers

| | |
|---|---|
| Name | Sphincs Minus |
| Symbol | SPHINCS |
| Total supply | 21,000,000 |
| Public mint | 10,000,000 (20,000 mints × 500 SPHINCS) |
| LP reserve | 10,000,000 (pre-minted at deploy) |
| Team reserve | 1,000,000 (pre-minted at deploy) |
| Mint price | 0.0025 ETH per slot |
| Mint cap revenue | 50 ETH (= 20,000 × 0.0025) |
| Chain | Ethereum mainnet |

## Repo layout

| dir | purpose |
|---|---|
| `contracts/` | Foundry project. `SphincsMinus.sol` (ERC20) + `MintGate.sol` (Merkle gate) + 11/11 tests pass. |
| `backend/`   | Vercel project. Python `/api/sign`, `/api/keygen`, `/api/sign-and-submit`. TS `/api/proof`, `/api/status`, `/api/post-root` (cron). |
| `frontend/`  | Next.js. 5 static pages: home / mint / proof / whitepaper / faq. |
| `whitepaper/`| Markdown source (also rendered as `/whitepaper` in the frontend). |
| `scripts/`   | dev wallet generator. |

## How a user mints

1. **keygen** in browser → 32-byte sk + 184-byte pk
2. **sign** `keccak256("sphincs-mint:v1") || keccak256(pk) || recipient` → 944-byte sig
3. **POST `/api/sign`** → backend re-runs Vitalik's verifier, queues `(pk_hash, recipient)`
4. backend cron (every 5 min) closes a batch → posts Merkle root via `MintGate.postRoot()`
5. **GET `/api/proof?pkHash=…`** → returns the proof
6. **call `MintGate.mint(epoch, recipient, pk_hash, proof)`** with `value = 0.0025 ETH`
7. contract verifies proof, marks `pk_hash` used, mints 500 SPHINCS, forwards 0.0025 ETH to dev

---

## Deploy guide

### 0 — prerequisites

```bash
# foundry
curl -L https://foundry.paradigm.xyz | bash && foundryup

# node 20+
node --version

# python 3.10+ (for backend tests)
python3 --version
```

### 1 — contracts

```bash
cd contracts
git submodule add https://github.com/foundry-rs/forge-std lib/forge-std   # if not present
forge test -vv          # expect 11/11 PASS

cp .env.example .env
# edit .env: SIGNER, DEV (=0xCf28...d3F7), LP_RECIPIENT, TEAM_RECIPIENT, DEPLOYER_PRIVATE_KEY

source .env
forge script script/Deploy.s.sol:Deploy \
  --rpc-url $RPC_URL --broadcast --verify -vvvv
```

The script prints the `MintGate` and `SphincsMinus` addresses. Save them.

### 2 — backend on Vercel

```bash
cd backend
npm install
vercel link            # create new project, attach this dir
```

Then add env vars in Vercel dashboard (Settings → Environment Variables):

| key | value |
|---|---|
| `UPSTASH_REDIS_REST_URL`   | from Upstash console (create a free Redis db) |
| `UPSTASH_REDIS_REST_TOKEN` | from Upstash console |
| `RPC_URL`                  | mainnet RPC (Ankr / Alchemy / etc.) |
| `SIGNER_PRIVATE_KEY`       | private key of the SIGNER address you set in step 1 |
| `MINTGATE_ADDRESS`         | the address printed by the deploy script |
| `CRON_SECRET`              | any long random string; must match `Authorization: Bearer …` header Vercel cron sends |

Then:

```bash
vercel deploy --prod
```

The cron `/api/post-root` runs every 5 min (configured in `vercel.json`).

### 3 — frontend on Vercel

```bash
cd frontend
cp .env.example .env.local
# edit .env.local: NEXT_PUBLIC_BACKEND_URL, NEXT_PUBLIC_MINTGATE_ADDRESS

vercel link            # separate Vercel project
vercel deploy --prod
```

Point `sphx.lol` (or whatever domain you bought) at the frontend project in Vercel.
Point `api.sphx.lol` at the backend project.

### 4 — sanity check

```bash
# contract is live?
cast call $MINTGATE "MAX_MINTS()(uint256)" --rpc-url $RPC_URL          # 20000
cast call $MINTGATE "mintsDone()(uint256)" --rpc-url $RPC_URL          # 0
cast call $TOKEN "totalSupply()(uint256)" --rpc-url $RPC_URL           # 11000000000000000000000000  (= 11M)

# backend is live?
curl https://api.sphx.lol/api/status

# end-to-end: visit https://sphx.lol/mint
```

---

## Trust model

| Actor | Trust assumption |
|---|---|
| User | Trusts their own laptop (or the in-browser keygen) ran SPHINCS- correctly. |
| Backend | Untrusted for correctness. Cannot mint to wrong recipient (recipient is in signed message). Cannot create fake mint slots (every leaf must have a valid SPHINCS- sig committed to IPFS). At worst, can DoS new mints by refusing to publish roots. |
| Dev | Owns 1M team allocation + 10M LP reserve (held in multisig). Receives 0.0025 ETH × 20,000 = 50 ETH max if fully minted. |
| Smart contract | Immutable. No proxy, no admin, no pause, no withdraw. |

## Operational checklist for the human

- [ ] **dev key cold-storage**: move private key of `0xCf28...d3F7` to a hardware wallet *before* deploy
- [ ] **multisig** for LP_RECIPIENT and TEAM_RECIPIENT (Safe.global recommended)
- [ ] **monitor cron**: Vercel dashboard → Logs → `/api/post-root` should run every 5 min and print `{ ok: true, epoch: N }`
- [ ] **monitor signer ETH**: SIGNER address needs gas to post Merkle roots (~50k gas × 5 gwei × ~5 epochs/hour = trivial, but top up monthly)
- [ ] **publish IPFS bundle weekly**: dump every epoch's `(pk, sig, recipient)` triples to IPFS; pin the CID in the FAQ page

## License

MIT for code. CC-BY-4.0 for the whitepaper. The SPHINCS- algorithm itself is in
the public domain via Vitalik's repo (Apache 2.0).
