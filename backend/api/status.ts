import type { VercelRequest, VercelResponse } from "@vercel/node";
import { createPublicClient, http, parseAbi } from "viem";
import { mainnet } from "viem/chains";

const GATE_ABI = parseAbi([
  "function mintsDone() view returns (uint256)",
  "function MAX_MINTS() view returns (uint256)",
]);

// Tried in order. First one that returns is used.
// `RPC_URL` (env) is prepended if set.
const FALLBACK_RPCS = [
  "https://eth.drpc.org",
  "https://1rpc.io/eth",
  "https://eth.llamarpc.com",
  "https://ethereum-rpc.publicnode.com",
];

async function readState(gate: `0x${string}`, rpcs: string[]) {
  let lastErr: any = null;
  for (const rpc of rpcs) {
    try {
      const pub = createPublicClient({ chain: mainnet, transport: http(rpc, { timeout: 4000 }) });
      const [m, max] = await Promise.all([
        pub.readContract({ address: gate, abi: GATE_ABI, functionName: "mintsDone" }),
        pub.readContract({ address: gate, abi: GATE_ABI, functionName: "MAX_MINTS" }),
      ]);
      return { ok: true as const, mintsDone: m.toString(), maxMints: max.toString(), rpc };
    } catch (e: any) {
      lastErr = e?.shortMessage ?? e?.message ?? String(e);
    }
  }
  return { ok: false as const, error: lastErr };
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Cache-Control", "s-maxage=10, stale-while-revalidate=60");

  const gate = (process.env.MINTGATEV2_ADDRESS ?? process.env.MINTGATE_ADDRESS) as `0x${string}` | undefined;
  if (!gate) {
    return res.status(500).json({ ok: false, error: "MINTGATEV2_ADDRESS not configured" });
  }

  const rpcs = [process.env.RPC_URL, ...FALLBACK_RPCS].filter(Boolean) as string[];
  const r = await readState(gate, rpcs);

  if (!r.ok) {
    return res.status(502).json({
      ok: false,
      mintGate: gate,
      error: `all RPCs failed: ${r.error}`,
    });
  }

  return res.status(200).json({
    ok: true,
    mintGate: gate,
    rpcUsed: r.rpc,
    onChain: {
      mintsDone: r.mintsDone,
      maxMints:  r.maxMints,
    },
  });
}
