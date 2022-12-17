from datetime import datetime
from functools import partial
from itertools import product
from typing import Sequence

from examples.synthetic_graph_evolution.graph_metrics import *
from examples.synthetic_graph_evolution.utils import draw_graphs_subplots
from golem.core.adapter.nx_adapter import BaseNetworkxAdapter, nx_to_directed
from golem.core.dag.verification_rules import has_no_self_cycled_nodes
from golem.core.optimisers.optimization_parameters import GraphRequirements
from golem.core.optimisers.genetic.gp_optimizer import EvoGraphOptimizer
from golem.core.optimisers.genetic.gp_params import GPAlgorithmParameters
from golem.core.optimisers.genetic.operators.inheritance import GeneticSchemeTypesEnum
from golem.core.optimisers.genetic.operators.mutation import MutationTypesEnum
from golem.core.optimisers.graph import OptGraph, OptNode
from golem.core.optimisers.objective import Objective
from golem.core.optimisers.optimizer import GraphGenerationParams

NumNodes = int
DiGraphGenerator = Callable[[NumNodes], nx.DiGraph]

graph_generators: Dict[str, DiGraphGenerator] = {
    'star': lambda n: nx_to_directed(nx.star_graph(n)),
    'grid2d': lambda n: nx.grid_2d_graph(int(np.sqrt(n)), int(np.sqrt(n))),
    '2ring': lambda n: nx_to_directed(nx.circular_ladder_graph(n)),
    'hypercube': lambda n: nx_to_directed(nx.hypercube_graph(int(np.log2(n).round()))),
    'gnp': lambda n: nx.gnp_random_graph(n, p=0.15)
}


def get_all_quality_metrics(target_graph):
    quality_metrics = {
        'edit_distance': get_edit_dist_metric(target_graph),
        'matrix_edit_dist': partial(matrix_edit_dist, target_graph),
        'sp_adj': partial(spectral_dist, target_graph, kind='adjacency'),
        'sp_lapl': partial(spectral_dist, target_graph, kind='laplacian'),
        'sp_lapl_norm': partial(spectral_dist, target_graph, kind='laplacian_norm'),
        'graph_size': partial(size_diff, target_graph),
    }
    return quality_metrics


def run_experiments(graph_names: Sequence[str] = tuple(graph_generators.keys()),
                    graph_sizes: Sequence[int] = (30, 100, 300),
                    num_trials: int = 1,
                    trial_timeout: Optional[int] = None,
                    visualize: bool = False,
                    ):
    for graph_name, num_nodes in product(graph_names, graph_sizes):
        graph_generator = graph_generators[graph_name]
        experiment_id = f'Experiment [graph={graph_name} graph_size={num_nodes}]'
        trial_results = []
        for i in range(num_trials):
            start_time = datetime.now()
            print(f'\nTrial #{i} of {experiment_id} started at {start_time}')

            target_graph = graph_generator(num_nodes)
            found_graph, history, objective = run_trial(target_graph,
                                                        timeout=timedelta(minutes=trial_timeout))
            trial_results.extend(history.final_choices)
            found_nx_graph = BaseNetworkxAdapter().restore(found_graph)

            duration = datetime.now() - start_time
            print(f'Trial #{i} finished, spent time: {duration}')
            print('target graph stats: ', nxgraph_stats(target_graph))
            print('found graph stats: ', nxgraph_stats(found_nx_graph))
            if visualize:
                draw_graphs_subplots(target_graph, found_nx_graph)
                history.show.fitness_box()

        # Compute mean & std for metrics of trials
        ff = objective.format_fitness
        trial_metrics = np.array([ind.fitness.values for ind in trial_results])
        trial_metrics_mean = trial_metrics.mean(axis=0)
        trial_metrics_std = trial_metrics.std(axis=0)
        print(f'{experiment_id} finished with metrics:\n'
              f'mean={ff(trial_metrics_mean)}\n'
              f' std={ff(trial_metrics_std)}')
        return trial_metrics_mean, trial_metrics_std


def run_trial(target_graph: nx.DiGraph,
              timeout: Optional[timedelta] = None):
    # Setup parameters
    num_nodes = target_graph.number_of_nodes()
    requirements = GraphRequirements(
        max_arity=num_nodes,
        max_depth=num_nodes,
        early_stopping_timeout=5,
        early_stopping_iterations=1000,
        timeout=timeout,
        n_jobs=-1,
    )
    gp_params = GPAlgorithmParameters(
        multi_objective=True,
        genetic_scheme_type=GeneticSchemeTypesEnum.generational,
        mutation_types=[
            MutationTypesEnum.simple,
            MutationTypesEnum.single_add,
            MutationTypesEnum.single_edge,
            MutationTypesEnum.single_drop,
        ]
    )
    graph_gen_params = GraphGenerationParams(
        adapter=BaseNetworkxAdapter(),
        rules_for_constraint=[has_no_self_cycled_nodes],
    )

    # Setup objective that measures some graph-theoretic similarity measure
    objective = Objective(
        quality_metrics={
            'sp_adj': partial(spectral_dist, target_graph, kind='adjacency'),
            'sp_lapl': partial(spectral_dist, target_graph, kind='laplacian'),
        },
        complexity_metrics={
            'graph_size': partial(size_diff, target_graph),
        },
        is_multi_objective=True
    )
    # Generate simple initial population with single-node graphs
    initial_graphs = [OptGraph(OptNode(f'Node{i}')) for i in range(gp_params.pop_size)]

    # Run the optimizer
    optimiser = EvoGraphOptimizer(objective, initial_graphs, requirements, graph_gen_params, gp_params)
    found_graphs = optimiser.optimise(objective)

    return found_graphs[0], optimiser.history, objective


if __name__ == '__main__':
    run_experiments(graph_names=['grid2d', 'gnp'],
                    graph_sizes=(30, 100,),
                    num_trials=2,
                    trial_timeout=1,
                    visualize=True)
