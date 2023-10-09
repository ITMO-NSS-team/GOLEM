import os
from abc import ABC
from datetime import timedelta, datetime
from io import StringIO
from itertools import product
from pathlib import Path
from typing import Optional, Type, Sequence, List, Callable, Union, Tuple

import numpy as np
import pandas as pd
from networkx import DiGraph

from examples.synthetic_graph_evolution.generators import generate_labeled_graph
from examples.synthetic_graph_evolution.utils import draw_graphs_subplots
from golem.core.adapter.nx_adapter import BaseNetworkxAdapter
from golem.core.dag.graph import Graph
from golem.core.optimisers.genetic.gp_optimizer import EvoGraphOptimizer
from golem.core.optimisers.objective import Objective
from golem.core.optimisers.opt_history_objects.opt_history import OptHistory
from golem.core.optimisers.optimizer import GraphOptimizer
from golem.metrics.graph_metrics import nxgraph_stats


class ExperimentLauncher(ABC):
    """ Class that allows to easily set up experiments and save results in format
    required for ExperimentAnalyzer. """
    def __init__(self, graph_names: List[str], graph_sizes: List[int], path_to_save: str,
                 is_save_visualizations: bool = True, optimizer_cls: Type[GraphOptimizer] = EvoGraphOptimizer,
                 node_types: Optional[Sequence[str]] = None, num_trials: int = 10, trial_timeout: Optional[int] = None,
                 trial_iterations: Optional[int] = None):
        self.graph_names = graph_names
        self.graph_sizes = graph_sizes
        self.optimizer_cls = optimizer_cls
        self.node_types = node_types
        self.num_trials = num_trials
        self.trial_timeout = trial_timeout
        self.trial_iterations = trial_iterations
        self.path_to_save = path_to_save
        self.is_save_visualizations = is_save_visualizations

    def launch(self, optimizer_setup: Callable):
        """
        Launches experiments for product of all graph names and graph sizes for specified number of trials.
        """
        log = StringIO()
        if not self.node_types:
            node_types = ['X']
        for graph_name, num_nodes in product(self.graph_names, self.graph_sizes):
            experiment_id = f'Experiment [graph={graph_name} graph_size={num_nodes}]'
            file_name = f'{self.optimizer_cls.__name__[:-9]}_{graph_name}_n{num_nodes}_iter{self.trial_iterations}'
            trial_results = []
            for i in range(self.num_trials):
                setup_name = optimizer_setup.__name__
                cur_path_to_save = os.path.join(self.path_to_save, setup_name, f'{graph_name}_{num_nodes}', str(i))
                os.makedirs(cur_path_to_save, exist_ok=True)
                start_time = datetime.now()
                print(f'\nTrial #{i} of {experiment_id} started at {start_time}', file=log)

                optimizer, objective, target_graph = self._launch_experiment(graph_name=graph_name,
                                                                             num_nodes=num_nodes,
                                                                             node_types=node_types,
                                                                             optimizer_setup=optimizer_setup)

                found_graphs = optimizer.optimise(objective)
                found_graph = found_graphs[0] if isinstance(found_graphs, Sequence) else found_graphs
                history = optimizer.history

                trial_results.extend(history.final_choices)
                found_nx_graph = BaseNetworkxAdapter().restore(found_graph)

                duration = datetime.now() - start_time
                print(f'Trial #{i} finished, spent time: {duration}', file=log)
                print('target graph stats: ', nxgraph_stats(target_graph), file=log)
                print('found graph stats: ', nxgraph_stats(found_nx_graph), file=log)

                self._save_experiment_results(path_to_save=cur_path_to_save, optimizer=optimizer)

                if self.is_save_visualizations:
                    self._save_visualizations(target_graph=target_graph, found_nx_graph=found_nx_graph,
                                              history=history, setup_name=setup_name, path_to_save=cur_path_to_save)

            # Compute mean & std for metrics of trials
            ff = objective.format_fitness
            trial_metrics = np.array([ind.fitness.values for ind in trial_results])
            trial_metrics_mean = trial_metrics.mean(axis=0)
            trial_metrics_std = trial_metrics.std(axis=0)
            print(f'{experiment_id} finished with metrics:\n'
                  f'mean={ff(trial_metrics_mean)}\n'
                  f'std={ff(trial_metrics_std)}',
                  file=log)
            print(log.getvalue())

    def _launch_experiment(self, graph_name: str, num_nodes: int, node_types: List[str], optimizer_setup: Callable):
        """ Launches one experiment with specified params. """
        raise NotImplementedError()

    @staticmethod
    def _save_experiment_results(path_to_save: str, optimizer):
        """ Saves experiment result as it is required in ExperimentAnalyzer. """
        os.makedirs(path_to_save, exist_ok=True)

        # save metrics
        obj_names = optimizer.objective.metric_names
        fitness = dict.fromkeys(obj_names)
        for ind in optimizer.best_individuals:
            for j, metric in enumerate(obj_names):
                if not fitness[metric]:
                    fitness[metric] = []
                fitness[metric].append(ind.fitness.values[j])
        df_metrics = pd.DataFrame(fitness)
        df_metrics.to_csv(os.path.join(path_to_save, 'metrics.csv'))

        # save history
        history = optimizer.history
        history.save(os.path.join(path_to_save, 'history.json'))

    @staticmethod
    def _save_visualizations(target_graph: Union[Graph, DiGraph], found_nx_graph: Union[DiGraph, Sequence[DiGraph]],
                             history: OptHistory, setup_name: str, path_to_save: str):
        """ Saves visualizations of results. """
        path_to_save = os.path.join(path_to_save, 'visualizations')
        os.makedirs(path_to_save, exist_ok=True)
        draw_graphs_subplots(target_graph, found_nx_graph,
                             titles=['Target Graph', 'Found Graph'], show=False, path_to_save=path_to_save)
        diversity_path_to_save = os.path.join(path_to_save, 'diversity')
        os.makedirs(diversity_path_to_save, exist_ok=True)
        diversity_filename = f'diversity_hist_{setup_name}.gif'
        history.show.diversity_population(save_path=os.path.join(diversity_path_to_save, diversity_filename))
        history.show.diversity_line(save_path=diversity_path_to_save, show=False)
        history.show.fitness_line(save_path=os.path.join(path_to_save, 'fitness_line.png'))


class CustomExperimentLauncher(ExperimentLauncher):
    """ Custom ExperimentLauncher. """
    def _launch_experiment(self, graph_name: str, num_nodes: int, node_types: List[str], optimizer_setup: Callable) \
            -> Tuple[GraphOptimizer, Objective, Union[Graph, DiGraph]]:
        """ Custom example for graph structure search task. """
        # Generate random target graph and run the optimizer
        target_graph = generate_labeled_graph(graph_name, num_nodes, node_types)
        target_graph = target_graph.reverse()
        # Run optimizer setup
        optimizer, objective = optimizer_setup(target_graph=target_graph,
                                               optimizer_cls=self.optimizer_cls,
                                               node_types=node_types,
                                               timeout=timedelta(minutes=self.trial_timeout)
                                               if self.trial_timeout else None,
                                               num_iterations=self.trial_iterations)
        return optimizer, objective, target_graph
