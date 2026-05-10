// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {SphincsMinus} from "./SphincsMinus.sol";

/// @title MintGate
/// @notice Mint gate for $SPHINCS. Each mint requires:
///   1) the user has produced a valid SPHINCS- (Vitalik's post-quantum sig)
///      signature over `keccak256("sphincs-mint" || pk_hash || recipient)`,
///      verified off-chain by the backend
///   2) the backend has included the leaf `keccak256(pk_hash, recipient)` in
///      a Merkle root that the SIGNER has posted on-chain
///   3) `pk_hash` has not been used before
///   4) the caller pays exactly `MINT_PRICE` ETH, all of which is forwarded
///      to `DEV` immediately
///
/// The contract is immutable. There is no admin, no pause, no upgrade.
/// `SIGNER` can post Merkle roots; if `SIGNER` goes rogue and posts a fake
/// root, the rogue mints would be visible on-chain and provably absent from
/// the IPFS-published batch.  The total mint is bounded by `MAX_MINTS`, so
/// the worst SIGNER can do is steal mint slots, not mint extra supply.
contract MintGate {
    /// @notice The $SPHINCS token. Hard-wired at construction.
    SphincsMinus public immutable TOKEN;

    /// @notice Address allowed to publish Merkle roots. Off-chain backend.
    address public immutable SIGNER;

    /// @notice Address that receives all mint fees.
    address public immutable DEV;

    /// @notice Tokens minted per slot.
    uint256 public constant MINT_AMOUNT = 500 * 1e18;

    /// @notice ETH price per slot.
    uint256 public constant MINT_PRICE  = 0.0025 ether;

    /// @notice Hard cap on number of mints. 10,000,000 / 500 = 20,000.
    uint256 public constant MAX_MINTS   = 20_000;

    /// @notice Domain tag prepended to every signed message. Bumping this
    ///         would invalidate every previously-issued SPHINCS- sig.
    bytes32 public constant DOMAIN_TAG  = keccak256("sphincs-mint:v1");

    /// @notice Number of mints completed so far.
    uint256 public mintsDone;

    /// @notice Per-epoch Merkle root of accepted leaves. Set by SIGNER.
    mapping(uint256 => bytes32) public roots;

    /// @notice Latest epoch number for which a root was posted.
    uint256 public latestEpoch;

    /// @notice Each `pk_hash` (uniquely identifying a SPHINCS- public key)
    ///         can only mint once.
    mapping(bytes32 => bool) public pkUsed;

    event RootPosted(uint256 indexed epoch, bytes32 root, uint256 leaves);
    event Minted(address indexed recipient, bytes32 indexed pkHash, uint256 epoch);

    error NotSigner();
    error EpochExists();
    error BadEpoch();
    error BadProof();
    error PkAlreadyUsed();
    error WrongPrice();
    error MintCapReached();
    error PayoutFailed();

    /// @notice Pre-mint 10M SPHINCS to `lpRecipient_` (for LP) and 1M to
    ///         `teamRecipient_` (for team). These addresses are written
    ///         into the bytecode at deploy and cannot be changed.
    constructor(
        address signer_,
        address dev_,
        address lpRecipient_,
        address teamRecipient_
    ) {
        SIGNER = signer_;
        DEV = dev_;
        TOKEN = new SphincsMinus(address(this));
        // Genesis allocation: 10M LP reserve + 1M team. Public mint cap
        // (MAX_MINTS * MINT_AMOUNT = 10M) is enforced separately.
        TOKEN.mint(lpRecipient_,   10_000_000 * 1e18);
        TOKEN.mint(teamRecipient_,  1_000_000 * 1e18);
    }

    /// @notice Backend posts a new Merkle root for a fresh epoch.
    /// @param epoch  Sequential epoch number. Must be exactly latestEpoch+1.
    /// @param root   Merkle root over leaves of `keccak256(pkHash, recipient)`.
    /// @param leaves Number of leaves in this batch (informational, indexed in event).
    function postRoot(uint256 epoch, bytes32 root, uint256 leaves) external {
        if (msg.sender != SIGNER) revert NotSigner();
        if (epoch != latestEpoch + 1) revert BadEpoch();
        if (roots[epoch] != bytes32(0)) revert EpochExists();
        roots[epoch] = root;
        latestEpoch = epoch;
        emit RootPosted(epoch, root, leaves);
    }

    /// @notice Mint 500 SPHINCS to `recipient`, gated by a Merkle proof.
    /// @param epoch     The epoch whose root contains this leaf.
    /// @param recipient The address that receives the SPHINCS.
    /// @param pkHash    keccak256 of the user's SPHINCS- public key.
    /// @param proof     Merkle proof from leaf to root.
    function mint(
        uint256 epoch,
        address recipient,
        bytes32 pkHash,
        bytes32[] calldata proof
    ) external payable {
        if (msg.value != MINT_PRICE) revert WrongPrice();
        if (mintsDone >= MAX_MINTS) revert MintCapReached();
        if (pkUsed[pkHash]) revert PkAlreadyUsed();

        bytes32 root = roots[epoch];
        if (root == bytes32(0)) revert BadEpoch();

        bytes32 leaf = keccak256(abi.encode(pkHash, recipient));
        if (!_verify(proof, root, leaf)) revert BadProof();

        pkUsed[pkHash] = true;
        unchecked { mintsDone++; }

        TOKEN.mint(recipient, MINT_AMOUNT);

        (bool ok,) = DEV.call{value: msg.value}("");
        if (!ok) revert PayoutFailed();

        emit Minted(recipient, pkHash, epoch);
    }

    /// @notice OpenZeppelin-style Merkle proof verification (sorted pairs).
    function _verify(bytes32[] calldata proof, bytes32 root, bytes32 leaf)
        internal pure returns (bool)
    {
        bytes32 h = leaf;
        for (uint256 i = 0; i < proof.length; ++i) {
            bytes32 p = proof[i];
            h = h < p
                ? keccak256(abi.encodePacked(h, p))
                : keccak256(abi.encodePacked(p, h));
        }
        return h == root;
    }

    /// @notice Convenience view: how many slots remain.
    function slotsRemaining() external view returns (uint256) {
        return MAX_MINTS - mintsDone;
    }
}
