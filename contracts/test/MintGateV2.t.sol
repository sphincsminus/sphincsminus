// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "forge-std/Test.sol";
import {MintGateV2} from "../src/MintGateV2.sol";
import {SphincsMinus} from "../src/SphincsMinus.sol";

contract MintGateV2Test is Test {
    MintGateV2 gate;
    SphincsMinus tok;

    uint256 signerPk = 0xA11CE;
    address signer;
    address dev = address(0xDE7);
    address lp  = address(0x11);
    address team= address(0x22);
    address alice = address(0xa11ce);
    address bob   = address(0xb0b);

    function setUp() public {
        signer = vm.addr(signerPk);
        gate = new MintGateV2(signer, dev, lp, team);
        tok = gate.TOKEN();
        vm.deal(alice, 10 ether);
        vm.deal(bob, 10 ether);
    }

    function _attest(bytes32 pkHash, address rcpt, uint256 deadline)
        internal view returns (uint8 v, bytes32 r, bytes32 s)
    {
        bytes32 structHash = keccak256(abi.encode(
            gate.ATTEST_TYPEHASH(), pkHash, rcpt, deadline
        ));
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01", gate.DOMAIN_SEPARATOR(), structHash
        ));
        (v, r, s) = vm.sign(signerPk, digest);
    }

    function testGenesisAllocation() public view {
        assertEq(tok.balanceOf(lp),   10_000_000 ether);
        assertEq(tok.balanceOf(team),  1_000_000 ether);
        assertEq(tok.totalSupply(),  11_000_000 ether);
    }

    function testHappyPathMint() public {
        bytes32 pk = keccak256("alice-pk");
        uint256 dl = block.timestamp + 1 hours;
        (uint8 v, bytes32 r, bytes32 s) = _attest(pk, alice, dl);

        uint256 devBefore = dev.balance;
        vm.prank(alice);
        gate.mint{value: 0.0025 ether}(pk, alice, dl, v, r, s);

        assertEq(tok.balanceOf(alice), 500 ether);
        assertEq(dev.balance - devBefore, 0.0025 ether);
        assertEq(gate.mintsDone(), 1);
        assertTrue(gate.pkUsed(pk));
    }

    function testCannotReusePk() public {
        bytes32 pk = keccak256("alice-pk");
        uint256 dl = block.timestamp + 1 hours;
        (uint8 v, bytes32 r, bytes32 s) = _attest(pk, alice, dl);

        vm.prank(alice);
        gate.mint{value: 0.0025 ether}(pk, alice, dl, v, r, s);

        vm.prank(alice);
        vm.expectRevert(MintGateV2.PkAlreadyUsed.selector);
        gate.mint{value: 0.0025 ether}(pk, alice, dl, v, r, s);
    }

    function testForgedRecipientFails() public {
        // Backend signs an attestation for alice. Bob steals it and tries
        // to mint for himself. Recipient is in the signed digest, so the
        // signature won't recover SIGNER.
        bytes32 pk = keccak256("alice-pk");
        uint256 dl = block.timestamp + 1 hours;
        (uint8 v, bytes32 r, bytes32 s) = _attest(pk, alice, dl);

        vm.prank(bob);
        vm.expectRevert(MintGateV2.BadAttestation.selector);
        gate.mint{value: 0.0025 ether}(pk, bob, dl, v, r, s);
    }

    function testWrongSignerFails() public {
        bytes32 pk = keccak256("x");
        uint256 dl = block.timestamp + 1 hours;
        // Sign with a non-signer key
        bytes32 structHash = keccak256(abi.encode(
            gate.ATTEST_TYPEHASH(), pk, alice, dl
        ));
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01", gate.DOMAIN_SEPARATOR(), structHash
        ));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(0xDEADBEEF, digest);

        vm.prank(alice);
        vm.expectRevert(MintGateV2.BadAttestation.selector);
        gate.mint{value: 0.0025 ether}(pk, alice, dl, v, r, s);
    }

    function testExpiredAttestationFails() public {
        bytes32 pk = keccak256("alice-pk");
        uint256 dl = block.timestamp + 1 hours;
        (uint8 v, bytes32 r, bytes32 s) = _attest(pk, alice, dl);

        vm.warp(block.timestamp + 2 hours);
        vm.prank(alice);
        vm.expectRevert(MintGateV2.AttestationExpired.selector);
        gate.mint{value: 0.0025 ether}(pk, alice, dl, v, r, s);
    }

    function testWrongPriceFails() public {
        bytes32 pk = keccak256("alice-pk");
        uint256 dl = block.timestamp + 1 hours;
        (uint8 v, bytes32 r, bytes32 s) = _attest(pk, alice, dl);

        vm.prank(alice);
        vm.expectRevert(MintGateV2.WrongPrice.selector);
        gate.mint{value: 0.001 ether}(pk, alice, dl, v, r, s);
    }

    function testMintCapEnforced() public {
        // Slot mintsDone right before mint() = 19999 -> succeeds.
        // Then second mint at 20000 -> reverts.
        bytes32 pk1 = keccak256("k1");
        bytes32 pk2 = keccak256("k2");
        uint256 dl = block.timestamp + 1 hours;
        (uint8 v1, bytes32 r1, bytes32 s1) = _attest(pk1, alice, dl);
        (uint8 v2, bytes32 r2, bytes32 s2) = _attest(pk2, alice, dl);

        // Set mintsDone = 19999 (storage slot 0)
        vm.store(address(gate), bytes32(uint256(0)), bytes32(uint256(19_999)));
        vm.prank(alice);
        gate.mint{value: 0.0025 ether}(pk1, alice, dl, v1, r1, s1);
        assertEq(gate.mintsDone(), 20_000);

        vm.prank(alice);
        vm.expectRevert(MintGateV2.MintCapReached.selector);
        gate.mint{value: 0.0025 ether}(pk2, alice, dl, v2, r2, s2);
    }

    function testTokenMetadata() public view {
        assertEq(tok.name(),     "Sphincs Minus");
        assertEq(tok.symbol(),   "SPHINCS");
        assertEq(uint256(tok.decimals()), 18);
        assertEq(tok.MAX_SUPPLY(), 21_000_000 ether);
    }

    function testOnlyMintGateCanMintToken() public {
        vm.expectRevert(SphincsMinus.NotMinter.selector);
        tok.mint(alice, 1);
    }
}
