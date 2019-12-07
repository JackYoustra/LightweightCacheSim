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
        self.child.push(access)

    def flush(self):
        if self.child != None:
            self.child.flush()

    def __str__(self):
        return " of size {} got {} hits and {} misses".format(self.size, self.hits, self.misses)

class LRULevel(Level):
    def __init__(self, size):
        super().__init__(size)
        self.state = []
        self.counters = []
        pass

    def push(self, access):
        largest_counter_idx = -1
        largest_counter = -1
        for i in range(len(self.state)):
            if self.state[i] == access:
                self.hits += 1
                self.counters[i] = 0
                return
            else:
                if self.counters[i] > largest_counter:
                    largest_counter_idx = i
                    largest_counter = self.counters[i]
                self.counters[i] += 1
        if len(self.state) < self.size:
            # compulsory miss
            self.state.append(access)
            self.counters.append(0)
        else:
            # evict oldest
            self.state[largest_counter_idx] = access
            self.counters[largest_counter_idx] = 0
        misses += 1
        super().push(access)

    def __str__(self):
        return "LRU{}".format(super())

import heapq as hq
class PFOO_L(Level):
    def __init__(self, size):
        super().__init__(size)

    def push(self, access):

        super().push(access)


class FOO(Level):
    def __init__(self, size):
        super().__init__(size)


class RRIPLevel(Level):
    def __init__(self, size):
        super().__init__(size)


    
if __name__ == "__main__":
    import csv
    # csv: r/w? address / file ID (arbitrary), size, (offset?)



