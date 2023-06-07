from abc import abstractmethod
from copy import deepcopy
from datetime import timedelta
from typing import TypeVar, Generic, Optional, Union, Tuple

import numpy as np

from golem.core.adapter import BaseOptimizationAdapter
from golem.core.adapter.adapter import IdentityAdapter
from golem.core.constants import MAX_TUNING_METRIC_VALUE
from golem.core.dag.graph_utils import graph_structure
from golem.core.log import default_log
from golem.core.optimisers.fitness import SingleObjFitness, MultiObjFitness
from golem.core.optimisers.graph import OptGraph
from golem.core.optimisers.objective import ObjectiveEvaluate, ObjectiveFunction
from golem.core.tuning.search_space import SearchSpace, convert_parameters
from golem.core.utilities.data_structures import ensure_wrapped_in_sequence

DomainGraphForTune = TypeVar('DomainGraphForTune')


class BaseTuner(Generic[DomainGraphForTune]):
    """
    Base class for hyperparameters optimization

    Args:
      objective_evaluate: objective to optimize
      adapter: the function for processing of external object that should be optimized
      search_space: SearchSpace instance
      iterations: max number of iterations
      early_stopping_rounds: Optional max number of stagnating iterations for early stopping.
      timeout: max time for tuning
      n_jobs: num of ``n_jobs`` for parallelization (``-1`` for use all cpu's)
      deviation: required improvement (in percent) of a metric to return tuned graph.
        By default, ``deviation=0.05``, which means that tuned graph will be returned
        if it's metric will be at least 0.05% better than the initial.
    """

    def __init__(self, objective_evaluate: ObjectiveFunction,
                 search_space: SearchSpace,
                 adapter: Optional[BaseOptimizationAdapter] = None,
                 iterations: int = 100,
                 early_stopping_rounds: Optional[int] = None,
                 timeout: timedelta = timedelta(minutes=5),
                 n_jobs: int = -1,
                 deviation: float = 0.05):
        self.iterations = iterations
        self.adapter = adapter or IdentityAdapter()
        self.search_space = search_space
        self.n_jobs = n_jobs
        if isinstance(objective_evaluate, ObjectiveEvaluate):
            objective_evaluate.eval_n_jobs = self.n_jobs
        self.objective_evaluate = self.adapter.adapt_func(objective_evaluate)
        self.deviation = deviation

        self.timeout = timeout
        self.early_stopping_rounds = early_stopping_rounds

        self._default_metric_value = MAX_TUNING_METRIC_VALUE
        self.was_tuned = False
        self.init_graph = None
        self.init_metric = None
        self.obtained_metric = None
        self.log = default_log(self)

    @abstractmethod
    def tune(self, graph: DomainGraphForTune) -> DomainGraphForTune:
        """
        Function for hyperparameters tuning on the graph

        Args:
          graph: domain graph for which hyperparameters tuning is needed

        Returns:
          Graph with optimized hyperparameters
        """
        raise NotImplementedError()

    def init_check(self, graph: OptGraph) -> None:
        """
        Method get metric on validation set before start optimization

        Args:
          graph: graph to calculate objective
        """
        self.log.info('Hyperparameters optimization start: estimation of metric for initial graph')

        # Train graph
        self.init_graph = deepcopy(graph)

        self.init_metric = self.get_metric_value(graph=self.init_graph)
        self.log.message(f'Initial graph: {graph_structure(self.init_graph)} \n'
                         f'Initial metric: {list(map(abs, ensure_wrapped_in_sequence(self.init_metric)))}')

    def final_check(self, tuned_graph: OptGraph) -> OptGraph:
        """
        Method propose final quality check after optimization process

        Args:
          tuned_graph: Tuned graph to calculate objective
        """

        self.obtained_metric = self.get_metric_value(graph=tuned_graph)

        if self.obtained_metric == self._default_metric_value:
            self.obtained_metric = None

        self.log.info('Hyperparameters optimization finished')

        prefix_tuned_phrase = 'Return tuned graph due to the fact that obtained metric'
        prefix_init_phrase = 'Return init graph due to the fact that obtained metric'

        # 0.05% deviation is acceptable
        deviation_value = (self.init_metric / 100.0) * self.deviation
        init_metric = self.init_metric + deviation_value * (-np.sign(self.init_metric))
        if self.obtained_metric is None:
            self.log.info(f'{prefix_init_phrase} is None. Initial metric is {abs(init_metric):.3f}')
            final_graph = self.init_graph
            final_metric = self.init_metric
        elif self.obtained_metric <= init_metric:
            self.log.info(f'{prefix_tuned_phrase} {abs(self.obtained_metric):.3f} equal or '
                          f'better than initial (+ {self.deviation}% deviation) {abs(init_metric):.3f}')
            final_graph = tuned_graph
            final_metric = self.obtained_metric
        else:
            self.log.info(f'{prefix_init_phrase} {abs(self.obtained_metric):.3f} '
                          f'worse than initial (+ {self.deviation}% deviation) {abs(init_metric):.3f}')
            final_graph = self.init_graph
            final_metric = self.init_metric
        self.log.message(f'Final graph: {graph_structure(final_graph)}')
        if final_metric is not None:
            self.log.message(f'Final metric: {abs(final_metric):.3f}')
        else:
            self.log.message('Final metric is None')
        self.obtained_metric = final_metric
        return final_graph

    def get_metric_value(self, graph: OptGraph) -> Union[float, Tuple[float, ]]:
        """
        Method calculates metric for algorithm validation

        Args:
          graph: Graph to evaluate

        Returns:
          value of loss function
        """
        graph_fitness = self.objective_evaluate(graph)

        if isinstance(graph_fitness, SingleObjFitness):
            metric_value = graph_fitness.value
            if not graph_fitness.valid:
                return self._default_metric_value
            return metric_value

        elif isinstance(graph_fitness, MultiObjFitness):
            metric_values = graph_fitness.getValues()
            for e, value in enumerate(metric_values):
                if value is None:
                    metric_values[e] = self._default_metric_value
            return metric_values

    @staticmethod
    def set_arg_graph(graph: OptGraph, parameters: dict) -> OptGraph:
        """ Method for parameters setting to a graph

        Args:
            graph: graph to which parameters should be assigned
            parameters: dictionary with parameters to set

        Returns:
            graph: graph with new hyperparameters in each node
        """
        # Set hyperparameters for every node
        for node_id, node in enumerate(graph.nodes):
            node_params = {key: value for key, value in parameters.items()
                           if key.startswith(f'{str(node_id)} || {node.name}')}

            if node_params is not None:
                BaseTuner.set_arg_node(graph, node_id, node_params)

        return graph

    @staticmethod
    def set_arg_node(graph: OptGraph, node_id: int, node_params: dict) -> OptGraph:
        """ Method for parameters setting to a graph

        Args:
            graph: graph which contains the node
            node_id: id of the node to which parameters should be assigned
            node_params: dictionary with labeled parameters to set

        Returns:
            graph with new hyperparameters in each node
        """

        # Remove label prefixes
        node_params = convert_parameters(node_params)

        # Update parameters in nodes
        graph.nodes[node_id].parameters = node_params

        return graph

    def _stop_tuning_with_message(self, message: str):
        self.log.message(message)
        self.obtained_metric = self.init_metric
