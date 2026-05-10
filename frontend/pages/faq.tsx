export default function Faq() {
  return (
    <>
      <h1>faq.</h1>

      <h2>is this real post-quantum?</h2>
      <p>
        yes. SPHINCS- is the same hash-only signature scheme that vitalik
        published. its security reduces to the security of keccak256 alone.
        if it ever breaks, ethereum breaks first.
      </p>

      <h2>then why is verification off-chain?</h2>
      <p>
        a real on-chain SPHINCS- verify would cost about 300k gas per mint
        with the <em>test</em> parameters and would dominate the cost of a
        $6 mint. instead, our backend re-runs vitalik&apos;s python verifier,
        and if the signature is valid, signs a short EIP-712 attestation
        with a normal ECDSA key. the on-chain contract <code>ecrecover</code>s
        the attestation in ~5k gas. every (public key, SPHINCS- sig,
        attestation) triple is published to ipfs so anyone can independently
        re-verify with vitalik&apos;s python.
      </p>
      <p>
        we are explicit about this trade-off because pretending otherwise
        would be a lie. if you trust the contract bytecode and the IPFS
        feed, you cannot be cheated of supply or rugged of fees, regardless
        of what the backend does.
      </p>

      <h2>can the backend rug me?</h2>
      <p>
        the backend can <em>delay</em> your mint by refusing to publish the
        next root. it cannot:
      </p>
      <ul className="compact">
        <li>mint to a different address — your address is inside the signed message</li>
        <li>mint extra supply — the contract caps public mint at 10,000,000</li>
        <li>change the price — <code>MINT_PRICE</code> is a constant in the bytecode</li>
        <li>steal your fee — fees are forwarded to the dev wallet on every mint, the contract holds zero ETH</li>
      </ul>

      <h2>what about replays?</h2>
      <p>
        every public key can mint exactly once. the contract stores a
        <code>pkUsed[pkHash]</code> mapping. the message you sign is bound
        to a fixed domain tag (<code>keccak256("sphincs-mint:v1")</code>)
        plus your recipient address, so signatures cannot be reused on any
        other contract.
      </p>

      <h2>what happens at 100% mint?</h2>
      <p>
        when 20,000 mints have been claimed, the public mint is over forever.
        the 10M LP reserve gets paired with ETH on uniswap v4 (we pre-announce
        block number and pool fee). the 1M team reserve unlocks on a 6-month
        linear schedule.
      </p>

      <h2>where do my fees go?</h2>
      <p>
        <code>0.0025 ETH</code> per mint is forwarded to the dev wallet
        (<code>0xCf28…d3F7</code>) at the same time as your tokens are
        minted. there is no withdraw button, no fee escrow. if the
        contract is ever compromised, no ETH is held.
      </p>

      <h2>why &quot;sphincs minus&quot;?</h2>
      <p>
        because vitalik&apos;s repo is called <code>sphincsminus</code>.
        the &quot;minus&quot; is from <em>SPHINCS−C</em>, an optimized
        variant of SPHINCS+ where the C stands for &quot;counter&quot;
        (the FORS+C grinding step). we kept the lowercase, kept the dash,
        and let the meme do the rest.
      </p>
    </>
  );
}
