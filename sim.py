#!/usr/bin/env python3

# strata cache hiearchy:
# L0:  Read-only volatile
# L1:  NVMe
# L2:  SSD
# LLC: HDD

from ortools.graph import pywrapgraph

def result_to_str(flower, result):
    if result == flower.NOT_SOLVED:
        return "NOT_SOLVED"
    if result == flower.OPTIMAL:
        return "OPTIMAL"
    if result == flower.FEASIBLE:
        return "FEASIBLE"
    if result == flower.INFEASIBLE:
        return "UNBALANCED"
    if result == flower.BAD_RESULT:
        return "BAD_RESULT"
    if result == flower.BAD_COST_RANGE:
        return "BAD_COST_RANGE"
    return str(result)


# Push + flush architecture
access_counter = 0
class Access:
    def __init__(self, address=None, size=0):
        if address is None:
            global access_counter
            self.address = access_counter
            access_counter += 1
        else:
            self.address = address

        # self.size = size # remove this since each access is of size 1 block
    def __str__(self):
        return "{}".format(self.address)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, Access):
            return self.address == other.address
        return False

    def __hash__(self):
        return self.address.__hash__()

class Level(object):
    def __init__(self, lvlnum, size, inodes):
        self.child = None
        self.hits = 0
        self.misses = 0
        self.size = size
        self.lvlnum = lvlnum
        self.inodes = inodes
        pass

    def push(self, access, inum=-1, blocknum=-1):
        if self.child == None:
            self.inodes.add_block_addr(inum, blocknum, access, self.lvlnum + 1)
            return None
        #print("pushing access to child!" + self.child.__str__())
        return self.child.push(access, inum, blocknum)

    def deleteCopies(self, access):
        if self.child == None:
            return None
        #print("deleting copies in child!" + self.child.__str__())
        self.child.deleteCopies(access)

    def flush(self):
        if self.child != None:
            self.child.flush()

    def __str__(self):
        return " of size {} got {} hits and {} misses".format(self.size, self.hits, self.misses)

    def delete_access(self, access):
        raise NotImplementedError

import heapq as hq

class LRU(Level):
    def __init__(self, lvlnum, size, inodes):
        super().__init__(lvlnum, size, inodes)
        self.state = []
        self.inserted = {}
        self.quanta = 0
        self.current_occupation = 0

    # from file system perspective, always call lvl 1 push
    def push(self, access, inum=-1, blocknum=-1):
        self.quanta += 1
        #print("Looking for {} in {}".format(access, self.state))
        if self.size < 1:
            # don't even attempt to emplace
            self.misses += 1
            self.inodes.add_block_addr(inum, blocknum, access, self.lvlnum)
        else:
            # do we exist in the heap?
            found = False
            #print(self.state, access.__str__())
            for i in range(len(self.state)):
                if self.state[i][1] == access:
                    self.state[i][0] = self.quanta
                    hq.heapify(self.state)
                    # hit does not change inode table
                    found = True
                    self.hits += 1
                    break
            
            if not found:
                #print("not found access=", access, "in level", self.lvlnum)
                self.misses += 1
                super().deleteCopies(access)

                while self.size - self.current_occupation < 1:
                    # miss may change inode table
                    assert(len(self.state) > 0)
                    oldquanta, oldaccess, oldinum, oldblocknum = hq.heappop(self.state)
                    self.current_occupation -= 1
                    # eviction has stateful changes (cascading to deletes + adds)
                    #print("evicting block=", oldblocknum)
                    self.inodes.delete_block_addr(oldinum, oldblocknum)
                    super().push(oldaccess, oldinum, oldblocknum)

                self.inodes.add_block_addr(inum, blocknum, access, self.lvlnum)
                hq.heappush(self.state, [self.quanta, access, inum, blocknum])
                self.current_occupation += 1



    def deleteCopies(self, access):
        for i in range(len(self.state)):
            if self.state[i][1] == access:
                self.state.remove(i)
                self.current_occupation -= 1

        hq.heapify(self.state)

    def __str__(self):
        return "LRU{}".format(super().__str__())


class PFOO_L(Level):
    def __init__(self, lvlnum, size, inodes):
        super().__init__(lvlnum, size, inodes)
        self.heap = []

    def push(self, access, inum=-1, blocknum=-1):
        super().push(access)
        self.heap.append(1)
    
    def flush(self):
        super().flush()
        remaining = self.size
        self.heap.sort()
        for i in range(len(self.heap)): 
            elem = self.heap[i]
            if elem > remaining:
                misses += len(self.heap) - i
                break
            else:
                remaining -= elem
                hits += 1

    def __str__(self):
        return "PFOO_L{}".format(super())

scaling = 2048
class FOO(Level):
    def __init__(self, lvlnum, size, inodes):
        super().__init__(lvlnum, size, inodes)
        self.accesses = []
        self.result = None
        self.solved = None
        self.compulsory = 0

    def push(self, access, inum=-1, blocknum=-1):
        super().push(access)
        self.accesses.append(access)

    def flush(self):
        super().flush()
        last_access_dict = {}
        # maintain edge list. First, we're going to do the inner edges
        start_nodes = [x for x in range(len(self.accesses))]
        end_nodes = [x + 1 for x in range(len(self.accesses))]
        capacities = [self.size for x in range(len(self.accesses))]
        unit_costs = [0 for x in range(len(self.accesses))]
        supplies = [0 for x in range(len(self.accesses))]

        # now for the outer edges
        for i in range(len(self.accesses)):
            access = self.accesses[i]
            # if found, create the outer edge and update the last access
            if access in last_access_dict:
                start_nodes.append(last_access_dict[access]) # we're going to want to change this to some unique ID 
                end_nodes.append(i)
                capacities.append(access.size)
                unit_costs.append(int(scaling / access.size))
            else:
                # create source, compulsory miss
                self.compulsory += 1
                supplies[i] = access.size

            # Update last access 
            last_access_dict[access] = i

        # now for sinks for things that haven't been re-referenced to make non-reuse feasible
        for access, index in last_access_dict.items():
            #start_nodes.append(index)
            #end_nodes.append(len(self.accesses))
            #capacities.append(access.size)
            #unit_costs.append(0)
            supplies[index] -= access.size

        # Instantiate a SimpleMinCostFlow solver.
        min_cost_flow = pywrapgraph.SimpleMinCostFlow()

        # Add each arc.
        for i in range(0, len(start_nodes)):
            min_cost_flow.AddArcWithCapacityAndUnitCost(start_nodes[i], end_nodes[i],
                                                        capacities[i], unit_costs[i])

        # Add node supplies.
        for i in range(0, len(supplies)):
            min_cost_flow.SetNodeSupply(i, supplies[i])

        self.result = min_cost_flow.Solve()
        self.solved = min_cost_flow
        self.misses += self.compulsory
        for i in range(min_cost_flow.NumArcs()):
            if min_cost_flow.Flow(i) * min_cost_flow.UnitCost(i) / scaling > 0:
                self.misses += 1

        self.hits = len(self.accesses) - self.misses

    def __str__(self):
        if self.result == self.solved.INFEASIBLE:
            return "Graph was infeasible"
        return "Status: {}. FOO has {} misses implied by aggregate cost (lower bound), while worst-case (miss any taken tail) it has {} misses out of a total of {} accesses".format(result_to_str(self.solved, self.result), self.compulsory + self.solved.OptimalCost() / scaling, self.misses, len(self.accesses))

class SRRIPLevel(Level):
    def __init__(self, lvlnum, size, inodes, levels):
        super().__init__(lvlnum, size, inodes)
        self.state = []
        self.bits = levels
        self.order = 0

    def __str__(self):
        s = "RRIP cache with size {} and bits {}".format(self.size, self.bits)
        s += super().__str__()
        return s
    
    def print_state(self):
        for i in range(len(self.state)):
            print(self.state[i][0], self.state[i][1], self.state[i][2])
        
    def get_current_util(self):
        return len(self.state)

    # access the element in cache
    def push(self, access, inum=-1, blocknum=-1):
        for i in range (len(self.state)):
            if self.state[i][2] == access:
                # cache hit
                self.hits += 1
                element = self.state.pop(i)
                self.increment(element[2], element[0])
                return None
        # cache miss
        self.misses += 1
        if(len(self.state)) >= self.size: #cache is full. Go to next level
            elem = self.evict()
            # opcode = [("DEL", elem, dev_level)]
            # opcode.append(super().push(elem, dev_level+1))
            super().push(elem)
        priority = 0
        hq.heappush(self.state, [priority, self.order, access])
        # opcode.append(["ADD", access, dev_level])
        self.order += 1
        return 

    def deleteCopies(self, access):
        for i in range(len(self.state)):
            if self.state[i][2] == access:
                self.state.remove(i)

        hq.heapify(self.state)

    def increment(self, access, priority):
        if priority < (2**self.bits) - 1:
            priority += 1
        # else, already the highest priority
        hq.heappush(self.state, [priority, self.order, access])
        self.order += 1

    # evict from queue if queue is full
    def evict(self):
        elem = hq.heappop(self.state)
        return elem
    
    def delete_access(self, access):
        self.state.remove(access)
        return

import unittest as ut

# taken from https://arxiv.org/pdf/1711.03709.pdf
# change test samples to remove size from Access objects
test_samples = (
        (0xA, 3),
        (0xB, 1),
        (0xC, 1),
        (0xB, 1),
        (0xD, 2),
        (0xA, 3),
        (0xC, 1),
        (0xD, 2),
        (0xA, 3),
        (0xB, 1),
        (0xB, 1),
        (0xA, 3),
)

test_accesses = [Access(addr, size) for addr, size in test_samples]
class TestSamples(ut.TestCase):
    def test_lru(self):
        # LRU test
        lru = LRU(2)
        for access in test_accesses:
            lru.push(access)
        lru.flush()
        self.assertEqual(lru.hits, 2)
        self.assertEqual(lru.misses, 10)
        
    def test_foo(self):
        foo = FOO(2)
        for access in test_accesses:
            foo.push(access)
        foo.flush()
        self.assertEqual(foo.hits, 4)
        self.assertEqual(foo.misses, 8)

    def test_rrip(self):
        rrip = RRIPLevel(3, 2) #size, number of bits
        for access in test_accesses:
            rrip.push(access)
        rrip.flush()
        self.assertEqual(rrip.hits, 4)
        self.assertEqual(rrip.misses, 8)


import argparse as ap
import csv

if __name__ == "__main__":
    parser = ap.ArgumentParser(description='Simulate a simple cache ')
    parser.add_argument('source', metavar='S', type=str, nargs=ap.REMAINDER)
    args = parser.parse_args()
    if len(args.source) == 0:
        print("No path, running tests instead")
        ut.main()
    else:
        source = args.source
        print("Simulating from {}".format(source))
        # csv: r/w? address / file ID (arbitrary), size, (offset?)
        # we're just going to ship posix calls



