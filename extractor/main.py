#!/bin/python3
from extractor import myContract

def main(address, workdir, contractName, storageLayoutJson, input_abi, input_state_change, input_tx_receipt):    
    contract =myContract.Contract(workdir, contractName, storageLayoutJson, input_abi,  input_state_change, input_tx_receipt)

    contract.readAllTxs(address=address)
    contract.printStorageVariables(address=address)
   
if __name__ == "__main__":
    main()
    