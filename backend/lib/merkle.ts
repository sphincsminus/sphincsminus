import { keccak256, encodeAbiParameters, type Hex } from "viem";

// Leaf format must match MintGate._verify exactly:
//   leaf = keccak256(abi.encode(bytes32 pkHash, address recipient))
export function leafHash(pkHash: Hex, recipient: Hex): Hex {
  return keccak256(
    encodeAbiParameters(
      [{ type: "bytes32" }, { type: "address" }],
      [pkHash, recipient],
    ),
  );
}

// Sorted-pair Merkle (matches OpenZeppelin MerkleProof and our MintGate).
function pair(a: Hex, b: Hex): Hex {
  const [lo, hi] = (BigInt(a) < BigInt(b)) ? [a, b] : [b, a];
  // keccak256(abi.encodePacked(lo, hi)) = keccak256 of 64-byte concat
  return keccak256(("0x" + lo.slice(2) + hi.slice(2)) as Hex);
}

export interface MerkleResult {
  root: Hex;
  proofs: Hex[][];   // proofs[i] is the proof for leaves[i]
}

export function buildMerkle(leaves: Hex[]): MerkleResult {
  if (leaves.length === 0) {
    throw new Error("cannot build Merkle from empty leaf list");
  }
  if (leaves.length === 1) {
    return { root: leaves[0], proofs: [[]] };
  }

  // Build all levels bottom-up. At each level, pair adjacent nodes.
  // If the level has odd count, duplicate the last node (matches OZ behavior
  // when used with a sorted-pair tree — but we instead just hash with itself).
  const levels: Hex[][] = [leaves.slice()];
  while (levels[levels.length - 1].length > 1) {
    const cur = levels[levels.length - 1];
    const next: Hex[] = [];
    for (let i = 0; i < cur.length; i += 2) {
      const a = cur[i];
      const b = cur[i + 1] ?? cur[i];
      next.push(pair(a, b));
    }
    levels.push(next);
  }
  const root = levels[levels.length - 1][0];

  // For each leaf, walk up gathering siblings.
  const proofs: Hex[][] = leaves.map((_, idx) => {
    const proof: Hex[] = [];
    let i = idx;
    for (let l = 0; l < levels.length - 1; l++) {
      const lvl = levels[l];
      const sibIdx = i ^ 1;
      const sib = lvl[sibIdx] ?? lvl[i]; // odd-tail dup
      proof.push(sib);
      i = i >> 1;
    }
    return proof;
  });

  return { root, proofs };
}
