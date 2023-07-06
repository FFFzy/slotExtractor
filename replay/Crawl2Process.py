import json
import os
import base64
from functools import cmp_to_key
from parsing.storageLayout import main_impl as generateStorageLayout
import os
import requests 
from bs4 import BeautifulSoup as soup
import pandas as pd 
import json
import cloudscraper
import traceback
import consts.Config as config
import shutil

scraper = cloudscraper.create_scraper(browser='chrome') # returns a CloudScraper instance
scraper.proxies = {"http": "socks5://127.0.0.1:20170", "https": "socks5://127.0.0.1:20170",
    "socks5": "socks5://127.0.0.1:20170"}
INTERNAL_TRANSACTION="internal_transactions"

TransactionThreshold = 50
def getPage(url):
    return getPage2(url)

def getPage1(url):
    resp = requests.get(url)
    body = resp.content
    return body

def getPage2(url):
    global scraper
    body = scraper.get(url).content
    return body 

def getAPIData(url):
    body = getPage(url)
    return json.loads(body.decode("utf8"))["result"]

def getBlockTimeStamp(blockNo):
    url = f"https://api.etherscan.io/api?module=block&action=getblockreward&blockno={blockNo}&apikey={APIKEY_BLOCKCHAIN_ETH}"
    # url = f"https://api.etherscan.io/api?module=proxy&action=eth_getBlockByNumber&tag={hex(blockNo)}&boolean=false&apikey={APIKEY_BLOCKCHAIN_ETH}"
    block = getAPIData(url)
    timeStamp = block["timeStamp"]
    return timeStamp

def checkSelfDestructed(htmlbody):
    hasSelfDestructed = False
    if str(htmlbody).find("Self Destruct")!=-1:
        hasSelfDestructed = True
    
    print("Self Destruct: ", hasSelfDestructed)
    return hasSelfDestructed

def getETHHtmlBody(address):
    body = ""
    url = "https://etherscan.io/address/{0}".format(address)
    body = getPage(url)
    page_soup = soup(body, "html.parser")  
    body = page_soup
    title = page_soup.title.text
    print(title)
    for link in page_soup.find_all('a'):
        if link.get("title")=="Click to view full list":
            # print(link)
            # print(link.text)
            transactionNo = int(link.text.replace(",",""))
    body = page_soup.prettify()
    Transfers_info_table_1 = page_soup.find("div", {"class": "table-responsive"})
    df = pd.read_html(str(Transfers_info_table_1))[0]

    name, compiler_version, optimization, othersetting = tuple([div.text.strip() for div in page_soup.find_all("div", {"class": "col-7 col-lg-8"})])
    print(name, compiler_version, optimization, othersetting)
    divs = page_soup.select(".mb-4 ")
    # print(divs)
    arguments = "" 
    for div in divs:
        h4s = div.select("div h4")
        if len(h4s)>0:
            h4 = h4s[0]
            if h4 is not None and h4.text.find("Constructor Arguments")!=-1:
                arguments = div.select("div pre")[0].text.split("-----Decoded View---------------")[0]
                print(arguments)
                break    
    last_tx_date = df.iloc[0, 4]    
    is_killed = checkSelfDestructed(body)
    return is_killed, title, transactionNo, last_tx_date, name, compiler_version, optimization, othersetting, arguments

BLOCKCHAIN_ETH = "ETH"
APIKEY_BLOCKCHAIN_ETH = "BEYXCX8H6CDFDE5MUU4WQ6NUTIUKM1ZVQW"
WEBPAGE_FUNC_BLOCKCAHIN_ETH = getETHHtmlBody
APIENDPOINT_BLOCKCHAIN_ETH = "https://api.etherscan.io/api"
SOURCECODE_API_BLOCKCHAIN_ETH = "module=contract&action=getsourcecode&address={0}&apikey={1}"
ABI_API_BLOCKCHAIN_ETH = "module=contract&action=getabi&address={0}&apikey={1}"

def compare(item1, item2):
        if isinstance(item1["blockNumber"], str):
            if item1["blockNumber"].startswith("0x"):
                b1 = int(item1["blockNumber"], 16)
                item1["blockNumber"] = str(b1)
            else:
                b1 = int(item1["blockNumber"], 10)
        else:
            b1 = int(item1["blockNumber"])

        if isinstance(item2["blockNumber"], str):
            if item2["blockNumber"].startswith("0x"):
                b2 = int(item2["blockNumber"], 16)
                item2["blockNumber"] = str(b2)
            else:
                b2 = int(item2["blockNumber"], 10)
        else:
            b2 = int(item2["blockNumber"])
        
        if isinstance(item1["transactionIndex"], str):
            if item1["transactionIndex"].startswith("0x"):
                i1 = int(item1["transactionIndex"], 16)
                item1["transactionIndex"] = i1
            else:
                i1 = int(item1["transactionIndex"], 10)
        else:
            i1 = int(item1["transactionIndex"])

        if isinstance(item2["transactionIndex"], str):
            if item2["transactionIndex"].startswith("0x"):
                i2 = int(item2["transactionIndex"], 16)
                item2["transactionIndex"] = i2
            else:
                i2 = int(item2["transactionIndex"], 10)
        else:
            i2 = int(item2["transactionIndex"])
        
        if b1>b2 or (b1==b2 and i1>i2):
            return 1
        else:
            return -1

def getInTxs(InTxs, address):
    internal_transactions = []
    for InTx in InTxs:
        if (InTx["From"] == address or InTx["To"] == address) and InTx["CallType"] == "Call":
            tx = {}
            tx["action"] = dict()
            # tx["blockNumber"] = tx_json["ExTx"]["BlockNumber"]
            # tx["transactionPosition"] = tx_json["ExTx"]["TxIndex"]
            tx["action"]["from"] = InTx["From"]
            tx["action"]["to"] = InTx["To"]
            tx["action"]["callType"] = "call"
            tx["action"]["value"] = "0x" + str(InTx["Value"])
            tx["action"]["gas"] = str(InTx["Gas"])
            if InTx["Input"] is not None:
                InTx_input = base64.b64decode(InTx["Input"]).hex()
            else:
                InTx_input = ""
            tx["action"]["input"] = "0x" + InTx_input
            # if InTx["InTxs"] is None:
            #     tx["type"] = "call"
            internal_transactions.append(tx)
        if InTx["InTxs"] is not None:
            tx_InTxs = getInTxs(InTx["InTxs"], address)
            if tx_InTxs is not []:
                for tx_InTx in tx_InTxs:
                    internal_transactions.append(tx_InTx)
                
    return internal_transactions

def getSortedAllStates(path, address):
    allStates = []
    for tx_file in os.listdir(path):
        tx_file_path = os.path.join(path, tx_file)
        tx_json = json.load(open(tx_file_path))

        state = {}
        state["blockNumber"] = str(tx_json["ExTx"]["BlockNumber"])
        state["transactionIndex"] = str(tx_json["ExTx"]["TxIndex"])
        try:
            state["storage"] = tx_json["OutputAlloc"][address]["storage"]
        except:
            pass
        allStates.append(state)
    allStates.sort(key=cmp_to_key(compare), reverse=False)
    return allStates

def make_dir(path):
    folders = []
    while not os.path.isdir(path):
        path, suffix = os.path.split(path)
        folders.append(suffix)
    for folder in folders[::-1]:
        path = os.path.join(path, folder)
        os.mkdir(path)

class Crawler:
    def __init__(self, address, workdir="./"):
        self.address = address
        workdir = os.path.abspath(workdir)
        # self.workdir = os.path.join(workdir, "./crawler")
        self.workdir = workdir
        if not os.path.exists(self.workdir):
            os.mkdir(self.workdir)
        # if blockchain == BLOCKCHAIN_ETH:
        self.api_key = APIKEY_BLOCKCHAIN_ETH
        self.apiendpoint = APIENDPOINT_BLOCKCHAIN_ETH
        self.source_api = SOURCECODE_API_BLOCKCHAIN_ETH
        self.abi_api = ABI_API_BLOCKCHAIN_ETH
        self.webpage_func = WEBPAGE_FUNC_BLOCKCAHIN_ETH
        self.addressdir = f"{self.workdir}/{self.address}"
    
    def readLocalSource(self):
        if config.CACHED and os.path.exists(f"{self.addressdir}/config.json"):
            return True, json.load(open(f"{self.addressdir}/config.json"))
        else:
            return False, None
           
    def saveLocal(self, dictobj):
        json.dump(dictobj, open(f"{self.addressdir}/config.json", "w"), indent=6)
          
    def getSourceCode(self):
        url = self.apiendpoint+"?"+self.source_api.format(self.address, self.api_key)
        sourcecode = getAPIData(url)
        # with open(f"./urlData.json", "w") as f:
        #     f.write(json.dumps(sourcecode))
        # There is some case that a lot of source code files are provided
        # TODO 
        contractName = sourcecode[0]["ContractName"]
        compilerVersion = sourcecode[0]["CompilerVersion"]
        constructorArguments = sourcecode[0]["ConstructorArguments"]

        contractCode = sourcecode[0]["SourceCode"]
        if len(contractCode) > 2 and contractCode[0] == contractCode[1] == "{":
            new_code = contractCode[1:-1]
            res = json.loads(new_code)
            sources = res["sources"]
            mainContract_path = ""
            for name in sources:
                _dir, _file = os.path.split(self.addressdir+ "/"+"SourceCode"+ "/"+name)
                # print(name)
                make_dir(_dir)
                # print(_dir)
                if "@openzeppelin" in sources[name]["content"]:
                    sources[name]["content"] = sources[name]["content"].replace("@openzeppelin", self.addressdir+ "/"+"SourceCode"+ "/"+"@openzeppelin")
                sol_file = open(self.addressdir+ "/"+"SourceCode"+ "/"+name, 'w+', encoding='UTF-8')
                sol_file.write(sources[name]["content"])
                
                if "contract "+contractName+" " in sources[name]["content"]:
                    mainContract_path = self.addressdir+ "/"+"SourceCode"+ "/" + name
                sol_file.close()
            assert mainContract_path != "", "Error in source code; either network error or main contract source code is unavailable!"
            return contractName, compilerVersion, constructorArguments, mainContract_path
        else:
            sourcecode = "\n".join([ contract["SourceCode"] for contract in sourcecode ])
            assert isinstance(sourcecode, str), "Error in source code; either network error or source code is unavailable!"
            with open(f"{self.addressdir}/{self.address}.sol", "w") as f:
                f.write(sourcecode.encode("charmap", "ignore").decode("utf8", "ignore"))
            return contractName, compilerVersion, constructorArguments, f"{self.addressdir}/{self.address}.sol"

    def getABI(self):
        url = self.apiendpoint+"?"+self.abi_api.format(self.address, self.api_key)
        abi = getAPIData(url)
        assert isinstance(abi, str), "Error in abi; either network error or abi is unavailable!"
        with open(f"{self.addressdir}/{self.address}.abi", "w") as f:
            f.write(str(abi))
        return f"{self.addressdir}/{self.address}.abi"
        
    # only use at most 10,000 txs for specification mining
    # we target the transactions in the earliest 180 days of deployed smart contracts
  
    def crawl2process(self):
        if os.path.exists(self.addressdir):
            boolflag, results = self.readLocalSource()
            if boolflag:
                nodejs_dir = "/home/fangzy/workplace/slotExtractor/nodejs"
                cmd = f'cd {nodejs_dir} && node decodeTx.js --abi {results["abi_file"]} --tx {results["transactions_file"]} --output {os.path.join(os.path.dirname(results["transactions_file"]), "tx_decode.json")}'
                os.system(cmd)
                assert os.path.exists(os.path.join(os.path.dirname(results["transactions_file"]), "tx_decode.json")), "Decoding error: failed to decode transactions"
                results["tx_decode_file"] = os.path.join(os.path.dirname(results["transactions_file"]), "tx_decode.json") 
                return results 
        if not os.path.exists(self.addressdir):
            os.mkdir(self.addressdir)
        try:
            # crawl
            results = dict()
            contractName, compilerVersion, constructorArguments, sourcecode = self.getSourceCode()
            if contractName is None or compilerVersion is None or contractName == "" or compilerVersion == "":
                shutil.rmtree(self.addressdir)
                with open(os.path.dirname(self.addressdir)+"/sourceCodeNotAvailable.txt", "a") as f:
                    f.write(self.address)
                    f.write("\n")
                exit(-1)
            results["sourcecode_file"] = sourcecode
            results["name"] = contractName
            results["compiler_version"] = compilerVersion
            results["arguments"] = constructorArguments
            abi = self.getABI()
            results["abi_file"] = abi

            # process
            path = f"input/formation_v2/relatedTxs/"
            # path = f"example/tmp/0x0e82fd54ed2221c1594cb9cc96862b587a206047/0x0e82fd54ed2221c1594cb9cc96862b587a206047/"

            # get txs.json
            transactions = []
            for tx_file in os.listdir(path):
                tx_file_path = os.path.join(path, tx_file)
                tx_json = json.load(open(tx_file_path))
                
                tx = {}
                tx["blockNumber"] = str(tx_json["ExTx"]["BlockNumber"])
                tx["timeStamp"] = str(tx_json["ExTx"]["Timestamp"])
                tx["transactionIndex"] = str(tx_json["ExTx"]["TxIndex"])
                tx["gas"] = str(tx_json["ExTx"]["InitialGas"])
                for k, v in tx_json["ExTx"]["InTxs"][0].items():
                    if k == "From":
                        tx["from"] = v
                    elif k == "To":
                        tx["to"] = v
                    elif k == "Value":
                        tx["value"] = str(v)
                    elif k == "Input":
                        if v is not None:
                            input = base64.b64decode(v).hex()
                        else:
                            input = ""
                        tx["input"] = "0x" + input
                    elif k == "InTxs" and v is not None:
                        tx["internal_transactions"] = []
                        tx["internal_transactions"] = getInTxs(v, self.address)
                        if tx["internal_transactions"] == []:
                            del tx["internal_transactions"]
                        else:
                            tx["type"] = "internal_transactions"

                transactions.append(tx)

            transactions.sort(key=cmp_to_key(compare), reverse=False)
            with open(f"{self.addressdir}/txs.json", "w") as f:
                f.write(json.dumps(transactions))

            # get tx_decode.json
            results["transactions_file"] = f"{self.addressdir}/txs.json"
            results["abi_file"] = f"{self.addressdir}/{self.address}.abi"
            nodejs_dir ="/home/fangzy/workplace/slotExtractor/nodejs"
            tx_decode_file = os.path.join(os.path.dirname(results["transactions_file"]), "tx_decode.json")
            cmd = f'cd {nodejs_dir} && node decodeTx.js --abi {results["abi_file"]} --tx {results["transactions_file"]} --output {tx_decode_file}'
            os.system(cmd)
            if not os.path.exists(tx_decode_file):
                print("sourceCodeNotAvailable")
            assert os.path.exists(tx_decode_file), "Decoding error: failed to decode transactions"
            results["tx_decode_file"] = tx_decode_file

            # get state changes
            allStateChanges = list()
            SortedAllStates = getSortedAllStates(path, self.address)
            slot_value = dict()
            for state in SortedAllStates:
                stateChanges = list(["BlockNumber_TxIndex:" + state["blockNumber"] + "_" + state["transactionIndex"]])
                try:
                    for slot in state["storage"]:
                        if slot not in slot_value:
                            if state["storage"][slot] != "0x0000000000000000000000000000000000000000000000000000000000000000":
                                stateChanges.append(":".join([slot, "0x0000000000000000000000000000000000000000000000000000000000000000" + "-" + state["storage"][slot]]))
                        elif slot_value[slot] != state["storage"][slot]:
                            stateChanges.append(":".join([slot, slot_value[slot] + "-" + state["storage"][slot]]))
                        slot_value[slot] = state["storage"][slot]
                except:
                    pass
                allStateChanges.extend(stateChanges)

            with open(f"{self.addressdir}/statechanges.txt", "w") as fo:
                fo.write("\n".join(allStateChanges))
            results["allstatechanges_file"] = f"{self.addressdir}/statechanges.txt"

            # get storage layout
            results["storageLayout_file"] = f"{self.addressdir}/storage.json"
            generateStorageLayout(sol_file= results["sourcecode_file"], contractName=results["name"], compilerVersion=results["compiler_version"], outStorageFile=results["storageLayout_file"])
            assert os.path.exists(results["storageLayout_file"]), "Compiling error: failed to create storage.json"

            self.saveLocal(results)
            return results
        except:
            traceback.print_exc()
            exit(-1)