//SPDX-License-Identifier: Unlicense
pragma solidity 0.8.4;

import "/home/fangzy/workplace/slotExtractor/tmp/0x62931dece3411ada1038c09cd01baa11db08334b/SourceCode/@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "/home/fangzy/workplace/slotExtractor/tmp/0x62931dece3411ada1038c09cd01baa11db08334b/SourceCode/@openzeppelin/contracts/access/Ownable.sol";

contract StableToken is ERC20, Ownable {

    constructor() ERC20("mockSTABLE", "mockSTABLE") {}

    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }

    function _transferOwnership(address newOwner) public onlyOwner {
        transferOwnership(newOwner);
    }
}