from sim import *

class Cache(object):
    def __init__(self):
        pass
    def cachePolicy(cache_info):
        if cache_info[0] == "LRU":
            return LRU(*cache_info[1:]) #size
        elif cache_info[0] == "RRIP":
            return SRRIPLevel(*cache_info[1:]) #size, bits
        # please implement for the rest of the policies
    def cacheSize(cache_info):
        if cache_info[0] == "LRU":
            return cache_info[1] #size
        elif cache_info[0] == "RRIP":
            return cache_info[1] #size 
        # please implement for the rest of the policies

class File(object):
    def __init__(self, filename, size, starting_index=None):
        self.filename = filename
        self.size = size

BLOCK_SIZE = 4096 #4 KB
OFFSET = 4 # ??
class Strata(object):
    def __init__(self, num_dev):
        self.device = [Level] * num_dev
        self.device_size = [None] * num_dev
        #self.util_limit = [None] * num_dev
        self.num_dev = num_dev
        self.inode = Inode()
    
    def createDevice(self, level, dev_info, util_limit=None):
        self.device[level] = Cache.cachePolicy(dev_info)
        self.device_size[level] = Cache.cacheSize(dev_info)
        #self.util_limit[level] = util_limit
        # build level heirarchy
        if(level > 0):
            self.device[level-1].child = self.device[level]
    
    def read(self, file: File, offset : int, nbytes : int):
        inode_num = self.inode.get_inode(file.filename) # get the inode_num for this filename
        # if filename not found in the map, it creates a new entry in inode-> file and 
        # inode->address map . inode will point to empty list if new file
        node_list = self.inode.get_address_list(inode_num)
        size = file.size

        # suppose given start_b, end_b (last byte we write), and size_b (size of file in blocks)
        size_b = size // BLOCK_SIZE
        start_b = offset // BLOCK_SIZE
        end_b = ((nbytes - 1) // BLOCK_SIZE) + 1 #exclusive + 1

        for i in range(start_b, min(end_b, size_b)):
            access, dev_level = node_list[i] # -> current device, access addr
            if (dev_level == 1 ):
                pass
            else:
                self.device[dev_level].delete_access(access)
                dev_level = 1 #NVM
                access = Access()
                self.device[dev_level].push(access) # push file inum + block offset (file's perspective)
                self.inode.delete_block_addr(inode_num, i)
                self.inode.add_block_addr(inode_num, i, access, dev_level)


    def write(self, file: File, offset : int, nbytes : int):
        inode_num = self.inode.get_inode(file.filename)
        node_list = self.inode.get_address_list(inode_num)
        size = file.size

        # suppose given start_b, end_b (last byte we write), and size_b (size of file in blocks)
        size_b = size // BLOCK_SIZE
        start_b = offset // BLOCK_SIZE
        end_b = ((nbytes - 1) // BLOCK_SIZE) + 1 #exclusive + 1

        print(node_list)

        for i in range(size_b, start_b):
            dev_level = 1 #NVM
            access = Access()
            self.device[1].push(access, inode_num, i) #change inode mappings if migration(s) happen
            #self.inode.add_block_addr(inode_num, i, access, dev_level)

        for i in range(start_b, min(end_b, size_b)):
            access, dev_level = node_list[i] # -> current device, access addr
            if False:#(dev_level == 1 ):
                pass
            else:
                #self.device[dev_level].delete_access(access)
                dev_level = 1 #NVM
                access = Access()
                self.device[1].push(access, inode_num, i) # push file inum + block offset (file's perspective)
                #self.inode.delete_block_addr(inode_num, i)
                #self.inode.add_block_addr(inode_num, i, access, dev_level)

        for i in range(size_b, end_b):
            dev_level = 1 #NVM
            access = Access()
            self.device[1].push(access, inode_num, i) #change inode mappings if migration(s) happen
            #self.inode.add_block_addr(inode_num, i, access, dev_level)

        file.size = max(size, offset + nbytes)
        print(node_list)


class Inode(object):
    def __init__(self):
        self.file_inode = {} # filename -> inode_num
        self.block_addr = {} # inode_num -> [[access, dev_level]]  i.e. list of [access, dev_level]
        self.inode_counter = 0
    
    # given a filename, get inode_num from map
    def get_inode(self, filename):
        if filename not in self.file_inode: # new file, inode doesn't exist
            self.file_inode[filename] = self.inode_counter
            self.add_new_block_addr(self.inode_counter)
            self.inode_counter += 1
        return self.file_inode[filename]
    
    # given inode_num, get list of (access, dev_level) from map
    def get_address_list(self, inode_num):
        return self.block_addr[inode_num]
    
    # new file -> add empty list against inode_num
    def add_new_block_addr(self, inode_num):
        self.block_addr[inode_num] = [] #add a new empty entry to the inode - address map
    
    # delete this access element's entry from the inode_table for that file
    def delete_block_addr(self, inum, block_idx):
        baddr_list = self.block_addr[inum]

        if block_idx < len(baddr_list):
            baddr_list[block_idx] = (None, None)
            self.block_addr[inum] = baddr_list
        else:
            # error
            pass
    
    # new block added for the file. add its map to inode, using inode_num
    def add_block_addr(self, inum, block_idx, access, dev_level):
        #print("setblockaddr block=", block_idx, "in level", dev_level)
        elem = (access, dev_level)
        baddr_list = self.block_addr[inum]

        if block_idx < len(baddr_list):
            baddr_list[block_idx] = elem
        else:
            baddr_list.extend((None, None) for i in range(block_idx - len(baddr_list)))
            baddr_list.append(elem)

        self.block_addr[inum] = baddr_list


if __name__ == "__main__":
    strata = Strata(4)
    strata.createDevice(1, ["LRU", 1, 3, strata.inode]) # NVM lvlnum, size, inodes
    strata.createDevice(2, ["LRU", 2, 3, strata.inode], ) # SSD
    print(strata.device[1].__str__())
    print(strata.device[2].__str__())


    f1 = File("filefoo.txt",0)

    print("writing to strata!")
    strata.write(f1, 0, 50000)

    print(strata.device[1].__str__())
    print(strata.device[2].__str__())

    print("writing to strata!")
    strata.write(f1, 0, 50000)

    print(strata.device[1].__str__())
    print(strata.device[2].__str__())
