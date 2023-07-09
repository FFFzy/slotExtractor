from extractor.main import main as extractor
from crawl2process.Crawl2Process import Crawler
import json

def main():
    var_dict = json.load(open("./invs/0x62931dece3411ada1038c09cd01baa11db08334b/var_dict.json"))

    transactions = []
    workspace = "./tmp"
    eth_address= "0x62931dece3411ada1038c09cd01baa11db08334b"
    invspace = "./invs"

    for blockIndex in var_dict:
        blockNumber, Index = blockIndex.split("_")
        var_dict[blockIndex]["transactionIndex"] = Index
        var_dict[blockIndex]["blockNumber"] = str(var_dict[blockIndex]["blockNumber"])
        transactions.append(var_dict[blockIndex])

        crawler = Crawler(address = eth_address,  workdir=workspace, transactions = transactions)
        result = crawler.crawl2process()
        
    # print("finish")
        extractor(address = eth_address, blockNumber = blockNumber, Index = Index, workdir = invspace, contractName = result["name"], storageLayoutJson = result["storageLayout_file"], input_state_change = result["allstatechanges_file"], input_tx_receipt = result["transactions_file"])

if __name__ ==  "__main__":
    main()