

from copy import deepcopy
from math import inf, log2
from random import choice, choices
from functools import partial
from collections import Counter, defaultdict
from collections.abc import MutableMapping



class InconsistentState(Exception):
    pass


class UnknowState:
    def __init__(self, *states, **weights):
        self.weights = Counter(states)
        self.weights.update(weights)
        self._on_update()

    @property
    def entropy(self):
        return self._entropy

    def _on_update(self):
        weights = self.weights.values()
        sum_of_weights = sum(weights)
        if sum_of_weights <= 0:
            raise InconsistentState()
        for state, weight in tuple(self.weights.items()):
            if weight > 0:
                self.weights[state] /= sum_of_weights
            else:
                del self.weights[state]
        self._entropy = -sum(w * log2(w) for w in weights)

    def constrain(self, constraint):
        for state in tuple(self.weights.keys()):
            if state in constraint:
                self.weights[state] *= constraint[state]
            else:
                del self.weights[state]
        self._on_update()

    def observe(self):
        states, weights = zip(*self.weights.items())
        return choices(states, weights)[0]

    def copy(self):
        return deepcopy(self)


class Rules:
    def __init__(self):
        self.constraints = defaultdict(
            lambda: defaultdict(Counter))
        self.neighbors = {}

    def get_neighbor(self, name, node):
        return self.neighbors[name](node)

    def get_constraints(self, node, state):
        for name, constraint in self.constraints[state].items():
            neighbor = self.get_neighbor(name, node)
            yield neighbor, constraint

    def update_constraints(self, graph):
        for node, state in graph.items():
            for name, callback in self.neighbors.items():
                neighbor = callback(node)
                if neighbor in graph:
                    self.constraints[state][name][graph[neighbor]] += 1

    def register_neighbors(self, *args, **kwargs):
        for callback in args:
            name = callback.__name__
            self.neighbors[name] = callback
        for name, callback in kwargs.items():
            self.neighbors[name] = callback

    def neighbor(self, name=None, callback=None):
        if callback is None:
            return partial(self.neighbor, name)
        if name is None:
            self.register_neighbors(callback)
        else:
            self.register_neighbors(**{name: callback})
        return callback

    def copy(self):
        return deepcopy(self)


class Wave(MutableMapping):
    def __init__(self, rules=None):
        if rules is None:
            rules = Rules()
        self.rules = rules
        self.nodes = {}

    def __getitem__(self, node):
        return self.nodes[node]

    def __setitem__(self, node, state):
        self.nodes[node] = state

    def __delitem__(self, node):
        del self.nodes[node]

    def __iter__(self):
        return iter(self.nodes)

    def __len__(self):
        return len(self.nodes)

    def get_next_nodes(self):
        min_entropy = inf
        min_nodes = []
        for node, state in self.nodes.items():
            if isinstance(state, UnknowState):
                entropy = state.entropy
                if entropy <= min_entropy:
                    if entropy < min_entropy:
                        min_entropy = entropy
                        min_nodes.clear()
                    min_nodes.append(node)
        return min_nodes

    def propagate(self, node, state):
        for neighbor, constraint in self.rules.get_constraints(node, state):
            neighbor_state = self.nodes.get(neighbor)
            if isinstance(neighbor_state, UnknowState):
                neighbor_state.constrain(constraint)
            elif neighbor_state not in constraint:
                raise InconsistentState

    def observe(self, node):
        state = self.nodes[node]
        if isinstance(state, UnknowState):
            state = state.observe()
            self.nodes[node] = state
            self.propagate(node, state)
        return state

    def collapse(self):
        nodes = self.get_next_nodes()
        while nodes:
            node = choice(nodes)
            state = self.observe(node)
            yield node, state
            nodes = self.get_next_nodes()

    def copy(self):
        return deepcopy(self)


def text2graph(text):
    graph = {}
    for row, line in enumerate(text.splitlines()):
        for column, char in enumerate(line):
            graph[row, column] = char
    return graph


