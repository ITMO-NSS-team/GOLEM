from typing import Dict, Tuple, Callable, List, Union

import numpy as np
from hyperopt import hp


class SearchSpace:
    """
    Args:
        search_space: dictionary with parameters and their search_space
            {'operation_name': {'param_name': (hyperopt distribution function, [sampling scope]), ...}, ...},
            e.g. ``{'operation_name': {'param1': (hp.uniformint, [2, 21]), ...}, ..}
    """

    def __init__(self, search_space: Dict[str, Dict[str, Dict[str, Union[Callable, List, str]]]]):
        self.parameters_per_operation = search_space

    def get_parameter_hyperopt_space(self, operation_name: str, parameter_name: str, label: str = 'default'):
        """
        Method return hyperopt object with search_space from search_space dictionary

        Args:
            operation_name: name of the operation
            parameter_name: name of hyperparameter of particular operation
            label: label to assign in hyperopt pyll

        Returns:
            dictionary with appropriate range
        """

        # Get available parameters for current operation
        operation_parameters = self.parameters_per_operation.get(operation_name)

        if operation_parameters is not None:
            parameter_properties = operation_parameters.get(parameter_name)
            hyperopt_distribution = parameter_properties.get('hyperopt-dist')
            sampling_scope = parameter_properties.get('sampling-scope')
            if hyperopt_distribution == hp.loguniform:
                sampling_scope = [np.log(x) for x in sampling_scope]
            return hyperopt_distribution(label, *sampling_scope)
        else:
            return None

    def get_node_params_for_hyperopt(self, node_id, operation_name):
        """
        Method for forming dictionary with hyperparameters for considering
        operation as a part of the whole graph

        :param node_id: number of node in graph.nodes list
        :param operation_name: name of operation in the node

        :return params_dict: dictionary-like structure with labeled hyperparameters
        and their range per operation
        """

        # Get available parameters for current operation
        params_list = self.get_parameters_for_operation(operation_name)

        params_dict = {}
        for parameter_name in params_list:
            node_op_parameter_name = get_node_operation_parameter_label(node_id, operation_name, parameter_name)

            # For operation get range where search can be done
            space = self.get_parameter_hyperopt_space(operation_name=operation_name,
                                                      parameter_name=parameter_name,
                                                      label=node_op_parameter_name)

            params_dict.update({node_op_parameter_name: space})

        return params_dict

    def get_node_params_for_iopt(self, node_id, operation_name):
        # Get available parameters for operation
        params_dict = self.parameters_per_operation.get(operation_name)

        discrete_params_dict = {}
        float_params_dict = {}

        if params_dict is not None:

            for parameter_name, parameter_properties in params_dict.items():
                node_op_parameter_name = get_node_operation_parameter_label(node_id, operation_name, parameter_name)

                parameter_type = parameter_properties.get('type')
                if parameter_type == 'discrete':
                    discrete_params_dict.update({node_op_parameter_name: parameter_properties.get('sampling-scope')})
                elif parameter_type == 'continuous':
                    float_params_dict.update({node_op_parameter_name: parameter_properties.get('sampling-scope')})

        return float_params_dict, discrete_params_dict

    def get_parameters_for_operation(self, operation_name: str) -> List[str]:
        params_list = list(self.parameters_per_operation.get(operation_name, {}).keys())
        return params_list


def get_node_operation_parameter_label(node_id: int, operation_name: str, parameter_name: str) -> str:
    # Name with operation and parameter
    op_parameter_name = ''.join((operation_name, ' | ', parameter_name))

    # Name with node id || operation | parameter
    node_op_parameter_name = ''.join((str(node_id), ' || ', op_parameter_name))
    return node_op_parameter_name


def convert_params(params):
    """
    Function removes labels from dictionary with operations

    :param params: labeled parameters
    :return new_params: dictionary without labels of node_id and operation_name
    """

    new_params = {}
    for operation_parameter, value in params.items():
        # Remove right part of the parameter name
        parameter_name = operation_parameter.split(' | ')[-1]

        if value is not None:
            new_params.update({parameter_name: value})

    return new_params
