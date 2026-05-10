import { useEffect, useState } from "react";
import { useRouter } from "next/router";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "";

interface ProofRecord {
  pkHash:       string;
  pk:           string;
  sphincsSig:   string;
  msg:          string;
  recipient:    string;
  deadline:     number;
  v:            number;
  r:            string;
  s:            string;
  mintGate:     string;
  mintValueWei: string;
  issuedAt:     number;
}

export default function Proof() {
  const router = useRouter();
  const [pkHash, setPkHash] = useState("");
  const [data, setData]     = useState<ProofRecord | null>(null);
  const [err, setErr]       = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = router.query.pkHash;
    if (typeof q === "string" && q !== pkHash) {
      setPkHash(q);
      lookup(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.query]);

  async function lookup(hashOverride?: string) {
    const h = (hashOverride ?? pkHash).trim().toLowerCase();
    if (!/^0x[0-9a-f]{64}$/.test(h)) {
      setErr("invalid pkHash"); setData(null); return;
    }
    setLoading(true); setErr(""); setData(null);
    try {
      const r = await fetch(`${BACKEND}/api/proof?pkHash=${h}`).then((x) => x.json());
      if (!r.ok) throw new Error(r.error || "lookup failed");
      setData(r as ProofRecord);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <h1>proof.</h1>
      <p style={{ marginTop: 0, color: "var(--muted)", fontStyle: "italic" }}>
        every mint slot leaves a complete SPHINCS- signature on file. fetch
        any (pkHash) here and re-verify it offline against vitalik&apos;s python.
      </p>

      <h2>look up by pkHash</h2>
      <input
        placeholder="0x… (64 hex chars)"
        value={pkHash}
        onChange={(e) => setPkHash(e.target.value)}
      />
      <div style={{ marginTop: 12 }}>
        <button onClick={() => lookup()} disabled={loading}>
          {loading ? "…looking up" : "fetch proof"}
        </button>
      </div>

      {err && <p className="warn">error: {err}</p>}

      {data && (
        <>
          <h2 className="ok">attestation record</h2>
          <div className="kv">
            <div className="k">pkHash</div>     <div className="v">{data.pkHash}</div>
            <div className="k">recipient</div>  <div className="v">{data.recipient}</div>
            <div className="k">issued at</div>  <div className="v">{new Date(data.issuedAt * 1000).toUTCString()}</div>
            <div className="k">deadline</div>   <div className="v">{new Date(data.deadline * 1000).toUTCString()}</div>
            <div className="k">mintGate</div>   <div className="v">{data.mintGate}</div>
            <div className="k">value (wei)</div><div className="v">{data.mintValueWei}</div>
          </div>

          <h2>ECDSA attestation (verifies on-chain via ecrecover)</h2>
          <div className="kv">
            <div className="k">v</div><div className="v">{data.v}</div>
            <div className="k">r</div><div className="v">{data.r}</div>
            <div className="k">s</div><div className="v">{data.s}</div>
          </div>

          <h2>SPHINCS- public key ({(data.pk.length - 2) / 2} bytes)</h2>
          <pre>{data.pk}</pre>

          <h2>signed message ({(data.msg.length - 2) / 2} bytes)</h2>
          <p className="note">
            structure: <code>keccak256(&quot;sphincs-mint:v1&quot;) || keccak256(pk) || recipient</code>
          </p>
          <pre>{data.msg}</pre>

          <h2>SPHINCS- signature ({(data.sphincsSig.length - 2) / 2} bytes)</h2>
          <pre style={{ maxHeight: 280 }}>{data.sphincsSig}</pre>

          <h2>how to re-verify offline</h2>
          <p>this entire record is reproducible byte-for-byte. anyone can audit:</p>
          <pre>{`# 1. clone vitalik's reference implementation
git clone https://github.com/vbuterin/sphincsminus
cd sphincsminus

# 2. drop these three blobs into a python REPL
python3
>>> import sphincs_minus as s
>>> pk  = bytes.fromhex("${data.pk.slice(2, 50)}…")     # full pk above
>>> sig = bytes.fromhex("${data.sphincsSig.slice(2, 50)}…")  # full sig above
>>> msg = bytes.fromhex("${data.msg.slice(2)}")            # 84 bytes
>>> # use the unpacker from this project's backend/api/sign.py
>>> # then: s.sphincs_verify(params, pk_seed, pk_root, msg, sig_tuple, fors_keys)
True   # <-- this is the post-quantum proof of authenticity`}</pre>

          <p className="note">
            the on-chain part (ECDSA attestation) is verifiable by any
            tool that can run <code>ecrecover</code> over an EIP-712 digest
            — etherscan, foundry, viem, web3.py.
          </p>
        </>
      )}

      {!data && !loading && !err && !pkHash && (
        <p className="note" style={{ marginTop: 24 }}>
          tip: after you mint on{" "}
          <a href="/mint">/mint</a>, click the audit link in the success
          message to land here automatically.
        </p>
      )}
    </>
  );
}
