/* eslint-disable react/no-unescaped-entities */
export default function Whitepaper() {
  return (
    <article className="paper">
      <header className="paper-head">
        <div className="paper-title">Sphincs Minus: A Post-Quantum Mint Token</div>
        <div className="paper-sub">$SPHINCS · v1.0 · 2026 · sphx.lol</div>
      </header>

      <h2>abstract</h2>
      <p>
        This paper specifies <strong>Sphincs Minus</strong>, an ERC-20 token whose entire
        public mint allocation is gated behind valid <strong>SPHINCS-</strong> post-quantum
        signatures. SPHINCS- is the hash-only signature scheme published by Vitalik
        Buterin in <a href="https://github.com/vbuterin/sphincsminus" target="_blank" rel="noreferrer"><code>vbuterin/sphincsminus</code></a>,
        optimised for verification under the EVM execution model.
      </p>
      <p>
        The contract is immutable, the price is constant, and every minted slot is
        provably the result of a real post-quantum signature. We use a Merkle commitment
        to keep on-chain costs reasonable; the full batch of signatures and public keys
        is published to IPFS and is independently verifiable with Vitalik's reference
        Python implementation.
      </p>
      <p>
        This is a meme coin. We are not pretending it is anything else. The novelty is
        the gating mechanism: every $SPHINCS in circulation is, by construction, a
        receipt for a successful SPHINCS- verification. If a quantum computer ever
        breaks SECP256K1, $SPHINCS holders will be holding the only ERC-20 in existence
        whose existence cannot be retroactively forged.
      </p>

      <h2>1. background</h2>

      <h3>1.1 the quantum threat</h3>
      <p>
        Bitcoin and Ethereum addresses derive from elliptic-curve public keys. Shor's
        algorithm, when implemented on a sufficiently large fault-tolerant quantum
        computer, recovers the private key from the public key in polynomial time. For
        Bitcoin and Ethereum this means that any address that has ever revealed a
        public key (i.e., any address that has ever sent a transaction) is, in the
        post-quantum era, <em>publicly spendable</em>.
      </p>
      <p>
        Estimates of "Q-day" range from 5 to 30 years. The exact date does not matter
        for this paper; what matters is that every signature scheme currently used to
        secure billions of dollars of crypto-assets is, in expectation,
        <em> permanently</em> vulnerable.
      </p>

      <h3>1.2 SPHINCS+ and SPHINCS-</h3>
      <p>
        NIST standardised SPHINCS+ in 2024 as one of the few post-quantum signature
        schemes whose security reduces purely to the security of a cryptographic hash
        function. SPHINCS+ has no number-theoretic assumptions: no lattices, no codes,
        no isogenies, no curves. If <code>SHA-256</code> (or <code>SHA3-256</code>) is
        collision-resistant, SPHINCS+ is unforgeable.
      </p>
      <p>
        Vitalik Buterin's repository <code>vbuterin/sphincsminus</code> (the
        <strong> SPHINCS-</strong> variant) introduces four EVM-friendly modifications:
      </p>
      <ol>
        <li><strong>Hash function</strong>: SHA3-256 instead of SHA-256, so verification can use the EVM's <code>keccak256</code> opcode (with appropriate domain separation).</li>
        <li><strong>FORS+C</strong>: a counter-based trick that reduces signature size by replacing some FORS leaves with a verifiable counter.</li>
        <li><strong>WOTS+C</strong>: a checksum-grinding trick that shortens WOTS+ chains.</li>
        <li><strong>d=2 hypertree</strong>: a flat 2-level structure tuned for on-chain verification cost.</li>
      </ol>
      <p>The <code>test</code> parameter set we use in this paper produces:</p>
      <ul>
        <li><strong>Public key</strong>: 184 bytes</li>
        <li><strong>Signature</strong>: 944 bytes (uncompressed, internal format)</li>
        <li><strong>Verification cost</strong>: ≈ 300,000 gas on-chain (estimated)</li>
      </ul>

      <h2>2. token specification</h2>

      <h3>2.1 tokenomics</h3>
      <table className="paper-table">
        <tbody>
          <tr><td>Name</td><td>Sphincs Minus</td></tr>
          <tr><td>Symbol</td><td><code>SPHINCS</code></td></tr>
          <tr><td>Decimals</td><td>18</td></tr>
          <tr><td>Hard cap</td><td>21,000,000</td></tr>
          <tr><td>Public mint</td><td>10,000,000</td></tr>
          <tr><td>LP reserve</td><td>10,000,000</td></tr>
          <tr><td>Team reserve</td><td>1,000,000</td></tr>
          <tr><td>Mint price</td><td>0.0025 ETH</td></tr>
          <tr><td>Tokens per mint</td><td>500</td></tr>
          <tr><td>Total mint slots</td><td>20,000</td></tr>
          <tr><td>Chain</td><td>Ethereum mainnet</td></tr>
        </tbody>
      </table>

      <h3>2.2 allocation rationale</h3>
      <ul>
        <li><strong>Public mint (10,000,000 = 47.6%)</strong>: claimable through the SPHINCS- gate. Distributed as 20,000 slots × 500 tokens each.</li>
        <li><strong>LP reserve (10,000,000 = 47.6%)</strong>: paired with raised ETH on Uniswap v4 at the conclusion of the public mint. Held in a 2-of-3 multisig until paired.</li>
        <li><strong>Team reserve (1,000,000 = 4.8%)</strong>: 6-month linear vesting from the date of public-mint completion.</li>
      </ul>

      <h3>2.3 revenue projection</h3>
      <p>
        If the public mint reaches its cap, the protocol will have raised
        <strong> 20,000 × 0.0025 = 50 ETH</strong>. All ETH is forwarded to the dev
        wallet at the moment of each mint; the contract never holds ETH.
      </p>

      <h2>3. mint mechanism</h2>

      <h3>3.1 trust model</h3>
      <p>The protocol involves three parties:</p>
      <ol>
        <li><strong>User</strong>: produces a SPHINCS- key pair, signs a message containing their recipient address, submits the signature.</li>
        <li><strong>Signer service</strong> ("backend"): verifies signatures off-chain, batches accepted entries into a Merkle tree, and submits the Merkle root on-chain at fixed intervals.</li>
        <li><strong>MintGate contract</strong>: verifies a Merkle proof, marks the public-key hash as used, mints 500 SPHINCS to the recipient, and forwards the fee.</li>
      </ol>
      <p>
        The contract is the only trusted component for <em>correctness</em>. The
        signer service is trusted only for <em>liveness</em>. Specifically:
      </p>
      <ul>
        <li>The signer <strong>cannot</strong> mint to a wrong recipient. The recipient address is committed inside the signed message; modifying it invalidates the SPHINCS- signature.</li>
        <li>The signer <strong>cannot</strong> mint extra supply. The contract enforces a hard cap of <code>MAX_MINTS = 20,000</code>.</li>
        <li>The signer <strong>cannot</strong> rug fees. The fee is forwarded inside the same transaction that mints; the contract holds no ETH.</li>
        <li>The signer <strong>can</strong> DoS new mints, by refusing to publish further roots. In that case, all already-published roots remain valid and existing proofs remain mintable forever.</li>
      </ul>

      <h3>3.2 message format</h3>
      <p>Every SPHINCS- signature must commit to:</p>
      <pre>{`domain     = keccak256("sphincs-mint:v1")     // 32 bytes
pk_hash    = keccak256(public_key)            // 32 bytes
recipient  = recipient_address                // 20 bytes

msg = domain || pk_hash || recipient          // 84 bytes`}</pre>
      <p>
        This domain separation prevents a SPHINCS- signature produced for any other
        purpose (or for any other contract) from being accepted as a mint
        authorisation.
      </p>

      <h3>3.3 merkle commitment</h3>
      <p>Each batch of accepted entries is hashed into a Merkle tree with leaves:</p>
      <pre>{`leaf_i = keccak256(abi.encode(pk_hash_i, recipient_i))`}</pre>
      <p>
        The Merkle tree uses <strong>sorted-pair hashing</strong>, identical to
        OpenZeppelin's <code>MerkleProof.sol</code>. The root is posted on-chain by
        calling <code>MintGate.postRoot(epoch, root, leaves)</code>. Epochs increase
        monotonically; each epoch is final the moment its transaction is mined.
      </p>

      <h3>3.4 claim flow</h3>
      <ol>
        <li>User obtains their Merkle proof from the backend (<code>GET /api/proof?pkHash=…</code>).</li>
        <li>
          User calls <code>MintGate.mint(epoch, recipient, pk_hash, proof)</code>{" "}
          with <code>value = 0.0025 ETH</code>.
        </li>
        <li>
          The contract:
          <ol type="a">
            <li>checks <code>msg.value == MINT_PRICE</code>,</li>
            <li>checks <code>mintsDone &lt; MAX_MINTS</code>,</li>
            <li>checks <code>pkUsed[pk_hash] == false</code>,</li>
            <li>recomputes the leaf and verifies the Merkle proof against the stored epoch root,</li>
            <li>sets <code>pkUsed[pk_hash] = true</code> and increments <code>mintsDone</code>,</li>
            <li>mints 500 SPHINCS to <code>recipient</code>,</li>
            <li>forwards <code>msg.value</code> to <code>DEV</code>.</li>
          </ol>
        </li>
      </ol>

      <h2>4. security</h2>

      <h3>4.1 contract surface</h3>
      <p>The MintGate contract has exactly three external functions:</p>
      <table className="paper-table">
        <thead>
          <tr><th>Function</th><th>Caller</th><th>Effect</th></tr>
        </thead>
        <tbody>
          <tr><td><code>postRoot(epoch, root, leaves)</code></td><td><code>SIGNER</code></td><td>sets <code>roots[epoch] = root</code></td></tr>
          <tr><td><code>mint(epoch, recipient, pk_hash, proof)</code></td><td>anyone (paying 0.0025 ETH)</td><td>mints 500 SPHINCS, forwards fee</td></tr>
          <tr><td><code>slotsRemaining()</code> (view)</td><td>anyone</td><td>returns <code>MAX_MINTS - mintsDone</code></td></tr>
        </tbody>
      </table>
      <p>
        There is no <code>pause</code>, no <code>withdraw</code>, no
        <code> setOwner</code>, no <code>upgradeTo</code>, no proxy, no admin, no
        timelock, no emergency switch. The bytecode is final at deploy.
      </p>

      <h3>4.2 threat model</h3>
      <table className="paper-table">
        <thead>
          <tr><th>Threat</th><th>Mitigation</th></tr>
        </thead>
        <tbody>
          <tr><td>Replay across chains</td><td><code>keccak256("sphincs-mint:v1")</code> domain tag bound into every signature</td></tr>
          <tr><td>Replay within chain</td><td><code>pkUsed[pk_hash]</code> mapping; one mint per public key</td></tr>
          <tr><td>Recipient theft</td><td>recipient committed in signed message</td></tr>
          <tr><td>Supply inflation</td><td><code>MAX_MINTS</code> constant; LP and team allocations pre-minted in constructor</td></tr>
          <tr><td>Backend rug of fees</td><td>fees forwarded in same tx; contract holds no ETH</td></tr>
          <tr><td>Backend front-running</td><td>recipient bound; backend cannot redirect</td></tr>
          <tr><td>Quantum-day</td><td>SPHINCS- signatures are post-quantum; keccak256-based</td></tr>
        </tbody>
      </table>

      <h3>4.3 verifier correctness</h3>
      <p>
        The verifier is a direct copy of Vitalik's reference Python implementation
        (<code>sphincs_minus.py</code>). The repository ships with a
        <code> verify_test_vector.py</code> script and a <code>test_vector.json</code>
        containing reference vectors; we have verified that the deployed verifier
        produces identical results.
      </p>
      <p>A separate IPFS-hosted bundle for each epoch contains:</p>
      <ul>
        <li>the full list of <code>(public_key, signature, recipient)</code> triples,</li>
        <li>the expected leaf, the position in the Merkle tree, the proof,</li>
        <li>the Merkle root and on-chain transaction hash.</li>
      </ul>
      <p>Anyone can rebuild the tree from this bundle and confirm that the on-chain root matches.</p>

      <h2>5. why off-chain verify</h2>
      <p>
        Verifying a SPHINCS- signature with the <code>test</code> parameters costs an
        estimated 300,000 gas on Ethereum mainnet. At 5 gwei, that is about 0.0015
        ETH per mint <em>purely for verification</em> — comparable to the entire mint
        price.
      </p>
      <p>We considered three options:</p>
      <ol>
        <li><strong>Full on-chain verify</strong>: educationally beautiful, economically suicidal.</li>
        <li><strong>ZK-SNARK of verify</strong>: defers cost to the prover; introduces a trusted setup or a STARK toolchain we are not equipped to ship safely on day 1.</li>
        <li><strong>Off-chain verify + on-chain Merkle commitment + IPFS evidence</strong>: pragmatic, falsifiable, simple to audit.</li>
      </ol>
      <p>
        We chose option 3 with full disclosure. The contract states clearly that the
        trust assumption for <em>liveness</em> is the signer service. The trust
        assumption for <em>correctness</em> is the smart contract alone.
      </p>
      <p>
        A v2 of this protocol may move to ZK-SNARK verification once the ecosystem
        (Risc0, SP1, Jolt, Nexus) for KECCAK-heavy workloads matures. The token
        contract is intentionally compatible with such an upgrade: since
        <code> MintGate</code> is itself the minter, swapping <code>MintGate</code>
        for a v2 gate requires <em>no migration</em> of token holders.
      </p>

      <h2>6. roadmap</h2>
      <table className="paper-table">
        <thead>
          <tr><th>Stage</th><th>Trigger</th><th>Action</th></tr>
        </thead>
        <tbody>
          <tr><td>0</td><td>T-0</td><td>Deploy <code>MintGate</code> and <code>SphincsMinus</code>. LP and team reserves pre-minted.</td></tr>
          <tr><td>1</td><td>first mint</td><td>Backend cron starts publishing Merkle roots every 5 minutes.</td></tr>
          <tr><td>2</td><td>50% mint</td><td>First IPFS audit bundle published; community can independently verify.</td></tr>
          <tr><td>3</td><td>100% mint</td><td>LP reserve paired with raised ETH on Uniswap v4. Team vesting begins.</td></tr>
          <tr><td>4</td><td>T+6 months</td><td>Team vesting completes. Protocol is finished forever.</td></tr>
        </tbody>
      </table>

      <h2>7. acknowledgements</h2>
      <p>
        Vitalik Buterin for <code>vbuterin/sphincsminus</code>. The SPHINCS+ team
        (Aumasson, Bernstein, Dobraunig, Eichlseder, Fluhrer, Gazdag, Hülsing,
        Kampanakis, Kölbl, Lange, Lauridsen, Mendel, Niederhagen, Rechberger,
        Rijneveld, Schwabe, Westerbaan) for the original scheme. NIST for
        standardising post-quantum cryptography.
      </p>
      <p className="disclaimer">
        This is a meme coin. Please do not use it as collateral, as a savings
        vehicle, or as evidence in litigation.
      </p>

    </article>
  );
}
