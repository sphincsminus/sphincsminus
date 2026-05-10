import MintProgress from "../components/MintProgress";

export default function Home() {
  return (
    <>
      <h1>sphincs minus.</h1>
      <p style={{ marginTop: 0, color: "var(--muted)", fontStyle: "italic" }}>
        the first meme coin gated by vitalik&apos;s post-quantum signature.
      </p>

      <MintProgress />

      <p>
        every mint is unlocked by a real <strong>SPHINCS-</strong> signature
        — the same hash-only post-quantum scheme that vitalik buterin
        published as a reference implementation. no elliptic curves. no shor.
        no trusted setup. just keccak. all of our code is open source at{" "}
        <a href="https://github.com/sphincsminus/sphincsminus" target="_blank" rel="noreferrer">
          github.com/sphincsminus/sphincsminus
        </a>.
      </p>

      <p>
        you generate a 32-byte key on your laptop, sign one message, and
        burn that key forever. the signature mints you 500 $sphincs.
      </p>

      <h2>numbers</h2>
      <div className="kv">
        <div className="k">name</div><div className="v">sphincs minus</div>
        <div className="k">symbol</div><div className="v">SPHINCS</div>
        <div className="k">total supply</div><div className="v">21,000,000</div>
        <div className="k">public mint</div><div className="v">10,000,000  (20,000 mints × 500)</div>
        <div className="k">lp reserve</div><div className="v">10,000,000</div>
        <div className="k">team reserve</div><div className="v">1,000,000</div>
        <div className="k">price per mint</div><div className="v">0.0025 ETH (~$6)</div>
        <div className="k">tokens per mint</div><div className="v">500 $sphincs</div>
        <div className="k">chain</div><div className="v">ethereum mainnet</div>
        <div className="k">mint mechanic</div><div className="v">SPHINCS- sig (off-chain) → ECDSA attestation → mint (on-chain)</div>
      </div>

      <h2>why</h2>
      <p>
        every signature you have ever made — your seed phrase, your hardware
        wallet, every uniswap trade — relies on <em>elliptic curve</em>
        cryptography. shor&apos;s algorithm breaks all of it the day a real
        quantum computer ships.
      </p>
      <p>
        SPHINCS- doesn&apos;t care. its security is reducible to the security
        of <code>keccak256</code> alone. if you can break sphincs-minus, you
        can also break ethereum&apos;s state trie, plasma, optimistic rollup
        fault proofs, every merkle drop ever, and bitcoin&apos;s pow.
      </p>
      <p>
        we minted a meme coin behind it because someone had to.
      </p>

      <h2>how it works (30 seconds)</h2>
      <ul className="compact">
        <li>1. press <em>generate key</em>. server runs vitalik&apos;s reference impl.</li>
        <li>2. type your eth address. press <em>sign</em>. backend re-verifies the SPHINCS- sig and signs an ECDSA attestation.</li>
        <li>3. press <em>mint now</em>. your wallet sends one transaction (~150k gas). contract <code>ecrecover</code>s the attestation and mints 500 $sphincs to you in the same block.</li>
      </ul>

      <h2>trust</h2>
      <ul className="compact">
        <li>contract is <strong>immutable</strong> — no admin, no proxy, no pause.</li>
        <li>backend can <strong>delay</strong> your mint but cannot mint to a wrong address — your address is inside the signed message.</li>
        <li>backend cannot mint <strong>extra</strong> supply — the contract caps public mint at 10M.</li>
        <li>every <code>(pk, sig, msg, attestation)</code> tuple is retrievable at <a href="/proof">/proof</a>. anyone can re-verify with vitalik&apos;s python.</li>
        <li>all source code (contracts, backend, frontend, whitepaper) is MIT-licensed at <a href="https://github.com/sphincsminus/sphincsminus" target="_blank" rel="noreferrer">github.com/sphincsminus/sphincsminus</a>.</li>
      </ul>

      <p style={{ marginTop: 32, display: "flex", gap: 24, flexWrap: "wrap" }}>
        <a href="/mint" style={{ fontFamily: "var(--mono)", fontSize: 16 }}>→ mint now</a>
        <a href="https://github.com/sphincsminus/sphincsminus" target="_blank" rel="noreferrer" style={{ fontFamily: "var(--mono)", fontSize: 16 }}>→ source code (github)</a>
        <a href="https://x.com/SphincsMinus" target="_blank" rel="noreferrer" style={{ fontFamily: "var(--mono)", fontSize: 16 }}>→ twitter (@SphincsMinus)</a>
        <a href="/whitepaper" style={{ fontFamily: "var(--mono)", fontSize: 16 }}>→ whitepaper</a>
      </p>
    </>
  );
}
