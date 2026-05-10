import { useState } from "react";
import MintProgress from "../components/MintProgress";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "";
const MINTGATE = (process.env.NEXT_PUBLIC_MINTGATE_ADDRESS || "0x615771e3510a5898b38ab46da2f5b4ef67a2f077") as `0x${string}`;

const MINT_ABI = [
  {
    name: "mint",
    type: "function",
    stateMutability: "payable",
    inputs: [
      { name: "pkHash",    type: "bytes32" },
      { name: "recipient", type: "address" },
      { name: "deadline",  type: "uint256" },
      { name: "v",         type: "uint8"   },
      { name: "r",         type: "bytes32" },
      { name: "s",         type: "bytes32" },
    ],
    outputs: [],
  },
] as const;

type Step =
  | { kind: "idle" }
  | { kind: "generating" }
  | { kind: "ready";    pkHex: string; skHex: string }
  | { kind: "signing";  pkHex: string; skHex: string }
  | { kind: "attested"; pkHex: string; skHex: string; att: Attestation }
  | { kind: "minting";  pkHex: string; skHex: string; att: Attestation }
  | { kind: "minted";   pkHex: string; skHex: string; att: Attestation; txHash: string }
  | { kind: "error";    msg: string };

interface Attestation {
  mintGate: `0x${string}`;
  pkHash:    `0x${string}`;
  recipient: `0x${string}`;
  deadline:  number;
  v: number;
  r: `0x${string}`;
  s: `0x${string}`;
  mintValueWei: string;
  sphincsSig: `0x${string}`;
}

declare global {
  interface Window { ethereum?: any; }
}

export default function Mint() {
  const [step, setStep] = useState<Step>({ kind: "idle" });
  const [recipient, setRecipient] = useState("");

  async function generate() {
    setStep({ kind: "generating" });
    try {
      const r = await fetch(`${BACKEND}/api/keygen`).then((x) => x.json());
      if (!r.ok) throw new Error(r.error || "keygen failed");
      setStep({ kind: "ready", pkHex: r.pk, skHex: r.sk });
    } catch (e: any) {
      setStep({ kind: "error", msg: e.message });
    }
  }

  async function signAndAttest() {
    if (step.kind !== "ready") return;
    if (!/^0x[0-9a-fA-F]{40}$/.test(recipient)) {
      setStep({ kind: "error", msg: "invalid eth address" });
      return;
    }
    const { pkHex, skHex } = step;
    setStep({ kind: "signing", pkHex, skHex });
    try {
      const r = await fetch(`${BACKEND}/api/sign-and-attest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pk: pkHex, sk: skHex, recipient }),
      }).then((x) => x.json());
      if (!r.ok) throw new Error(r.error || "attest failed");
      setStep({ kind: "attested", pkHex, skHex, att: r as Attestation });
    } catch (e: any) {
      setStep({ kind: "error", msg: e.message });
    }
  }

  async function mintNow() {
    if (step.kind !== "attested") return;
    if (typeof window === "undefined" || !window.ethereum) {
      setStep({ kind: "error", msg: "no wallet detected. install MetaMask or similar." });
      return;
    }
    const { pkHex, skHex, att } = step;
    setStep({ kind: "minting", pkHex, skHex, att });
    try {
      // Connect
      await window.ethereum.request({ method: "eth_requestAccounts" });
      const chainIdHex = await window.ethereum.request({ method: "eth_chainId" });
      if (chainIdHex !== "0x1") {
        try {
          await window.ethereum.request({
            method: "wallet_switchEthereumChain",
            params: [{ chainId: "0x1" }],
          });
        } catch {
          throw new Error("please switch your wallet to Ethereum mainnet");
        }
      }

      // Lazy-import viem to keep first-load JS small
      const { createWalletClient, custom, encodeFunctionData } = await import("viem");
      const { mainnet } = await import("viem/chains");

      const wallet = createWalletClient({
        chain: mainnet,
        transport: custom(window.ethereum),
      });
      const [account] = await wallet.getAddresses();

      const data = encodeFunctionData({
        abi: MINT_ABI,
        functionName: "mint",
        args: [
          step.att.pkHash,
          step.att.recipient,
          BigInt(step.att.deadline),
          step.att.v,
          step.att.r,
          step.att.s,
        ],
      });

      const txHash = await wallet.sendTransaction({
        account,
        to: att.mintGate,
        data,
        value: BigInt(att.mintValueWei),
      });
      setStep({ kind: "minted", pkHex, skHex, att, txHash });
    } catch (e: any) {
      setStep({ kind: "error", msg: e.shortMessage || e.message });
    }
  }

  return (
    <>
      <h1>mint.</h1>
      <p style={{ marginTop: 0, color: "var(--muted)", fontStyle: "italic" }}>
        generate a key, sign your address, claim 500 $sphincs in one transaction.
      </p>

      <MintProgress />

      <h2>step 1 — generate a sphincs- key</h2>
      <p>
        a fresh 32-byte key + ~184-byte public key is generated server-side
        (browser keygen coming in v3). the key is single-use — you don&apos;t
        need to save it, but you can if you want.
      </p>
      <button onClick={generate} disabled={step.kind === "generating"}>
        {step.kind === "generating" ? "…generating" : "generate key"}
      </button>

      {(step.kind === "ready" || step.kind === "signing" || step.kind === "attested" || step.kind === "minting" || step.kind === "minted") && (
        <div style={{ marginTop: 16 }}>
          <div className="kv">
            <div className="k">public key</div>
            <div className="v" style={{ wordBreak: "break-all" }}>
              {(step as any).pkHex ?? "(used)"}
            </div>
            <div className="k">private key</div>
            <div className="v" style={{ wordBreak: "break-all" }}>
              {(step as any).skHex ?? "(used)"}
            </div>
            <div className="k">size</div>
            <div className="v">
              pk = {(step as any).pkHex ? ((step as any).pkHex.length - 2) / 2 : "?"} bytes,
              sk = {(step as any).skHex ? ((step as any).skHex.length - 2) / 2 : "?"} bytes
            </div>
          </div>
          <p className="note" style={{ marginTop: 8 }}>
            ↑ this is your post-quantum SPHINCS- keypair. it never touches
            the blockchain — only its keccak256 hash does. v3 will move
            this generation into your browser via WASM.
          </p>
        </div>
      )}

      {(step.kind === "ready" || step.kind === "signing" || step.kind === "attested" || step.kind === "minting" || step.kind === "minted") && (
        <>
          <h2>step 2 — bind to your eth address</h2>
          <p>
            this is the address that will receive your 500 $sphincs.
            it is included in both the SPHINCS- signed message and the
            ECDSA attestation; nobody else can claim this slot.
          </p>
          <input
            placeholder="0x…"
            value={recipient}
            onChange={(e) => setRecipient(e.target.value)}
            disabled={step.kind !== "ready"}
          />
          <div style={{ marginTop: 12 }}>
            <button onClick={signAndAttest} disabled={step.kind !== "ready"}>
              {step.kind === "signing" ? "…signing & attesting" : "sign + get attestation"}
            </button>
          </div>
        </>
      )}

      {(step.kind === "attested" || step.kind === "minting") && (
        <>
          <h2 className="ok">step 3 — connect wallet & mint</h2>
          <p>
            you have a valid SPHINCS- attestation. now broadcast one
            transaction (~150k gas) to claim your 500 $sphincs.
          </p>
          <div className="kv">
            <div className="k">contract</div><div className="v">{step.att.mintGate}</div>
            <div className="k">value</div><div className="v">0.0025 ETH</div>
            <div className="k">deadline</div><div className="v">{new Date(step.att.deadline * 1000).toLocaleString()}</div>
          </div>
          <div style={{ marginTop: 16 }}>
            <button onClick={mintNow} disabled={step.kind === "minting"}>
              {step.kind === "minting" ? "…confirm in wallet" : "mint now"}
            </button>
          </div>
        </>
      )}

      {step.kind === "minted" && (
        <>
          <h2 className="ok">success — 500 $sphincs minted.</h2>
          <p>
            transaction:{" "}
            <a href={`https://etherscan.io/tx/${step.txHash}`} target="_blank" rel="noreferrer">
              {step.txHash}
            </a>
          </p>
          <p>
            audit your mint:{" "}
            <a href={`/proof?pkHash=${step.att.pkHash}`}>
              /proof?pkHash={step.att.pkHash.slice(0, 10)}…
            </a>
            {" "}— see the full SPHINCS- signature and re-verify it offline.
          </p>
          <p className="note">
            if you don&apos;t see SPHINCS in your wallet, add custom token:{" "}
            <code>0x04a4e420aaea469bbf8c2dc909f4d8a1f761b681</code>
          </p>
        </>
      )}

      {step.kind === "error" && (
        <p className="warn" style={{ marginTop: 24 }}>error: {step.msg}</p>
      )}
    </>
  );
}
