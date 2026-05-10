import { Redis } from "@upstash/redis";

export const kv = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

// Key schema:
//   sphx:pending                    -> Redis LIST of JSON {pkHash, recipient}
//   sphx:pk:<pkHash>                -> recipient (also acts as dedup lock)
//   sphx:epoch                      -> int (latest epoch number)
//   sphx:epoch:<n>:root             -> 0x... (the merkle root)
//   sphx:epoch:<n>:leaves           -> JSON list of {pkHash, recipient}
//   sphx:epoch:<n>:tx               -> 0x... (tx hash that posted this epoch)
//   sphx:proof:<pkHash>             -> JSON {epoch, leaf, proof[]}

export const KEY_PENDING = "sphx:pending";
export const KEY_EPOCH   = "sphx:epoch";
export const epochRoot   = (n: number) => `sphx:epoch:${n}:root`;
export const epochLeaves = (n: number) => `sphx:epoch:${n}:leaves`;
export const epochTx     = (n: number) => `sphx:epoch:${n}:tx`;
export const proofKey    = (pkHash: string) => `sphx:proof:${pkHash}`;
