// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

/// @title Sphincs Minus
/// @notice ERC-20 token for the Sphincs Minus mint protocol.
/// @dev Minimal ERC-20 (no permits, no extensions). MINTER is set once at
///      construction and is the only address that can mint. There is no
///      burn function, no admin, no upgrade path.
contract SphincsMinus {
    string public constant name = "Sphincs Minus";
    string public constant symbol = "SPHINCS";
    uint8  public constant decimals = 18;

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    /// @notice Hard cap = 21,000,000 SPHINCS. Cannot be increased.
    uint256 public constant MAX_SUPPLY = 21_000_000 * 1e18;

    /// @notice The MintGate contract. Set once. Only address allowed to mint.
    address public immutable MINTER;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    error NotMinter();
    error CapExceeded();
    error InsufficientBalance();
    error InsufficientAllowance();

    constructor(address minter_) {
        MINTER = minter_;
    }

    function transfer(address to, uint256 value) external returns (bool) {
        _transfer(msg.sender, to, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        if (a != type(uint256).max) {
            if (a < value) revert InsufficientAllowance();
            allowance[from][msg.sender] = a - value;
        }
        _transfer(from, to, value);
        return true;
    }

    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function _transfer(address from, address to, uint256 value) internal {
        uint256 b = balanceOf[from];
        if (b < value) revert InsufficientBalance();
        unchecked { balanceOf[from] = b - value; }
        balanceOf[to] += value;
        emit Transfer(from, to, value);
    }

    /// @notice Mint tokens. Only callable by the MINTER (the MintGate).
    function mint(address to, uint256 value) external {
        if (msg.sender != MINTER) revert NotMinter();
        uint256 ts = totalSupply + value;
        if (ts > MAX_SUPPLY) revert CapExceeded();
        totalSupply = ts;
        balanceOf[to] += value;
        emit Transfer(address(0), to, value);
    }
}
