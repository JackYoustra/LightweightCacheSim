# strata cache hiearchy:
# L0:  Read-only volatile
# L1:  NVMe
# L2:  SSD
# LLC: HDD

# Push + flush architecture

class Access(object):
    def __init__(self, address, size):
        self.address = address
        self.size = size

class Level(object):
    def __init__(self, size):
        self.child = None
        self.hits = 0
        self.misses = 0
        self.size = size
        pass

    def push(self, access):
        if self.child == None:
            return

class LRULevel(Level):
    def __init__(self, size):
        super().__init__(size)
        self.state = []
        self.replace_idx = 0
        pass

    def push(self, access):
        for i in range(len(self.state)):
            if self.state[i] == access:
                hits += 1
                return
        if len(self.state) < self.size:
            # compulsory miss
            self.state.append(access)
        else:
            # evict oldest
            self.state[self.replace_idx] = access
            self.replace_idx += 1
        misses += 1
        self.child.push(access)

class RRIPLevel(Level):
    def __init__(self, size):
        super().__init__(size)
    
if __name__ == "__main__":
    import csv
    # csv: r/w? address / file ID (arbitrary), size, (offset?)


