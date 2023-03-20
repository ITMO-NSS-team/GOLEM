from datetime import datetime, timedelta
from typing import Sequence, Type, Callable, Optional

import numpy as np
from scipy.stats import pearsonr

from examples.synthetic_graph_evolution.graph_search import graph_search_setup
from examples.synthetic_graph_evolution.generators import generate_labeled_graph, graph_kinds, postprocess_nx_graph
from examples.synthetic_graph_evolution.utils import draw_graphs_subplots
from golem.core.adapter.nx_adapter import BaseNetworkxAdapter
from golem.core.optimisers.genetic.gp_optimizer import EvoGraphOptimizer
from golem.core.optimisers.genetic.operators.base_mutations import MutationTypesEnum
from golem.metrics.graph_metrics import *


def run_adaptive_mutations(
        optimizer_setup: Callable = graph_search_setup,
        gnp_probs: Sequence[float] = (0.05, 0.1, 0.15, 0.3),
        graph_size: int = 50,
        trial_timeout: int = 15,
        trial_iterations: Optional[int] = 500,
        visualize: bool = False,
):
    node_types = ['x']
    stats_node_to_edge_ratios = []
    stats_action_probs = []

    for prob in gnp_probs:
        nx_graph = nx.gnp_random_graph(graph_size, prob, directed=True)
        target_graph = postprocess_nx_graph(nx_graph, node_labels=node_types)

        # One of the target statistics
        ne_ratio = target_graph.number_of_edges() / target_graph.number_of_nodes()
        stats_node_to_edge_ratios.append(ne_ratio)

        optimizer, objective = optimizer_setup(
            target_graph,
            optimizer_cls=EvoGraphOptimizer,
            node_types=node_types,
            timeout=timedelta(minutes=trial_timeout),
            num_iterations=trial_iterations,
        )
        found_graphs = optimizer.optimise(objective)
        found_graph = found_graphs[0] if isinstance(found_graphs, Sequence) else found_graphs
        history = optimizer.history

        # Get action probabilities
        agent = optimizer.mutation.agent
        action_probs = dict(zip(agent.actions, agent.get_action_probs()))
        # Mutation probabilities ratio is another target statistic
        action_prob_ratio = action_probs[MutationTypesEnum.single_edge] / action_probs[MutationTypesEnum.single_add]
        stats_action_probs.append(action_prob_ratio)

        print(f'N(edges)/N(nodes)= {ne_ratio:.3f}')
        print(f'P(add_edge)/P(add_node) = {action_prob_ratio:.3f}')
        if visualize:
            found_nx_graph = BaseNetworkxAdapter().restore(found_graph)
            draw_graphs_subplots(target_graph, found_nx_graph)
            history.show.fitness_line()

    # Compute correlation coefficient for given statistics
    result = pearsonr(stats_node_to_edge_ratios, stats_action_probs)
    print(f'N(edges)/N(nodes)= {np.round(stats_node_to_edge_ratios, 3)}')
    print(f'P(add_edge)/P(add_node) = {np.round(stats_action_probs, 3)}')
    print(result)

    return result


if __name__ == '__main__':
    run_adaptive_mutations(gnp_probs=np.arange(0.05, 0.35, 0.05))
