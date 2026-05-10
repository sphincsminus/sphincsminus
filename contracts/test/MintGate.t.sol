// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "forge-std/Test.sol";
import {MintGate} from "../src/MintGate.sol";
import {SphincsMinus} from "../src/SphincsMinus.sol";

contract MintGateTest is Test {
    MintGate gate;
    SphincsMinus tok;
    address signer = address(0xA1);
    address dev    = address(0xDE7);
    address lp     = address(0x11);
    address team   = address(0x22);
    address alice  = address(0xa11ce);
    address bob    = address(0xb0b);

    function setUp() public {
        gate = new MintGate(signer, dev, lp, team);
        tok  = gate.TOKEN();
        vm.deal(alice, 10 ether);
        vm.deal(bob, 10 ether);
    }

    function _leaf(bytes32 pkHash, address rcpt) internal pure returns (bytes32) {
        return keccak256(abi.encode(pkHash, rcpt));
    }

    function _pair(bytes32 a, bytes32 b) internal pure returns (bytes32) {
        return a < b ? keccak256(abi.encodePacked(a, b)) : keccak256(abi.encodePacked(b, a));
    }

    function testGenesisAllocation() public view {
        assertEq(tok.balanceOf(lp),   10_000_000 ether);
        assertEq(tok.balanceOf(team),  1_000_000 ether);
        assertEq(tok.totalSupply(),  11_000_000 ether);
    }

    function testTokenMetadata() public view {
        assertEq(tok.name(),     "Sphincs Minus");
        assertEq(tok.symbol(),   "SPHINCS");
        assertEq(uint256(tok.decimals()), 18);
        assertEq(tok.MAX_SUPPLY(), 21_000_000 ether);
    }

    function testOnlyMintGateCanMint() public {
        vm.expectRevert(SphincsMinus.NotMinter.selector);
        tok.mint(alice, 1);
    }

    function testHappyPathMint() public {
        bytes32 pk1 = keccak256("alice-pk");
        bytes32 pk2 = keccak256("bob-pk");
        bytes32 l1  = _leaf(pk1, alice);
        bytes32 l2  = _leaf(pk2, bob);
        bytes32 root = _pair(l1, l2);

        vm.prank(signer);
        gate.postRoot(1, root, 2);
        assertEq(gate.latestEpoch(), 1);

        // Alice mints
        bytes32[] memory proofA = new bytes32[](1);
        proofA[0] = l2;
        uint256 devBefore = dev.balance;

        vm.prank(alice);
        gate.mint{value: 0.0025 ether}(1, alice, pk1, proofA);

        assertEq(tok.balanceOf(alice), 500 ether);
        assertEq(dev.balance - devBefore, 0.0025 ether);
        assertEq(gate.mintsDone(), 1);
        assertTrue(gate.pkUsed(pk1));

        // Bob mints
        bytes32[] memory proofB = new bytes32[](1);
        proofB[0] = l1;

        vm.prank(bob);
        gate.mint{value: 0.0025 ether}(1, bob, pk2, proofB);
        assertEq(tok.balanceOf(bob), 500 ether);
        assertEq(gate.mintsDone(), 2);
    }

    function testCannotReusePk() public {
        bytes32 pk = keccak256("alice-pk");
        bytes32 root = _leaf(pk, alice); // single-leaf tree
        vm.prank(signer);
        gate.postRoot(1, root, 1);

        bytes32[] memory empty = new bytes32[](0);
        vm.prank(alice);
        gate.mint{value: 0.0025 ether}(1, alice, pk, empty);

        vm.prank(alice);
        vm.expectRevert(MintGate.PkAlreadyUsed.selector);
        gate.mint{value: 0.0025 ether}(1, alice, pk, empty);
    }

    function testWrongPriceReverts() public {
        bytes32 pk = keccak256("alice-pk");
        bytes32 root = _leaf(pk, alice);
        vm.prank(signer);
        gate.postRoot(1, root, 1);

        bytes32[] memory empty = new bytes32[](0);
        vm.prank(alice);
        vm.expectRevert(MintGate.WrongPrice.selector);
        gate.mint{value: 0.001 ether}(1, alice, pk, empty);
    }

    function testForgedRecipientFails() public {
        // Backend is honest: signed for alice. Bob tries to claim Alice's slot.
        bytes32 pk   = keccak256("alice-pk");
        bytes32 root = _leaf(pk, alice);
        vm.prank(signer);
        gate.postRoot(1, root, 1);

        bytes32[] memory empty = new bytes32[](0);
        vm.prank(bob);
        vm.expectRevert(MintGate.BadProof.selector);
        gate.mint{value: 0.0025 ether}(1, bob, pk, empty);
    }

    function testBadEpochReverts() public {
        bytes32 pk = keccak256("x");
        bytes32[] memory empty = new bytes32[](0);
        vm.expectRevert(MintGate.BadEpoch.selector);
        gate.mint{value: 0.0025 ether}(99, alice, pk, empty);
    }

    function testOnlySignerCanPostRoot() public {
        vm.expectRevert(MintGate.NotSigner.selector);
        gate.postRoot(1, bytes32(uint256(1)), 0);
    }

    function testEpochMustBeMonotonic() public {
        vm.startPrank(signer);
        gate.postRoot(1, bytes32(uint256(1)), 0);
        vm.expectRevert(MintGate.BadEpoch.selector);
        gate.postRoot(1, bytes32(uint256(2)), 0); // duplicate
        vm.expectRevert(MintGate.BadEpoch.selector);
        gate.postRoot(3, bytes32(uint256(3)), 0); // skipped 2
        gate.postRoot(2, bytes32(uint256(2)), 0); // ok
        vm.stopPrank();
    }

    function testMintCapEnforced() public {
        // Set mintsDone right at the cap
        vm.store(address(gate), bytes32(uint256(0)), bytes32(uint256(20_000)));
        bytes32 pk = keccak256("x");
        bytes32 root = _leaf(pk, alice);
        vm.prank(signer);
        gate.postRoot(1, root, 1);
        bytes32[] memory empty = new bytes32[](0);
        vm.prank(alice);
        vm.expectRevert(MintGate.MintCapReached.selector);
        gate.mint{value: 0.0025 ether}(1, alice, pk, empty);
    }
}
