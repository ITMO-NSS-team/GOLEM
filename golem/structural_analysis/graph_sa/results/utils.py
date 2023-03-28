from typing import Union, Tuple

from golem.core.dag.graph import Graph
from golem.core.dag.graph_node import GraphNode


def get_entity_from_str(graph: Graph, entity_str: str) -> Union[GraphNode, Tuple[GraphNode, GraphNode]]:
    """ Gets entity from entity str using graph. """
    if len(entity_str.split('_')) == 2:
        parent_node_idx, child_node_idx = entity_str.split('_')
        try:
            parent_node = graph.nodes[int(parent_node_idx)]
            child_node = graph.nodes[int(child_node_idx)]
        except IndexError:
            print('a')
        return parent_node, child_node
    else:
        return graph.nodes[int(entity_str)]
