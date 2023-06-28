from copy import copy, deepcopy
from random import seed

import numpy as np
import pytest

from golem.core.dag.graph import Graph, ReconnectType
from golem.core.dag.graph_delegate import GraphDelegate
from golem.core.dag.linked_graph import LinkedGraph
from golem.core.dag.linked_graph_node import LinkedGraphNode
from test.unit.utils import find_same_node, nodes_same

seed(1)
np.random.seed(1)

GraphImpl = LinkedGraph
GraphNode = LinkedGraphNode


def get_graph() -> GraphImpl:
    third_level_one = GraphNode('l3_n1')

    second_level_one = GraphNode('l2_n1', nodes_from=[third_level_one])
    second_level_two = GraphNode('l2_n2')

    second_level_three = GraphNode('l2_n3', nodes_from=[second_level_two])

    first_level_one = GraphNode('l1_n1', nodes_from=[second_level_one, second_level_two, second_level_three])

    root = GraphNode('l0_n1', nodes_from=[first_level_one])
    graph = GraphImpl(root)
    return graph


def test_graph_id():
    right_id = '((/n_n1;)/n_n2;;(/n_n1;)/n_n3;)/n_n4'
    first = GraphNode(content='n1')
    second = GraphNode(content='n2', nodes_from=[first])
    third = GraphNode(content='n3', nodes_from=[first])
    final = GraphNode(content='n4', nodes_from=[second, third])

    assert final.descriptive_id == right_id


def test_graph_str():
    # given
    first = GraphNode(content='n1')
    second = GraphNode(content='n2')
    third = GraphNode(content='n3')
    final = GraphNode(content='n4',
                      nodes_from=[first, second, third])
    graph = GraphImpl(final)

    expected_graph_description = "{'depth': 2, 'length': 4, 'nodes': [n4, n1, n2, n3]}"

    # when
    actual_graph_description = str(graph)

    # then
    assert actual_graph_description == expected_graph_description


def test_graph_repr():
    first = GraphNode(content='n1')
    second = GraphNode(content='n2')
    third = GraphNode(content='n3')
    final = GraphNode(content='n4',
                      nodes_from=[first, second, third])
    graph = GraphImpl(final)

    expected_graph_description = "{'depth': 2, 'length': 4, 'nodes': [n4, n1, n2, n3]}"

    assert repr(graph) == expected_graph_description


def test_delete_primary_node():
    # given
    first = GraphNode(content='n1')
    second = GraphNode(content='n2')
    third = GraphNode(content='n3', nodes_from=[first])
    final = GraphNode(content='n4', nodes_from=[second, third])
    graph = GraphImpl(final)

    # when
    graph.delete_node(first)

    new_primary_node = [node for node in graph.nodes if node.content['name'] == 'n2'][0]

    # then
    assert graph.length == 3
    assert isinstance(new_primary_node, GraphNode)


def test_delete_root_node():
    first = GraphNode(content='n1')
    second = GraphNode(content='n2')
    third = GraphNode(content='n3', nodes_from=[first])
    final = GraphNode(content='n4', nodes_from=[second, third])
    graph = GraphImpl(final)

    assert graph.root_node == final
    assert graph.depth == 3

    graph.delete_node(final)

    assert graph.root_nodes() == [second, third]
    assert graph.depth == 2

    graph.delete_node(second)

    assert graph.root_node == third
    assert graph.depth == 2


def test_delete_intermediate_node():
    first = GraphNode(content='n1')
    second = GraphNode(content='n2')
    third = GraphNode(content='n3', nodes_from=[first])
    final = GraphNode(content='n4', nodes_from=[second, third])
    graph = GraphImpl(final)

    assert third in final.nodes_from
    assert first not in final.nodes_from
    assert graph.node_children(third) == [final]
    assert graph.depth == 3

    graph.delete_node(third)

    # the only child node (final) is rewired to parent of remove node (first)
    assert third not in final.nodes_from
    assert first in final.nodes_from
    assert not graph.node_children(third)
    assert graph.depth == 2


def test_delete_leave_cycle():
    first = GraphNode(content='n1')
    second = GraphNode(content='n2', nodes_from=[first])
    third = GraphNode(content='n3', nodes_from=[second])
    final = GraphNode(content='n4', nodes_from=[third])
    graph = GraphImpl(final)
    graph.connect_nodes(final, first)

    assert len(graph.get_edges()) == 4

    graph.delete_node(third, reconnect=ReconnectType.single)

    assert third not in graph.nodes
    assert len(graph.get_edges()) == 3
    assert (second, final) in graph.get_edges()


def test_delete_break_cycle():
    first = GraphNode(content='n1')
    second = GraphNode(content='n2', nodes_from=[first])
    third = GraphNode(content='n3', nodes_from=[second])
    final = GraphNode(content='n4', nodes_from=[third])
    graph = GraphImpl(final)
    graph.connect_nodes(final, first)

    assert len(graph.get_edges()) == 4

    graph.delete_node(third, reconnect=ReconnectType.none)

    assert third not in graph.nodes
    assert len(graph.get_edges()) == 2
    assert not final.nodes_from


def test_delete_node_with_duplicated_edges():
    ok_primary_node = GraphNode('n1')
    bad_primary_node = GraphNode('n2')
    nodes_from_with_duplicate = [bad_primary_node, ok_primary_node, bad_primary_node]
    graph = GraphImpl([GraphNode('n3', nodes_from=nodes_from_with_duplicate)])

    to_delete_node = find_same_node(graph.nodes, bad_primary_node)
    graph.delete_node(to_delete_node)

    assert not find_same_node(graph.nodes, bad_primary_node)
    assert not find_same_node(graph.root_node.nodes_from, bad_primary_node)


def test_delete_subtree_with_several_edges_near():
    ok_primary_node = GraphNode('n1')
    bad_primary_node = GraphNode('n2a')
    bad_secondary_node = GraphNode('n2b', nodes_from=[bad_primary_node])
    root_node = GraphNode('n3', nodes_from=[bad_secondary_node, ok_primary_node, bad_primary_node])
    graph = GraphImpl(root_node)

    to_delete_node = find_same_node(graph.nodes, bad_secondary_node)
    graph.delete_subtree(to_delete_node)

    assert not find_same_node(graph.nodes, bad_secondary_node)
    assert not find_same_node(graph.nodes, bad_primary_node)
    subtree_child = graph.root_node
    assert not find_same_node(subtree_child.nodes_from, bad_secondary_node)
    assert not find_same_node(subtree_child.nodes_from, bad_primary_node)


def test_delete_subtree_with_several_edges_distant():
    ok_primary_node = GraphNode('n1')
    bad_primary_node = GraphNode('n2a')
    bad_secondary_node = GraphNode('n2b', nodes_from=[bad_primary_node])
    subtree_child = GraphNode('n3', nodes_from=[bad_secondary_node, ok_primary_node])
    root_node = GraphNode('n4', nodes_from=[subtree_child, bad_primary_node])
    graph = GraphImpl(root_node)

    to_delete_node = find_same_node(graph.nodes, bad_secondary_node)
    graph.delete_subtree(to_delete_node)

    assert not find_same_node(graph.nodes, bad_secondary_node)
    assert not find_same_node(graph.nodes, bad_primary_node)
    subtree_child = find_same_node(graph.nodes, subtree_child)
    assert find_same_node(subtree_child.nodes_from, ok_primary_node)
    assert not find_same_node(subtree_child.nodes_from, bad_secondary_node)
    # most important check: that distant edge from uder subtree is pruned
    assert not find_same_node(graph.root_node.nodes_from, bad_primary_node)


def test_delete_subtree_with_duplicated_edges():
    ok_primary_node = GraphNode('n1')
    bad_primary_node = GraphNode('n2a')
    bad_secondary_node = GraphNode('n2b', nodes_from=[bad_primary_node])
    nodes_from_with_duplicate = [bad_secondary_node, ok_primary_node, bad_secondary_node, bad_primary_node]
    graph = GraphImpl([GraphNode('n3', nodes_from=nodes_from_with_duplicate)])

    to_delete_node = find_same_node(graph.nodes, bad_secondary_node)
    graph.delete_subtree(to_delete_node)

    assert not find_same_node(graph.nodes, bad_secondary_node)
    assert not find_same_node(graph.nodes, bad_primary_node)
    assert not find_same_node(graph.root_node.nodes_from, bad_secondary_node)
    assert not find_same_node(graph.root_node.nodes_from, bad_primary_node)


def test_update_node_without_predecessors():
    primary_node_1 = GraphNode('l1n1')
    primary_node_2 = GraphNode('l1n2')

    nodes_from = [primary_node_1, primary_node_2]
    old_secondary_node_1 = GraphNode('l2n1', nodes_from=nodes_from)

    final_node = GraphNode('l3n1', nodes_from=[old_secondary_node_1])
    graph = GraphImpl([final_node])

    new_secondary_node = GraphNode('l2new')
    graph.update_node(old_secondary_node_1, new_secondary_node)

    new_node = find_same_node(graph.nodes, new_secondary_node)
    assert new_node is not None
    assert not find_same_node(graph.nodes, old_secondary_node_1)
    assert find_same_node(graph.root_node.nodes_from, new_secondary_node), "node children were not updated"
    assert nodes_same(old_secondary_node_1.nodes_from, new_node.nodes_from), "node parents were not updated"


def test_update_node_with_duplicated_edges():
    ok_primary_node = GraphNode('n1')
    bad_primary_node = GraphNode('n2')
    nodes_from_with_duplicate = [bad_primary_node, ok_primary_node, bad_primary_node]
    graph = GraphImpl([GraphNode('n3', nodes_from=nodes_from_with_duplicate)])

    updated_node = GraphNode('n2b')
    to_update_node = find_same_node(graph.nodes, bad_primary_node)
    graph.update_node(to_update_node, updated_node)

    assert not find_same_node(graph.nodes, bad_primary_node)
    assert not find_same_node(graph.root_node.nodes_from, bad_primary_node)
    assert find_same_node(graph.nodes, updated_node)
    assert find_same_node(graph.root_node.nodes_from, updated_node)


def test_update_subtree_with_duplicated_edges():
    ok_primary_node = GraphNode('n1')
    bad_primary_node = GraphNode('n2a')
    bad_secondary_node = GraphNode('n2b', nodes_from=[bad_primary_node])
    nodes_from_with_duplicate = [bad_secondary_node, ok_primary_node, bad_secondary_node, bad_primary_node]
    graph = GraphImpl([GraphNode('n3', nodes_from=nodes_from_with_duplicate)])

    updated_node = GraphNode('n4b', nodes_from=[GraphNode('n4a')])
    to_update_node = find_same_node(graph.nodes, bad_secondary_node)
    graph.update_subtree(to_update_node, updated_node)

    assert not find_same_node(graph.nodes, bad_secondary_node)
    assert not find_same_node(graph.nodes, bad_primary_node)
    assert not find_same_node(graph.root_node.nodes_from, bad_secondary_node)
    assert not find_same_node(graph.root_node.nodes_from, bad_primary_node)
    assert find_same_node(graph.nodes, updated_node)
    assert find_same_node(graph.root_node.nodes_from, updated_node)


@pytest.mark.parametrize('graph', [GraphImpl(GraphNode(content='n1')),
                                   GraphDelegate(GraphNode(content='n1'), delegate_cls=GraphImpl)])
def test_graph_copy(graph: Graph):
    graph_copy = copy(graph)

    assert id(graph) != id(graph_copy)
    assert graph.root_node.descriptive_id == graph_copy.root_node.descriptive_id

    _modify_graph_copy(graph_copy)

    assert graph.root_node.descriptive_id == graph_copy.root_node.descriptive_id


@pytest.mark.parametrize('graph', [GraphImpl(GraphNode(content='n1')),
                                   GraphDelegate(GraphNode(content='n1'), delegate_cls=GraphImpl)])
def test_graph_deepcopy(graph: Graph):
    graph_copy = deepcopy(graph)

    assert id(graph) != id(graph_copy)
    assert graph.root_node.descriptive_id == graph_copy.root_node.descriptive_id

    _modify_graph_copy(graph_copy)

    assert graph.root_node.descriptive_id != graph_copy.root_node.descriptive_id


def _modify_graph_copy(graph: Graph):
    graph.root_node.content['name'] = 'n2'


def test_reset_descriptive_id():
    """ Checks if descriptive_id is set to None after any changes in graph. """
    def perform_test_cycle_asserts(final_descriptive_id: str, initial_descriptive_id: str, is_equal: bool = False):
        assert initial_descriptive_id is not None
        if is_equal:
            assert final_descriptive_id == initial_descriptive_id
        else:
            assert final_descriptive_id != initial_descriptive_id

    graph = get_graph()

    initial_descriptive_id = graph.descriptive_id
    assert initial_descriptive_id is not None

    # Create, Update, Delete methods

    graph.delete_node(graph.nodes[3])
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id, initial_descriptive_id=initial_descriptive_id)

    initial_descriptive_id = graph.descriptive_id
    graph.disconnect_nodes(graph.nodes[3], graph.nodes[4])
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id, initial_descriptive_id=initial_descriptive_id)

    initial_descriptive_id = graph.descriptive_id
    graph.connect_nodes(graph.nodes[3], graph.nodes[4])
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id, initial_descriptive_id=initial_descriptive_id)

    initial_descriptive_id = graph.descriptive_id
    graph.update_node(graph.nodes[0], LinkedGraphNode('new'))
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id, initial_descriptive_id=initial_descriptive_id)

    initial_descriptive_id = graph.descriptive_id
    graph.update_subtree(graph.nodes[2], LinkedGraphNode('new_1'))
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id, initial_descriptive_id=initial_descriptive_id)

    initial_descriptive_id = graph.descriptive_id
    graph.add_node(LinkedGraphNode('new_2'))
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id, initial_descriptive_id=initial_descriptive_id)

    initial_descriptive_id = graph.descriptive_id
    graph.delete_subtree(graph.nodes[2])
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id, initial_descriptive_id=initial_descriptive_id)

    initial_descriptive_id = graph.descriptive_id
    graph.actualise_old_node_children(graph.nodes[2], LinkedGraphNode('new_3'))
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id, initial_descriptive_id=initial_descriptive_id)

    initial_descriptive_id = graph.descriptive_id
    graph.nodes = [LinkedGraphNode('new_4')]
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id, initial_descriptive_id=initial_descriptive_id)

    # Read methods

    graph = get_graph()

    initial_descriptive_id = graph.descriptive_id
    graph.node_children(graph.nodes[2])
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id,
                               initial_descriptive_id=initial_descriptive_id,
                               is_equal=True)

    initial_descriptive_id = graph.descriptive_id
    graph.sort_nodes()
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id,
                               initial_descriptive_id=initial_descriptive_id,
                               is_equal=True)

    initial_descriptive_id = graph.descriptive_id
    graph.get_edges()
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id,
                               initial_descriptive_id=initial_descriptive_id,
                               is_equal=True)

    initial_descriptive_id = graph.descriptive_id
    graph.get_node_by_uid(graph.nodes[1].uid)
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id,
                               initial_descriptive_id=initial_descriptive_id,
                               is_equal=True)

    initial_descriptive_id = graph.descriptive_id
    graph.root_nodes()
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id,
                               initial_descriptive_id=initial_descriptive_id,
                               is_equal=True)

    initial_descriptive_id = graph.descriptive_id
    _ = graph.graph_description
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id,
                               initial_descriptive_id=initial_descriptive_id,
                               is_equal=True)

    initial_descriptive_id = graph.descriptive_id
    _ = graph.nodes
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id,
                               initial_descriptive_id=initial_descriptive_id,
                               is_equal=True)

    initial_descriptive_id = graph.descriptive_id
    _ = graph.descriptive_id
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id,
                               initial_descriptive_id=initial_descriptive_id,
                               is_equal=True)

    initial_descriptive_id = graph.descriptive_id
    _ = graph.depth
    perform_test_cycle_asserts(final_descriptive_id=graph.descriptive_id,
                               initial_descriptive_id=initial_descriptive_id,
                               is_equal=True)
