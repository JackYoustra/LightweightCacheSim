#!/usr/bin/env python3

# strata cache hiearchy:
# L0:  Read-only volatile
# L1:  NVMe
# L2:  SSD
# LLC: HDD

import itertools as it
import functools as ft

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

@ft.total_ordering
class Access(object):
    def __init__(self, address):
        self.__init__(address, 0)

    def __init__(self, address, size):
        self.address = address
        self.size = size

    def __str__(self):
        return "{} (size {})".format(self.address, self.size)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, Access):
            return self.address == other.address
        return False

    def __lt__(self, other):
        return self.address < other.address

    def __hash__(self):
        return self.address.__hash__()

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

import heapq as hq

class LRU(Level):
    def __init__(self, size):
        super().__init__(size)
        self.state = []
        self.inserted = {}
        self.quanta = 0
        self.current_occupation = 0

    def push(self, access):
        self.quanta += 1
        #print("Looking for {} in {}".format(access, self.state))
        if self.size < access.size:
            # don't even attempt to emplace
            self.misses += 1
            super().push(access)
        else:
            # do we exist in the heap?
            found = False
            for i in range(len(self.state)):
                if self.state[i][1] == access:
                    self.state[i][0] = self.quanta
                    hq.heapify(self.state)
                    found = True
                    self.hits += 1
                    break
            if not found:
                self.misses += 1
                while self.size - self.current_occupation < access.size:
                    assert(len(self.state) > 0)
                    oldquanta, oldaccess = hq.heappop(self.state)
                    self.current_occupation -= oldaccess.size
                    super().push(access)
                hq.heappush(self.state, [self.quanta, access])
                self.current_occupation += access.size


    def __str__(self):
        return "LRU{}".format(super())

class PFOO_L(Level):
    def __init__(self, size):
        super().__init__(size)
        self.heap = []

    def push(self, access):
        super().push(access)
        self.heap.append(access.size)
    
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
    def __init__(self, size):
        super().__init__(size)
        self.accesses = []
        self.result = None
        self.solved = None
        self.compulsory = 0

    def push(self, access):
        super().push(access)
        self.accesses.append(access)

    def flush(self):
        from ortools.graph import pywrapgraph
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

class HP_SRRIP(Level):
    def __init__(self, size, levels):
        super().__init__(size)
        self.state = []  # Tuple: RRIP prio level, Address
        self.levels = levels

    def __str__(self):
        for i in range(len(self.state)):
            print(self.state[i][0], self.state[i][1])

    # write to the queue
    def push(self, access):
        assert(access.size == 1)
        access = access.address
        # check for hit
        for i in range(len(self.state)):
            if self.state[i][1] == access:
                # hit, RRIP counter to zero
                self.hits += 1
                self.state[i][0] = self.levels
                return
        # Miss
        self.misses += 1
        if(len(self.state)) >= self.size:
            hq.heapify(self.state)
            oldaccess, oldprio = hq.heappop(self.state)
            # increment all by the amount we would've if we found oldprio by faithfully adhearing to algorithm
            for i in range(len(self.state)):
                self.state[i][0] -= oldprio
        hq.heappush(self.state, [1, access])
        super().push(access)

import random as rd
import numpy as np
def generate_pattern(pattern, start, end, length=None):
    assert(end - start > 0)
    if length is None:
        length = end - start
    if pattern == "sr" or pattern == "sw":
        assert(end - start >= length)
        begin = rd.randint(start, end - length)
        return [x for x in range(begin, begin + length)]
    if pattern == "rr" or pattern == "rw":
        return [rd.randint(start, end) for x in range(length)]
    if pattern == "zr" or pattern == "zw":
        a = 5. # shape
        samples = length
        assert(end - start >= length)
        begin = rd.randint(start, end - length)
        return [begin + length * x for x in np.random.power(a, samples)]
    assert(False)

def generate_access_pattern(pattern, start, end, length=None):
    return [Access(x, 1) for x in generate_pattern(pattern, start, end, length)]

import unittest as ut

# taken from https://arxiv.org/pdf/1711.03709.pdf
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
        list = [1, 2, 2, 1, 3, 4, 5, 6, 1, 2]
        accesses = [Access(x, 1) for x in list]
        rrip = HP_SRRIP(4, 3)
        for access in accesses:
            rrip.push(access)
        rrip.flush()
        self.assertEqual(rrip.hits, 4)
        self.assertEqual(rrip.misses, 6)

    def test_disparate(self):
        # Test LRU failing
        per_length = 2**12
        number_of_streams = 3
        lru = LRU(per_length)
        readers = [item for sublist in [generate_access_pattern("sr", 0, 2**32, per_length) for x in range(number_of_streams)] for item in sublist]
        for access in readers:
            lru.push(access)
        lru.flush()
        self.assertEqual(lru.hits, 0)
        self.assertEqual(lru.misses, per_length * number_of_streams)

    def test_non_disparate(self):
        # Test LRU succeeding
        per_length = 2**12
        number_of_streams = 3
        lru = LRU(per_length)
        readers = [item for sublist in [generate_access_pattern("sr", per_length, per_length * 2, per_length) for x in range(number_of_streams)] for item in sublist]
        for access in readers:
            lru.push(access)
        lru.flush()
        self.assertEqual(per_length * (number_of_streams - 1), lru.hits)
        self.assertEqual(per_length, lru.misses)


import argparse as ap
import csv

# sequential r/w in a good region, with a scan in a bad, and then sequential in a good
def scanning_pattern(scan_length, cacheable_length, cacheable_iterations, atype="sr"):
    return it.chain(
        it.repeat(generate_pattern(atype, 0, cacheable_length), cacheable_iterations),
        generate_pattern(atype, cacheable_length + 1, scan_length + cacheable_length),
        it.repeat(generate_pattern(atype, 0, cacheable_length), cacheable_iterations),
    )

from tqdm import tqdm
def run_tests(test_head):
    print("Synthesizing input...")
    stream = scanning_pattern(10**9, 10**9 // 2, 5)
    print("Running test...")
    for access in tqdm(stream):
        stream.push(access)

if __name__ == "__main__":
    parser = ap.ArgumentParser(description='Simulate a simple cache ')
    parser.add_argument('source', metavar='S', type=str, nargs=ap.REMAINDER)
    args = parser.parse_args()
    #if len(args.source) == 0:
        #print("No path, running tests instead")
        #ut.main()

    block_size = 4096

    nvm_blocks = 2 * (10**9) // block_size
    ssd_blocks = 280 * (10**9) // block_size

    nvm = LRU(nvm_blocks)
    ssd = LRU(ssd_blocks)
    nvm.child = ssd

    run_tests(nvm)