import type { VercelRequest, VercelResponse } from "@vercel/node";
import { createPublicClient, http, parseAbi } from "viem";
import { mainnet } from "viem/chains";

const GATE_ABI = parseAbi([
  "function mintsDone() view returns (uint256)",
  "function MAX_MINTS() view returns (uint256)",
]);

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Cache-Control", "s-maxage=10");

  const gate = (process.env.MINTGATEV2_ADDRESS ?? process.env.MINTGATE_ADDRESS) as `0x${string}` | undefined;
  const rpc  = process.env.RPC_URL;

  let onChain = { mintsDone: "0", maxMints: "20000" };
  if (gate && rpc) {
    try {
      const pub = createPublicClient({ chain: mainnet, transport: http(rpc) });
      const [m, max] = await Promise.all([
        pub.readContract({ address: gate, abi: GATE_ABI, functionName: "mintsDone" }),
        pub.readContract({ address: gate, abi: GATE_ABI, functionName: "MAX_MINTS" }),
      ]);
      onChain = { mintsDone: m.toString(), maxMints: max.toString() };
    } catch (e: any) {
      // fall through with defaults
    }
  }

  return res.status(200).json({
    ok: true,
    mintGate: gate,
    onChain,
  });
}
