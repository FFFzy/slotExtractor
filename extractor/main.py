#!/bin/python3
from extractor import myContract

def main(address, blockNumber, Index, workdir, contractName, storageLayoutJson, input_state_change, input_tx_receipt):    
    contract = myContract.Contract(address, blockNumber, Index, workdir, contractName, storageLayoutJson,  input_state_change, input_tx_receipt)

    contract.readAllTxs()

    contract.slotReplace()
   
if __name__ == "__main__":
    main()
    