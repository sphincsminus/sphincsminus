// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "forge-std/Script.sol";
import {MintGate} from "../src/MintGate.sol";
import {SphincsMinus} from "../src/SphincsMinus.sol";

/// @notice Deploys MintGate (which auto-deploys SphincsMinus).
///         Reads SIGNER, DEV, LP_RECIPIENT, TEAM_RECIPIENT from env.
///
/// Usage:
///   forge script script/Deploy.s.sol:Deploy \
///       --rpc-url $RPC_URL --broadcast --verify -vvvv
contract Deploy is Script {
    function run() external {
        address signer = vm.envAddress("SIGNER");
        address dev    = vm.envAddress("DEV");
        address lp     = vm.envAddress("LP_RECIPIENT");
        address team   = vm.envAddress("TEAM_RECIPIENT");

        uint256 pk = vm.envUint("DEPLOYER_PRIVATE_KEY");
        vm.startBroadcast(pk);

        MintGate gate = new MintGate(signer, dev, lp, team);
        SphincsMinus token = gate.TOKEN();

        vm.stopBroadcast();

        console2.log("MintGate     :", address(gate));
        console2.log("SphincsMinus :", address(token));
        console2.log("SIGNER       :", signer);
        console2.log("DEV          :", dev);
        console2.log("LP recipient :", lp);
        console2.log("Team recipient:", team);
    }
}
