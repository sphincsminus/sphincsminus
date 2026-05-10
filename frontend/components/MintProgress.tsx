import { useEffect, useState } from "react";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "";

interface Status {
  ok: boolean;
  mintGate?: string;
  onChain: { mintsDone: string; maxMints: string };
}

export default function MintProgress({ compact = false }: { compact?: boolean }) {
  const [s, setS] = useState<Status | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const r = await fetch(`${BACKEND}/api/status`, { cache: "no-store" }).then((x) => x.json());
        if (alive) setS(r);
      } catch (e: any) {
        if (alive) setErr(e.message || "failed");
      }
    }
    load();
    const t = setInterval(load, 15_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (err && !s) {
    return <div className="note">progress unavailable: {err}</div>;
  }
  if (!s) {
    return <div className="note">loading mint progress…</div>;
  }

  const done = Number(s.onChain.mintsDone);
  const cap  = Number(s.onChain.maxMints);
  const pct  = cap > 0 ? (done / cap) * 100 : 0;
  const tokensMinted = done * 500;
  const tokensCap    = cap  * 500;
  const ethRaised    = (done * 0.0025).toFixed(4);

  return (
    <div className="progress-box">
      <div className="progress-row">
        <span className="progress-label">mint progress</span>
        <span className="progress-value">
          {done.toLocaleString()} / {cap.toLocaleString()} ({pct.toFixed(2)}%)
        </span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${Math.max(pct, 0.5)}%` }} />
      </div>
      {!compact && (
        <div className="progress-meta">
          <div>
            <span className="progress-meta-k">tokens minted</span>
            <span className="progress-meta-v">{tokensMinted.toLocaleString()} / {tokensCap.toLocaleString()} SPHINCS</span>
          </div>
          <div>
            <span className="progress-meta-k">eth raised</span>
            <span className="progress-meta-v">{ethRaised} ETH</span>
          </div>
          <div>
            <span className="progress-meta-k">slots remaining</span>
            <span className="progress-meta-v">{(cap - done).toLocaleString()}</span>
          </div>
        </div>
      )}
    </div>
  );
}
