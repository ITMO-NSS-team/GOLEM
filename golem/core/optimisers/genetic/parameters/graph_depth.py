from golem.core.optimisers.archive.generation_keeper import ImprovementWatcher
from golem.core.optimisers.genetic.operators.operator import PopulationT
from golem.core.optimisers.genetic.parameters.parameter import AdaptiveParameter


class AdaptiveGraphDepth(AdaptiveParameter[int]):
    """Adaptive graph depth parameter. Max allowed graph depth changes
     during optimisation depending on observed improvements in the population.
     If there are no improvements, then graph depth is incremented.
     If there is an improvement, then graph depth remains the same.
     Can also play a role of static value if :param adaptive: is False."""

    def __init__(self, improvements: ImprovementWatcher,
                 start_depth: int = 1, max_depth: int = 10,
                 max_stagnation_gens: int = 1,
                 adaptive: bool = True):
        if start_depth is None or start_depth <= 0:
            raise ValueError(f'Uncorrect start_depth value: {start_depth}. It should be greater than 0.')
        if max_depth is None or max_depth < start_depth:
            raise ValueError(f'Uncorrect max_depth value: {max_depth}. It should be greater than start_depth.')
        if max_stagnation_gens is None or max_stagnation_gens <= 0:
            raise ValueError(f'Uncorrect max_stagnation_gens value: {max_stagnation_gens}.'
                             'It should be greater than 0.')
        self._improvements = improvements
        self._start_depth = start_depth
        self._max_depth = max_depth
        self._current_depth = start_depth
        self._max_stagnation_gens = max_stagnation_gens
        self._adaptive = adaptive

    @property
    def initial(self) -> int:
        return self._start_depth

    def next(self, population: PopulationT = None) -> int:
        if not self._adaptive:
            return self._max_depth
        if self._current_depth >= self._max_depth:
            return self._current_depth
        if self._improvements.stagnation_iter_count >= self._max_stagnation_gens:
            self._current_depth += 1
        return self._current_depth
