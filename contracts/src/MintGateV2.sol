// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {SphincsMinus} from "./SphincsMinus.sol";

/// @title MintGateV2  -- ECDSA-attestation post-quantum mint gate
/// @notice Each mint requires a fresh EIP-712 attestation from the
///         off-chain SIGNER. The SIGNER only signs an attestation after
///         re-running Vitalik's SPHINCS- verifier on the user's
///         post-quantum signature. The full SPHINCS- signature, public
///         key, and attestation pre-image are published to IPFS so anyone
///         can independently re-verify.
///
///         Single transaction. No Merkle tree. No on-chain cron.
///
/// Trust model:
///   - SIGNER cannot mint to a wrong recipient (recipient is in the EIP-712 hash)
///   - SIGNER cannot mint extra supply (MAX_MINTS hard cap)
///   - SIGNER cannot rug fees (forwarded same-tx; contract holds 0 ETH)
///   - SIGNER can DoS new mints by refusing to issue attestations
///   - Anyone can verify each minted slot's SPHINCS- proof from IPFS
contract MintGateV2 {
    SphincsMinus public immutable TOKEN;

    /// @notice ECDSA address that signs attestations off-chain.
    address public immutable SIGNER;

    /// @notice Address that receives every mint fee.
    address public immutable DEV;

    uint256 public constant MINT_AMOUNT = 500 * 1e18;
    uint256 public constant MINT_PRICE  = 0.0025 ether;
    uint256 public constant MAX_MINTS   = 20_000;

    /// @notice EIP-712 domain separator components
    bytes32 public immutable DOMAIN_SEPARATOR;
    bytes32 public constant ATTEST_TYPEHASH = keccak256(
        "MintAttestation(bytes32 pkHash,address recipient,uint256 deadline)"
    );

    uint256 public mintsDone;
    mapping(bytes32 => bool) public pkUsed;

    event Minted(
        address indexed recipient,
        bytes32 indexed pkHash,
        uint256 mintIndex
    );

    error WrongPrice();
    error MintCapReached();
    error PkAlreadyUsed();
    error AttestationExpired();
    error BadAttestation();
    error PayoutFailed();

    constructor(
        address signer_,
        address dev_,
        address lpRecipient_,
        address teamRecipient_
    ) {
        SIGNER = signer_;
        DEV = dev_;
        TOKEN = new SphincsMinus(address(this));
        TOKEN.mint(lpRecipient_,   10_000_000 * 1e18);
        TOKEN.mint(teamRecipient_,  1_000_000 * 1e18);

        DOMAIN_SEPARATOR = keccak256(
            abi.encode(
                keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
                keccak256(bytes("SphincsMinus")),
                keccak256(bytes("2")),
                block.chainid,
                address(this)
            )
        );
    }

    /// @notice Mint 500 SPHINCS to `recipient`, gated by an ECDSA
    ///         attestation from SIGNER over (pkHash, recipient, deadline).
    /// @param pkHash    keccak256 of the user's SPHINCS- public key.
    /// @param recipient Address that receives 500 SPHINCS.
    /// @param deadline  Unix timestamp after which the attestation is invalid.
    /// @param v,r,s     ECDSA signature from SIGNER.
    function mint(
        bytes32 pkHash,
        address recipient,
        uint256 deadline,
        uint8   v,
        bytes32 r,
        bytes32 s
    ) external payable {
        if (msg.value != MINT_PRICE)        revert WrongPrice();
        if (block.timestamp > deadline)     revert AttestationExpired();
        if (mintsDone >= MAX_MINTS)         revert MintCapReached();
        if (pkUsed[pkHash])                 revert PkAlreadyUsed();

        bytes32 structHash = keccak256(abi.encode(
            ATTEST_TYPEHASH, pkHash, recipient, deadline
        ));
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01", DOMAIN_SEPARATOR, structHash
        ));
        address rec = ecrecover(digest, v, r, s);
        if (rec == address(0) || rec != SIGNER) revert BadAttestation();

        pkUsed[pkHash] = true;
        unchecked { mintsDone++; }

        TOKEN.mint(recipient, MINT_AMOUNT);

        (bool ok,) = DEV.call{value: msg.value}("");
        if (!ok) revert PayoutFailed();

        emit Minted(recipient, pkHash, mintsDone);
    }

    function slotsRemaining() external view returns (uint256) {
        return MAX_MINTS - mintsDone;
    }
}
