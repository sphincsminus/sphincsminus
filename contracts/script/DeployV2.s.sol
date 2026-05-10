// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "forge-std/Script.sol";
import {MintGateV2} from "../src/MintGateV2.sol";
import {SphincsMinus} from "../src/SphincsMinus.sol";

contract DeployV2 is Script {
    function run() external {
        address signer = vm.envAddress("SIGNER");
        address dev    = vm.envAddress("DEV");
        address lp     = vm.envAddress("LP_RECIPIENT");
        address team   = vm.envAddress("TEAM_RECIPIENT");

        uint256 pk = vm.envUint("DEPLOYER_PRIVATE_KEY");
        vm.startBroadcast(pk);

        MintGateV2 gate = new MintGateV2(signer, dev, lp, team);
        SphincsMinus token = gate.TOKEN();

        vm.stopBroadcast();

        console2.log("MintGateV2   :", address(gate));
        console2.log("SphincsMinus :", address(token));
        console2.log("SIGNER       :", signer);
        console2.log("DEV          :", dev);
        console2.log("LP recipient :", lp);
        console2.log("Team recipient:", team);
    }
}
