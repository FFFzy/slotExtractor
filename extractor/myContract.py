import os 
import json 
import math 
from web3 import Web3
import traceback
import math 
from alive_progress import alive_bar
INTERNAL_TRANSACTION="internal_transactions"

def toHex(val, size=8):
    # print(type(val))
    if isinstance(val, str):
        assert val.startswith("0x")
        val = int(val, 16)
    try:    
        assert isinstance(val, int)
    except:
        # print(val)
        traceback.print_exc()
        pass
    return '0x{0:0{1}x}'.format(val, size)

def toInt(hexstr):
    if not isinstance(hexstr, int):
        if not isinstance(hexstr, str):
            hexstr = hexstr.hex()
        if hexstr.startswith("0x"):
                return int(hexstr, 16)
        else:
                return int(hexstr)
            
    else:
        return hexstr 

ClassMapping = dict() 
Constants = set()

# For different types including int, uint, array, mapping, struct, enum and etc., 
# each storage must have a known slot and optional value
def Type_init(self, astId, contract, label, offset, slot, type):
    global Constants
    self.astId, self.contract, self.name, self.offset, self.slot, self.type_identifier = astId, contract, label, offset, slot, type 
    
    self.offset = toInt(self.offset)
    self.slot = toInt(self.slot)
    
    try:
        if self.encoding=="dynamic_array":
            self.firstElementSlot = toInt(Web3.soliditySha3(["uint256"], [self.slot]))
            self.value = 0
            self.elements = list() 
            # the num of elements is stored at memory of 'self.slot'
            self.numOfItems = 0
            Constants.add(self.numOfItems)
            Constants.add(self.numOfItems+1)

        elif self.encoding == "mapping":
            self.value = 0
            self.values = dict()
        elif self.encoding == "inplace":
            """
                uint8, .., uint256
                int8, .. , int256
                byte8, .., byte32
                address
                bytes, or string (note: length <= 32 bytes)
                fixed array
            """
            if self.isStruct():
                self.value = ContractStorageMonitor(self.members, self.slot)
            elif self.getType().find("[")==-1 and (self.getType().find("int")!=-1 or self.isEnum() or self.getType().find("bool")!=-1):
                self.value = 0
            elif self.basecls is not None:
                # this is a static array
                baseNumOfBytes = int(ClassMapping[self.basecls].numOfBytes)
                self.staticarraysize = int(int(self.numOfBytes)/baseNumOfBytes)
                self.elements = []
                for i in range(self.staticarraysize):
                    elementSlot = int(self.slot) + int((i*baseNumOfBytes)/32)
                    self.elements.append(self.getBasecls()(astId=self.astId, contract=self.contract, label="", offset=0, slot=elementSlot, type=self.getBasecls().label))
                self.values = self.elements
            else:
                self.value = toHex(0, size=2*self.numOfBytes)
            # TODO 
            pass 
        elif self.encoding == "bytes":
            # TODO 
            # This default value may be not true
            self.value = "0x0"

        # For context slicing; record the tainted mapping keys w.r.t. each transaction
        self.taintedKeys = []
    except Exception as e:
        print(e)
        print(self.members)
        traceback.print_exc()
        raise Exception("Unknown error")

class AbstractStorageItem:
    def __init__(self):
        pass

    def getSlot(self):
        return self.slot

    def getLabel(self):
        return self.name
    
    def getValue(self):
        if self.isInplace() and self.getType().find("int")!=-1:
            if self.basecls is not None:
                return self.values 
            # return int(self.value)%(10**15) 
            else:
                return int(self.value) 
        return self.value
    
    @property
    def mappings(self):
        return self.values

    @classmethod 
    def getType(cls):
        return cls.label

    @classmethod
    def isBytes(cls):
        return cls.encoding == "bytes"

    @classmethod
    def isInplace(cls):
        return cls.encoding == "inplace"

    @classmethod
    def isMapping(cls):
        return cls.encoding=="mapping"
    
    @classmethod
    def isDynamicArray(cls):
        return cls.encoding=="dynamic_array"
    
    @classmethod
    def isFixedArray(cls):
        return cls.encoding=="inplace" and cls.getType().find("[")!=-1
    
    @classmethod
    def isStruct(cls):
        return cls.getType().find("struct") != -1

    @classmethod
    def isEnum(cls):
        return cls.getType().find("enum") != -1

    @classmethod
    def hasArrayMappingValue(cls):
        global ClassMapping
        assert cls.isMapping()
        return ClassMapping[cls.valuecls].encoding=="dynamic_array"
    
    @classmethod
    def hasStructMappingValue(cls):
        global ClassMapping
        assert cls.isMapping()
        return ClassMapping[cls.valuecls].members is not None 
    
    @classmethod
    def getMappingStruct(cls):
        global ClassMapping
        assert cls.hasStructMappingValue()
        return ClassMapping[cls.valuecls]
    
    @classmethod
    def getMappingDynArray(cls):
        global ClassMapping
        assert cls.hasArrayMappingValue()
        return ClassMapping[cls.valuecls]
    
    @classmethod
    def getBasecls(cls):
        assert cls.basecls is not None 
        global ClassMapping
        return ClassMapping[cls.basecls]

    @classmethod
    def getValuecls(cls):
        assert cls.valuecls is not None 
        global ClassMapping
        return ClassMapping[cls.valuecls]
    
    @classmethod
    def getKeycls(cls):
        assert cls.keycls is not None 
        global ClassMapping
        return ClassMapping[cls.keycls]
    
    def _setValue(self, slot, value):
        raise NotImplementedError()

    def setValue(self, slot, value, additionalKeys=list()):
        return self._setValue(slot, value, additionalKeys)

def setValueForInplace(self, slot, value, additionalKeys=list()):
    global Constants
    try:
        assert isinstance(slot, str) and isinstance(value, str)
        assert slot.startswith("0x") and value.startswith("0x")
        slot = "0x"+slot.replace("0x", "")
        value = "0x"+value.replace("0x", "")
            # struct {
            #  uint gameId, 
            #  uint gameStatus
            #  mapping(uint=>address) xxx
            #  mapping(address=>uint) xxx
            # }
        if self.isStruct():
            if self.value.readStateChange(slot, value, additionalKeys):
                return True 
            else:
                return False 
        # print(slot, value, self.label, self.slot)
        if self.slot <= int(slot, 16) and int(slot, 16) <= self.slot + int((int(self.numOfBytes) + int(self.offset) -1) / 32):
            if self.isEnum():
                value = "0x"+value[66-2*(self.offset+self.numOfBytes):66-2*self.offset].replace("0x", "")
                self.value = int(value, 16)
            else:
                if self.basecls is not None:
                    element_slot = int(slot, 16)-self.slot 
                    baseNumOfBytes = self.getBaseCls().numOfBytes
                    element_index_start, element_index_end = element_slot * 32 / baseNumOfBytes, (element_slot+1) * 32 / baseNumOfBytes
                    for index in range(element_index_start, min(element_index_end, self.staticarraysize)):
                        value = "0x"+value[66-2*(self.offset+(index+1)*baseNumOfBytes):66-2*(self.offset+index*baseNumOfBytes)].replace("0x", "")
                        if self.getType().find("int")!=-1:
                            value = int(value, 16)
                        elif self.getType().find("bool") !=-1:
                            value = int(value, 16)
                        self.values[index] = value 
                else:
                    value = "0x"+value[66-2*(self.offset+self.numOfBytes):66-2*self.offset].replace("0x", "")
                    if self.getType().find("int")!=-1:
                        self.value = int(value, 16)
                        Constants.add(self.value)
                    elif self.getType().find("bool") !=-1:
                        self.value = int(value, 16)
                        # Constants.add(self.value)
                    else:
                        self.value = value 
                        if self.getType().find("address")!=-1:
                            Constants.add(self.value)
            return True 
        return False 
    except:
        # traceback.print_exc()
        pass
    return False

def setValueForDynamicArray(self, slot, value,  additionalKeys=list()):
    global ClassMapping
    global Constants
    assert isinstance(slot, str) and isinstance(value, str)
    assert slot.startswith("0x") and value.startswith("0x")
   
    try:
        # if int(slot, 16) - self.firstElementSlot <=10 and int(slot, 16) - self.firstElementSlot >=0:
        #     if config.DEBUG:
        #         print("should find an array slot for ", slot,  int(slot, 16) - self.firstElementSlot)
        #         print("condition: self.firstElementSlot + int(self.getBasecls().numOfBytes*(len(self.elements)+1)/32) - int(slot, 16) = ",self.firstElementSlot + int(self.getBasecls().numOfBytes*(len(self.elements)+1)/32) - int(slot, 16))
            
        if int(slot, 16) == self.slot:
            self.value = int(value, 16)
            self.numOfItems = self.value 
            Constants.add(self.numOfItems)
            Constants.add(self.numOfItems+1)
            return True

        elif self.firstElementSlot <= int(slot, 16) \
        and int(slot, 16) <= (self.firstElementSlot + math.ceil(self.getBasecls().numOfBytes/32)*(len(self.elements)+1)):
            # if config.DEBUG:
            #     print("find array slot...")
            index = int((int(slot, 16) - self.firstElementSlot) /math.ceil(self.getBasecls().numOfBytes/32))
            # TODO
            # Here, we assume every item in an array are stored at a new slot
            # This may be not true. May apply to uint128 ... uint256 only
            # Need to check later
            elementSlot = index * math.ceil(self.getBasecls().numOfBytes/32) + self.firstElementSlot
            assert elementSlot <= int(slot, 16), "elementSlot must be less than or equal to slot"
            if index < len(self.elements):
                # if config.DEBUG:
                #     print("update item")
                self.elements[index].setValue(slot, value)
            else:
                # if config.DEBUG:
                #     print("create item")
                self.elements.append(self.getBasecls()(astId=self.astId, contract=self.contract, label="", offset=0, slot=elementSlot, type=self.getBasecls().label))
                self.elements[-1].setValue(slot, value)
                self.numOfItems = len(self.elements)
            return True 
    except:
        traceback.print_exc()
    return False 

from functools import lru_cache
@lru_cache
def soliditySha3(key, slot):
    if isinstance(key, int):
                key = key
    elif isinstance(key, str):
                if key.startswith("0x"):
                    key = int(key, 16) 
                else:
                    key = int(key)
    else:
                assert False, f"{key} is not supported"
    assert key >= 0
    return Web3.soliditySha3(["uint256", "uint256"], [key, slot])

def setValueForMapping(self, slot, value, additionalKeys=list()):
    global ClassMapping
    global Constants
    assert isinstance(slot, str) and isinstance(value, str)
    assert slot.startswith("0x") and value.startswith("0x")

    @lru_cache
    def calculateKeySlot(key):
        #  mapping(uintXX=>) or mapping(intXXX => )
        if ClassMapping[self.keycls].label.find("int")!=-1 and ClassMapping[self.keycls].label.find("[")==-1:
            ret = soliditySha3(key, self.slot)
            # print("int", ret, ret.hex())
            return toInt(ret.hex())
        # mapping(address=>) or mapping(address => )
        elif ClassMapping[self.keycls].label.find("address")!=-1 and ClassMapping[self.keycls].label.find("[")==-1:
            ret = soliditySha3(key, self.slot)
            # print("address", ret, ret.hex())
            return toInt(ret.hex())
        
        # mapping(bytes32=>) or mapping(bytes32 => )
        elif ClassMapping[self.keycls].label.find("bytes32")!=-1 and ClassMapping[self.keycls].label.find("[")==-1:
            ret = soliditySha3(key, self.slot)
            # print("bytes32", ret, ret.hex())
            return toInt(ret.hex())

        elif (isinstance(key, int) or isinstance(key, str)) and \
             ClassMapping[self.keycls].numOfBytes *2 +2 > (len(hex(key)) if isinstance(key, int) else len(key)):
            ret = soliditySha3(key, self.slot)
            # print("key of arbitrary type:", key, ret.hex())
            return toInt(ret.hex())
        else:
            assert False, f"{key} is not supported for {self.__class__}"
            # pass 
    
    keycls = self.getKeycls()

    # print("additionalKeys", additionalKeys)
    for key in additionalKeys:
            # try:
                if keycls.getType().find("int")!=-1:
                    if isinstance(key, str):
                        if key.startswith("0x"):
                            key = int(key, 16)
                        else:
                            key = int(key)
                candiate_slot = calculateKeySlot(key)
                # print("candiate_slot:", key, candiate_slot)
             
                if key not in self.values:
                    var = self.getValuecls()(astId=self.astId, contract=self.contract, label="", offset=0, slot=candiate_slot, type=self.getValuecls().label)
                else:
                    var = self.values[key]
                if True == var.setValue(slot, value, additionalKeys=additionalKeys):
                    self.values[key] = var 
                    # self.taintedKeys = []
                    self.taintedKeys.append(key)
                    # incase there is a nested mapping structure
                    if len(var.taintedKeys)>0:
                        self.taintedKeys.append(var.taintedKeys)
                    return True 
            # except:
            #     pass 
    
    return False 

def setValueForStructMappingValue(self, slot, value, additionalKeys=list()):
    return self.setValueForMapping(slot, value, additionalKeys ) 

def setValueForArrayMappingValue(self, slot, value, additionalKeys=list()):
    return self.setValueForMapping(slot, value, additionalKeys)  

def setValueForInplaceStructValue(self, slot, value, additionalKeys=list()):
    return self.setValueForMapping(slot, value, additionalKeys) 

def setValueForBytes(self, slot, value, additionalKeys=list()):
    if self.setValueForInplace(slot, value, additionalKeys):
        return True 
    #  Here, we assume all the bytes string is less than 32 bytes
    # elif self.setValueForDynamicArray(slot, value, additionalKeys):
    #     return True 
    else:
        return False 

def _setValue(self, slot, value, additionalKeys=list()):
    if self.isInplace():
        return self.setValueForInplace(slot, value, additionalKeys) 
    elif self.isDynamicArray():
        return self.setValueForDynamicArray(slot, value, additionalKeys) 
    elif self.isMapping():
        return self.setValueForMapping(slot, value, additionalKeys)  
        # if self.hasStructMappingValue():
        #     return self.setValueForStructMappingValue(slot, value, additionalKeys) 
        # elif self.hasArrayMappingValue():
        #     return self.setValueForStructMappingValue(slot, value, additionalKeys) 
        # else:   
        #     return self.setValueForInplaceStructValue(slot, value, additionalKeys) 
    elif self.isBytes():
        return self.setValueForBytes(slot, value, additionalKeys)
    else:
        raise LookupError(f"unfounded variable type {self}")
            
def createTypeClasses(types):
    global ClassMapping
    for type_identifier in types:
        try:
            if isinstance(type_identifier, dict):
                type_identifier = type_identifier["type"]
            
            ClassMapping[type_identifier] = type(type_identifier, (AbstractStorageItem, ), \
                {
                    "encoding": types[type_identifier]["encoding"],
                    "label": types[type_identifier]["label"],
                    "basecls": types[type_identifier]["base"] if "base" in types[type_identifier] else None,
                    "numOfBytes": toInt(types[type_identifier]["numberOfBytes"]) if "numberOfBytes" in types[type_identifier] else None,
                    "keycls": types[type_identifier]["key"] if "key" in types[type_identifier] else None,
                    "valuecls": types[type_identifier]["value"] if "value" in types[type_identifier] else None,
                    "members": types[type_identifier]["members"] if "members" in types[type_identifier] else None,
                    "__init__": Type_init,
                    "_setValue": _setValue,
                    "setValueForInplace": setValueForInplace, 
                    "setValueForDynamicArray": setValueForDynamicArray,
                    "setValueForMapping": setValueForMapping, 
                    "setValueForStructMappingValue": setValueForStructMappingValue, 
                    "setValueForArrayMappingValue": setValueForArrayMappingValue,
                    "setValueForInplaceStructValue": setValueForInplaceStructValue,
                    "setValueForBytes": setValueForBytes,
                }
            )
        except:
            traceback.print_exc()
            print(type_identifier, types)
            # pass 
            raise Exception("Unsupported type")
    pass 

class ContractStorageMonitor:
    
    def __init__(self, storageJson, slot=0, typeJson = None, blockNumber=0, index=0):
        global ClassMapping
        
        self.blockNumber = blockNumber
        self.index = index

        if typeJson is not None:
            try:
                if type(storageJson) == int:
                    print(storageJson)
                assert not isinstance(storageJson, int)

                if type(typeJson) == int:
                    print(typeJson)
                assert not isinstance(typeJson, int)
            except:
                print(storageJson)
                print(typeJson)
                raise Exception("unknown error")
            createTypeClasses(types=typeJson)
        
        self.slot = toInt(slot) 
        self.storages = list()

        self.storageJson = storageJson
        
        self.availableslots = dict()
        self.grid_storages = dict()
        grid_storages = self.grid_storages 

        self.fields = list()

        self.storages_slot = dict()
        for storageItem in storageJson:
            try:
                astId, contract, label, offset, slot, type_identifier = storageItem["astId"], storageItem["contract"], storageItem["label"],storageItem["offset"],storageItem["slot"],storageItem["type"]
                if isinstance(slot, str):
                    if slot.startswith("0x"):
                        slot = int(slot, 16) + self.slot  
                    else:
                        try:
                            slot = int(slot) + self.slot 
                        except:
                            print(slot, type(slot), self.slot, type(self.slot))
                            raise Exception()

                if isinstance(offset, str):
                    if offset.startswith("0x"):
                        offset = int(offset, 16)
                    else:
                        offset = int(offset)
                if slot not in grid_storages:
                    grid_storages[slot] = dict()
                
                # print(astId, contract, label, offset, slot, type_identifier)
                assert type_identifier in ClassMapping
                # print("test0")
                grid_storages[slot][offset] = ClassMapping[type_identifier](astId, contract, label, offset, slot, type_identifier)
                # print("test1")
                self.storages.append(grid_storages[slot][offset])
                # print("test2")
                setattr(self, label, grid_storages[slot][offset])
                # print("test3")
                self.fields.append((label, grid_storages[slot][offset]))
            except:
                # pass
                traceback.print_exc()
                print(storageItem) 
                print(ClassMapping[type_identifier])
                raise Exception("Unknown Error")
    
    def getFields(self):
        return self.fields


    def getAllInplaceValues(self):
        inplace_values = set() 
        for storageItem in self.storages:
            if storageItem.isInplace() and not storageItem.isStruct() and storageItem.basecls is None:
               inplace_values.add(storageItem.getValue())
        return inplace_values

    def readStateChange(self, slot, value, additionalKeys):
        assert isinstance(value, str), "value should be hex string"
        assert value.startswith("0x")==True, "value should be hex string"
        assert isinstance(slot, str), "slot should be hex string"
        assert slot.startswith("0x")==True, "slot should be hex string"
        # if config.DEBUG:
        #     print(">>>Update storage.\n Slot: {0}\n Value: {1}".format(slot, value))
        # isRoot = False
        # if value.find("-")!=-1:
            # this is a root entry for state change read 
            # oldval, value = value.split("-")
            # isRoot = True 
            # # print("availableslots", self.availableslots)
            # if slot in self.availableslots:
            #     if self.availableslots[slot] != oldval.strip():
            #         assert False, f"the recorded value of {slot} is inconsistent. recorded: {self.availableslots[slot]} vs actual: {oldval}"
            # else:
            #     assert int(oldval, base=16) == 0, f"the recorded value of {slot} is inconsistent. recorded: {0} vs actual: {oldval}"
        hit = False

        for storageItem in self.storages:
            # if self.blockNumber + "_" + self.index == "13672708_275":
            if slot == "0xd7b6990105719101dabeb77144f2a3385c8033acd3af97e9423a695e81ad1ebb" and storageItem.setValue(slot, value, additionalKeys):
                print(slot, value, self.blockNumber)
            if storageItem.setValue(slot, value, additionalKeys):
                if slot not in self.storages_slot:
                    self.storages_slot[slot] = storageItem
                hit = True 
                if storageItem.numOfBytes>=32:
                    break 
                # return True 
        if hit:
            # print(f"{slot} is hit")
            # self.availableslots[slot] = value 
            return True 
        else:
            # if isRoot:
            #     print(f"{slot} not found")
            return False 

    def txStateTransition(self, slot_statechanges, additionalKeys):
        for slot_statechange in slot_statechanges:
                slot, state = tuple(slot_statechange.split(":"))
                self.readStateChange(slot, state, additionalKeys=additionalKeys)


def isString(v_type):
    return  v_type.find("address")!=-1 or v_type.find("bytes")!=-1 or  v_type.find("contract")!=-1
def isBool(v_type):
    return  v_type.find("bool")!=-1 

def isArray(v_type):
    return  v_type.find("[")!=-1

class Contract(ContractStorageMonitor):
    def __init__(self, address, blockNumber, Index, workdir, contractName, storageLayoutJson, input_state_change, input_tx_receipt):
        assert os.path.exists(storageLayoutJson)
        assert os.path.exists(input_tx_receipt)
        assert os.path.exists(input_state_change)
        
        layoutjson = json.load(open(storageLayoutJson))
        types = layoutjson["types"]
        storage = layoutjson["storage"]

        super().__init__(typeJson=types, storageJson = storage, blockNumber = blockNumber, index = Index)
        self.tx_receipts = json.load(open(input_tx_receipt))
        if "result" in self.tx_receipts:
                self.tx_receipts = self.tx_receipts["result"]
        
        self.address = address
        workdir = os.path.abspath(workdir)
        self.workdir = workdir
        if not os.path.exists(self.workdir):
            os.mkdir(self.workdir)
        self.addressdir = f"{self.workdir}/{self.address}"

        self.contractName = contractName
        self.input_state_change = input_state_change
        self.blockNumber = blockNumber
        self.index = Index

        self.tx_blockNumber_index_before_after_contractStatesDataTraces = dict()
        
    def addTxEnvVar(self, blockNumber_index):
        try:
            tx = list(filter(lambda tx: (tx["blockNumber"]+"_"+tx["transactionIndex"]) == blockNumber_index, self.tx_receipts))[0]
        except:
            traceback.print_exc()
        
        callList = tx["callList"]
        for txCall in callList:
            self.envs.add(txCall["from"].lower())
            args = txCall["args"]
            for arg in args:
                if isinstance(arg, dict):
                    if isinstance(arg["content"], str):
                        arg["content"] = arg["content"].lower()
                        self.envs.add(arg["content"])
                    elif isinstance(arg["content"], list):
                        self.envs.update(arg["content"])
                    elif isinstance(arg["content"], int):
                        self.envs.add(arg["content"])
                    else:
                        content = arg["content"]
                        assert False, f"Unsupported parameter type of arg[content] of values {content}"

    def readAllTxs(self):
        statechanges = open(self.input_state_change).read().strip().split("BlockNumber_TxIndex:")[1:]
        self.envs = set() 
        handled_BlockNumber_TxIndex_set = set()
        # with alive_bar(len(statechanges), force_tty=True) as bar:
        for tx_statechange in statechanges:
            self.envs = set() 
            blockNumber_index = tx_statechange.strip().split("\n")[0]
            if blockNumber_index in handled_BlockNumber_TxIndex_set:
                # bar()
                continue
            handled_BlockNumber_TxIndex_set.add(blockNumber_index)

            self.addTxEnvVar(blockNumber_index)

            self.envs.update(self.getAllInplaceValues())
            
            slot_statechanges = tx_statechange.strip().split("\n")[1:]

            self.txStateTransition(slot_statechanges = slot_statechanges, additionalKeys=self.envs)

            # bar()

        if not os.path.exists(f"{self.addressdir}/storageVar.json"):
            storageVar = dict()
        else:
            storageVar = dict(json.load(open(f"{self.addressdir}/storageVar.json")))
        # slot_storages = dict()
        for slot in self.storages_slot:
            if slot not in storageVar:
                storageVar[slot] = dict()
                storageVar[slot]["name"] = self.storages_slot[slot].name
                storageVar[slot]["type"] = self.storages_slot[slot].type_identifier
            # slot_storages[slot] = dict()
            # slot_storages[slot]["name"] = self.storages_slot[slot].name
            # slot_storages[slot]["type"] = self.storages_slot[slot].type_identifier
            # print('\n'.join(['{0}: {1}'.format(item[0], item[1]) for item in self.storages_slot[slot].__dict__.items()]))
            # print(slot, item.lable, item.type)
        if not os.path.exists(self.addressdir):
            os.mkdir(self.addressdir)
        with open(f"{self.addressdir}/storageVar.json", "w+") as f:
            f.write(json.dumps(storageVar))

    def slotReplace(self):
        storageVar = json.load(open(f"{self.addressdir}/storageVar.json"))

        if os.path.exists(f"{self.addressdir}/var_dict_new.json"):
            var_dict = json.load(open(f"{self.addressdir}/var_dict_new.json"))
        else:
            var_dict = json.load(open(f"{self.addressdir}/var_dict.json"))

        for blockIndex in var_dict:
            blockNumber, Index = blockIndex.split("_")
            # if blockNumber > self.blockNumber or (blockNumber == self.blockNumber and self.index > Index):
            #     break
            if self.blockNumber == blockNumber and self.index == Index:
                pre_storage = var_dict[blockIndex]["pre"]["storage"]
                post_storage = var_dict[blockIndex]["post"]["storage"]
                for address_slot in pre_storage:
                    address, slot = address_slot.split("_")
                    if(address == self.address):
                        value = pre_storage[address_slot]
                        if slot in storageVar:
                            var_dict[blockIndex]["pre"]["storage"][address_slot] =  dict()
                            var_dict[blockIndex]["pre"]["storage"][address_slot]["name"] = storageVar[slot]["name"]
                            var_dict[blockIndex]["pre"]["storage"][address_slot]["type"] = storageVar[slot]["type"]
                            var_dict[blockIndex]["pre"]["storage"][address_slot]["value"] = value
                
                for address_slot in post_storage:
                    address, slot = address_slot.split("_")
                    if(address == self.address):
                        value = post_storage[address_slot]
                        if slot in storageVar:
                            var_dict[blockIndex]["post"]["storage"][address_slot] =  dict()
                            var_dict[blockIndex]["post"]["storage"][address_slot]["name"] = storageVar[slot]["name"]
                            var_dict[blockIndex]["post"]["storage"][address_slot]["type"] = storageVar[slot]["type"]
                            var_dict[blockIndex]["post"]["storage"][address_slot]["value"] = value

        with open(f"{self.addressdir}/var_dict_new.json", "w+") as f:
            f.write(json.dumps(var_dict))