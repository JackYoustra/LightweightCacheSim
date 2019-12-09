from sim import *

class Cache(object):
    def __init__(self):
        pass

    def cachePolicy(cache_info):
        if cache_info[0] == "LRU":
            return LRU(cache_info[1]) #size
        elif cache_info[0] == "RRIP":
            return RRIPLevel(cache_info[1], cache_info[2]) #size, bits
        # please implement for the rest of the policies

    def cacheSize(cache_info):
        if cache_info[0] == "LRU":
            return cache_info[1] #size
        elif cache_info[0] == "RRIP":
            return cache_info[1] #size 
        # please implement for the rest of the policies

BLOCK_SIZE = 4096 #4 KB
OFFSET = 4 # ??
class Strata(object):
    def __init__(self, num_dev):
        self.device = [Level] * num_dev
        self.device_size = [None] * num_dev
        self.util_limit = [None] * num_dev
        self.num_dev = num_dev
        self.inode = Inode()
    
    def createDevice(self, level, dev_info, util_limit):
        self.device[level] = Cache.cachePolicy(dev_info)
        self.device_size[level] = Cache.cacheSize(dev_info)
        self.util_limit[level] = util_limit
        # build level heirarchy
        if(level > 0):
            self.device[level-1].child = self.device[level]
    
    def read(self, file: File):
        inode_num = inode.get_inode(file.filename) # get the inode_num for this filename
        # if filename not found in the map, it creates a new entry in inode-> file and 
        # inode->address map . inode will point to empty list if new file
        node_list = inode.get_address_list(inode_num) #node_list is list of [access, dev_level]
        for node in node_list: #node is [access, dev_level]
            if node:
                access, dev_level = node
                opcode = self.device[dev_level].push(access, dev_level) #change inode mappings if migration(s) happen
                for ops in opcode: # op, access, dev_level
                    if ops is not None:
                        if(ops[0] == "DEL") :
                            self.inode.delete_inode_address(ops[1], ops[2])
                        elif(ops[0] == "ADD"):
                            self.inode.add_inode_address(ops[1], ops[2], inode_num)
            else: #it is a new file. Can not read a new file
                raise FileNotFoundError() #or we can simply return ??

    def write(self, file: File):
        inode_num = inode.get_inode(file.filename)
        node_list = inode.get_address_list(inode_num)
        size = file.size
        starting_index = file.starting_index
        num_blocks = size / BLOCK_SIZE
        if not node_list: #new file. start writing from starting_index
            dev_level = 1 #NVM
            for i in range(num_blocks):
                access = Access(starting_index+ (OFFSET*i))
                opcode = self.device[dev_level].push(access, dev_level) #change inode mappings if migration(s) happen
                for ops in opcode: # op, access, dev_level
                    if ops is not None:
                        if(ops[0] == "DEL"):
                            self.inode.delete_inode_address(ops[1], ops[2])
                        elif(ops[0] == "ADD"):
                            self.inode.add_inode_address(ops[1], ops[2], inode_num)
        else:
            i = 0
            for node in node_list:
                if i>= num_blocks:
                    break #we have reached the end of the new writes.
                access, dev_level = node
                if access.address == starting_index + (i*OFFSET): #overwrite
                    if(dev_level == 1): #already in hottest, do nothing
                        pass
                    else:
                        self.device[dev_level].delete_access(access)
                        dev_level = 1 #NVM
                        opcode = self.device[dev_level].push(access, dev_level) #change inode mappings if migration(s) happen
                        for ops in opcode: # op, access, dev_level
                            if ops is not None:
                                if(ops[0] == "DEL"):
                                    self.inode.delete_inode_address(ops[1], ops[2])
                                elif(ops[0] == "ADD"):
                                    self.inode.add_inode_address(ops[1], ops[2], inode_num)
                    i += 1 #go to the next write block of the file

        while(i<num_blocks): #writes beyond the last block assigned to the file
            dev_level = 1 #NVM
            access = Access(starting_index+ (OFFSET*i))
            opcode = self.device[dev_level].push(access, dev_level) #change inode mappings if migration(s) happen
            for ops in opcode: # op, access, dev_level
                if ops is not None:
                    if(ops[0] == "DEL"):
                        self.inode.delete_inode_address(ops[1], ops[2])
                    elif(ops[0] == "ADD"):
                        self.inode.add_inode_address(ops[1], ops[2], inode_num)
            i += 1

class File(object):
    def __init__(self, filename, size, starting_index):
        self.filename = filename
        self.size = size
        self.starting_index = starting_index

class Inode(object):
    def __init__(self):
        self.file_inode = {} #filename -> inode_num
        self.inode_address = {} # inode_num -> [[access, dev_level]]  i.e. list of [access, dev_level]
        self.inode_counter = 0
    
    # given a filename, get inode_num from map
    def get_inode(self, filename):
        if filename in self.file_inode:
            return self.file_inode[filename]
        else: # new file, inode doesn't exist
            self.file_inode[filename] = self.inode_counter
            self.add_new_inode_address(self.inode_counter)
            self.inode_counter += 1
    
    # given inode_num, get list of (access, dev_level) from map
    def get_address_list(self, inode_num):
        return self.inode_address[inode_num]
    
    # new file -> add empty list against inode_num
    def add_new_inode_address(self, inode_num):
        self.inode_address[inode_num] = [] #add a new empty entry to the inode - address map
    
    # delete this access element's entry from the inode_table for that file
    def delete_inode_address(self, access, dev_level):
        elem = [access, dev_level]
        for k,v in self.inode_address.items():
            if elem in v:
                v.remove(elem)
                break
    
    # new block added for the file. add its map to inode, using inode_num
    def add_inode_address(self, access, dev_level, inode_num):
        elem = [access, dev_level]
        val = self.inode_address[inode_num]
        val.append(elem)
        self.inode_address[inode_num] = val

if __name__ == "__main__":
    strata = Strata(4)
    strata.createDevice(1, ["RRIP", 3, 2], )
    strata.createDevice(2, ["LRU", 3])
    strata.device[1].__str__()
    strata.device[2].__str__()

