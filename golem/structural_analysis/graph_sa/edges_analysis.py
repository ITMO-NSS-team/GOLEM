from os.path import join
from typing import Optional, List, Type, Callable

import multiprocessing

from golem.core.log import default_log
from golem.core.optimisers.graph import OptGraph
from golem.core.optimisers.timer import OptimisationTimer
from golem.core.paths import default_data_dir
from golem.structural_analysis.graph_sa.edge_sa_approaches import EdgeAnalyzeApproach, EdgeAnalysis
from golem.structural_analysis.graph_sa.entities.edge import Edge
from golem.structural_analysis.graph_sa.result_presenting_structures.sa_analysis_results import SAAnalysisResults
from golem.structural_analysis.graph_sa.sa_requirements import StructuralAnalysisRequirements


class EdgesAnalysis:
    """
    This class is for edges structural analysis within an OptGraph .
    It takes edges and approaches to be applied to chosen edges.
    To define which edges to analyze pass them to edges_to_analyze filed
    or all edges will be analyzed.

    :param objectives: list of objective functions for computing metric values
    :param approaches: methods applied to edges to modify the graph or analyze certain operations.\
    Default: [EdgeDeletionAnalyze, EdgeReplaceOperationAnalyze]
    :param path_to_save: path to save results to. Default: ~home/Fedot/structural
    """

    def __init__(self, objectives: List[Callable],
                 approaches: Optional[List[Type[EdgeAnalyzeApproach]]] = None,
                 requirements: StructuralAnalysisRequirements = None,
                 path_to_save=None):

        self.objectives = objectives
        self.approaches = approaches
        self.requirements = \
            StructuralAnalysisRequirements() if requirements is None else requirements
        self.log = default_log(self)
        self.path_to_save = \
            join(default_data_dir(), 'structural', 'edges_structural') if path_to_save is None else path_to_save

    def analyze(self, graph: OptGraph, results: SAAnalysisResults,
                edges_to_analyze: List[Edge] = None,
                n_jobs: int = -1, timer: OptimisationTimer = None) -> SAAnalysisResults:
        """
        Main method to run the analyze process for every edge.

        :param graph: graph object to analyze
        :param results: SA results
        :param edges_to_analyze: edges to analyze. Default: all edges
        :param n_jobs: n_jobs
        :param timer: timer indicating how much time is left for optimization
        :return edges_results: dict with analysis result per Edge
        """

        if n_jobs == -1:
            n_jobs = multiprocessing.cpu_count()

        if not edges_to_analyze:
            self.log.message('Edges to analyze are not defined. All edges will be analyzed.')
            edges_to_analyze = [Edge.from_tuple([edge])[0] for edge in graph.get_edges()]

        edge_analysis = EdgeAnalysis(approaches=self.approaches,
                                     approaches_requirements=self.requirements,
                                     path_to_save=self.path_to_save)

        with multiprocessing.Pool(processes=n_jobs) as pool:
            cur_edges_result = pool.starmap(edge_analysis.analyze,
                                            [[graph, edge, self.objectives, timer]
                                             for edge in edges_to_analyze])
        for res in cur_edges_result:
            results.add_edge_result(res)

        return results