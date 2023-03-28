import json
import os.path
from datetime import datetime
from typing import List, Tuple, Callable, Optional, Union, Dict, Any

from golem.core.dag.graph import Graph, GraphNode
from golem.core.log import default_log
from golem.core.paths import project_root
from golem.core.utilities.serializable import Serializable
from golem.serializers import Serializer
from golem.structural_analysis.graph_sa.entities.edge import Edge
from golem.structural_analysis.graph_sa.results.deletion_sa_approach_result import DeletionSAApproachResult
from golem.structural_analysis.graph_sa.results.object_sa_result import ObjectSAResult, \
    StructuralAnalysisResultsRepository


class SAAnalysisResults(Serializable):
    """ Class presenting results of Structural Analysis for the whole graph. """

    def __init__(self):
        self.results_per_iteration = {}
        self._add_empty_iteration_results()
        self.log = default_log('sa_results')

    def _add_empty_iteration_results(self):
        last_iter_num = int(list(self.results_per_iteration.keys())[-1]) if self.results_per_iteration.keys() else -1
        self.results_per_iteration.update({str(last_iter_num+1): self._init_iteration_result()})

    @staticmethod
    def _init_iteration_result():
        return {'nodes': [], 'edges': []}

    @property
    def is_empty(self):
        """ Bool value indicating is there any calculated results. """
        if self.results_per_iteration['0'] is None and \
                self.results_per_iteration['0'] is None:
            return True
        return False

    def get_info_about_worst_result(self, metric_idx_to_optimize_by: int, iter: Optional[int] = None):
        """ Returns info about the worst result.
        :param metric_idx_to_optimize_by: metric idx to optimize by
        :param iter: iteration on which to search for. """
        worst_value = None
        worst_result = None
        if not iter:
            iter = list(self.results_per_iteration.keys())[-1]
        if str(iter) not in self.results_per_iteration.keys():
            raise IndexError("No such iteration found.")

        nodes_results = self.results_per_iteration[str(iter)]['nodes']
        edges_results = self.results_per_iteration[str(iter)]['edges']

        for i, res in enumerate(nodes_results + edges_results):
            cur_res = res.get_worst_result_with_names(
                metric_idx_to_optimize_by=metric_idx_to_optimize_by)
            if not worst_value or cur_res['value'] > worst_value:
                worst_value = cur_res['value']
                worst_result = cur_res
        return worst_result

    def add_results(self, results: List[ObjectSAResult]):
        if not results:
            return 
        if results[0].entity_type == 'edges':
            key = 'edges'
        else:
            key = 'nodes'
        iter_num = self._find_last_empty_iter(key=key)
        for result in results:
            self.results_per_iteration[str(iter_num)][key].append(result)

    def _find_last_empty_iter(self, key: str):
        for i, result in enumerate(self.results_per_iteration.values()):
            if not result[key]:
                return i
        self._add_empty_iteration_results()
        return list(self.results_per_iteration.keys())[-1]

    def save(self, path: str = None, datetime_in_path: bool = True) -> dict:
        dict_results = dict()
        for iter in self.results_per_iteration.keys():
            dict_results[iter] = {}
            iter_result = self.results_per_iteration[iter]
            for entity_type in iter_result.keys():
                if entity_type not in dict_results[iter].keys():
                    dict_results[iter][entity_type] = {}
                for entity in iter_result[entity_type]:
                    dict_results[iter][entity_type].update(entity.get_dict_results())

        json_data = json.dumps(dict_results, cls=Serializer)

        if not path:
            path = os.path.join(project_root(), 'sa_results.json')
        if datetime_in_path:
            file_name = os.path.basename(path).split('.')[0]
            file_name = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{file_name}.json"
            path = os.path.join(os.path.dirname(path), file_name)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(json_data)
            self.log.debug(f'SA results saved in the path: {path}.')

        return dict_results

    @staticmethod
    def load(source: Union[str, dict], graph: Optional[Graph] = None):
        if isinstance(source, str):
            source = json.load(open(source))

        sa_result = SAAnalysisResults()
        results_repo = StructuralAnalysisResultsRepository()

        for iter in source:
            for entity_type in source[iter]:
                type_list = []
                for entity_idx in source[iter][entity_type]:
                    cur_result = ObjectSAResult(entity_idx=entity_idx,
                                                entity_type=entity_type)
                    dict_results = source[iter][entity_type][entity_idx]
                    for approach in dict_results:
                        app = results_repo.get_class_by_str(approach)()
                        if isinstance(app, DeletionSAApproachResult):
                            app.add_results(metrics_values=dict_results[approach])
                        else:
                            for entity_to_replace_to in dict_results[approach]:
                                app.add_results(entity_to_replace_to=entity_to_replace_to,
                                                metrics_values=dict_results[approach][entity_to_replace_to])
                        cur_result.add_result(app)
                    type_list.append(cur_result)
                sa_result.add_results(type_list)

        return sa_result


