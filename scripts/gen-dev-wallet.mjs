import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";
const pk = generatePrivateKey();
const acc = privateKeyToAccount(pk);
console.log("DEV_ADDRESS=" + acc.address);
console.log("DEV_PRIVATE_KEY=" + pk);
