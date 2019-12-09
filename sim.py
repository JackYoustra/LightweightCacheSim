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

class Access(object):
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
                hq.heappush(self.state, [self.quanta, access])
                self.current_occupation += access.size

        super().push(access)

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
    def __init__(self, size, levels):
        super().__init__(size)
        self.state = []
        self.levels = levels

    def __str__(self):
        for i in range(len(self.state)):
            print(self.state[i][0], self.state[i][1], self.state[i][2].data)

    # write to the queue
    def push(self, access):
        # We only support single sizes atm
        assert(access.size == 1)
        if 
        super().push(access)

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
        rrip = RRIPLevel(3, 2)
        for access in test_accesses:
            rrip.push(access)
        rrip.flush()
        self.assertEqual(rrip.hits, 2)
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



