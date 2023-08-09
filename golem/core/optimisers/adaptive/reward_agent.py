from typing import List, Tuple

from golem.core.optimisers.adaptive.operator_agent import ObsType


class RewardAgent:
    """
    Agent to process raw fitness values.
    The original idea is that the use of raw fitness values as rewards affects algorithm's robustness,
    therefore fitness values must be processed.
    The article with explanation -- https://ieeexplore.ieee.org/document/6410018
    """
    def __init__(self, decaying_factor: float = 1.):
        self._decaying_factor = decaying_factor

    def get_rewards_for_arms(self, obs: List[ObsType], arms: List[int]) -> List[float]:
        unique_arms, decay_values = self.get_decay_values_for_arms(obs, arms)
        frr_per_arm = self.get_fitness_rank_rate(decay_values)
        frr_values = [frr_per_arm[unique_arms.index(arm)] for arm in arms]
        return frr_values

    def get_decay_values_for_arms(self, rewards: List[ObsType], arms: List[int]) -> Tuple[List[int], List[float]]:
        decays = dict.fromkeys(set(arms), 0.0)
        for i, reward in enumerate(rewards):
            decays[arms[i]] += reward
        decays.update((key, value * self._decaying_factor) for key, value in decays.items())
        return list(decays.keys()), list(decays.values())

    @staticmethod
    def get_fitness_rank_rate(decay_values: List[float]) -> List[float]:
        decay_values_abs = [abs(i) for i in decay_values]
        total_decay_sum = sum(decay_values_abs)
        return [decay / total_decay_sum for decay in decay_values] if total_decay_sum != 0 else [0.]
