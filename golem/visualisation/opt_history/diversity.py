from typing import Optional

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation

from golem.core.optimisers.genetic.operators.operator import PopulationT
from golem.core.optimisers.opt_history_objects.opt_history import OptHistory
from golem.visualisation.opt_history.utils import show_or_save_figure


def compute_fitness_diversity(population: PopulationT) -> np.ndarray:
    """Returns numpy array of standard deviations of fitness values."""
    # substitutes None values
    fitness_values = np.array([ind.fitness.values for ind in population], dtype=float)
    # compute std along each axis while ignoring nan-s
    diversity = np.nanstd(fitness_values, axis=0)
    return diversity


def plot_diversity_dynamic_gif(history: OptHistory,
                               filename: Optional[str] = None,
                               fig_size: int = 5,
                               fps: int = 4,
                               ) -> FuncAnimation:
    metric_names = history.objective.metric_names
    # dtype=float removes None, puts np.nan
    # indexed by [population, metric, individual] after transpose (.T)
    pops = history.individuals[1:-1]  # ignore initial pop and final choices
    fitness_distrib = [np.array([ind.fitness.values for ind in pop], dtype=float).T
                       for pop in pops]

    # Define bounds on metrics: find min & max on a flattened view of array
    q = 0.025
    lims_max = np.max([np.quantile(pop, 1 - q, axis=1) for pop in fitness_distrib], axis=0)
    lims_min = np.min([np.quantile(pop, q, axis=1) for pop in fitness_distrib], axis=0)

    # Setup the plot
    fig, axs = plt.subplots(ncols=len(metric_names))
    fig.set_size_inches(fig_size * len(metric_names), fig_size)
    np.ravel(axs)

    # Set update function for updating data on the axes
    def update_axes(iframe: int):
        for i, (ax, metric_distrib) in enumerate(zip(axs, fitness_distrib[iframe])):
            # Clear & Prepare axes
            ax: plt.Axes
            ax.clear()
            ax.set_xlim(0.5, 1.5)
            ax.set_ylim(lims_min[i], lims_max[i])
            ax.set_ylabel('Metric value')
            ax.grid()
            # Plot information
            fig.suptitle(f'Population {iframe+1} diversity by metric')
            ax.set_title(f'{metric_names[i]}, '
                         f'mean={np.mean(metric_distrib).round(3)}, '
                         f'std={np.nanstd(metric_distrib).round(3)}')
            ax.violinplot(metric_distrib,
                          quantiles=[0.25, 0.5, 0.75])

    # Run this function in FuncAnimation
    num_frames = len(fitness_distrib)
    animate = FuncAnimation(
        fig=fig,
        func=update_axes,
        save_count=num_frames,
        interval=200,
    )
    # Save the GIF from animation
    if filename:
        animate.save(filename, fps=fps, dpi=150)
    return animate


def plot_diversity_dynamic(history: OptHistory,
                           show=True, save_path: Optional[str] = None, dpi: int = 100):
    labels = history.objective.metric_names
    h = history.individuals[:-1]  # don't consider final choices
    xs = np.arange(len(h))

    # Compute diversity by metrics
    np_history = np.array([compute_fitness_diversity(pop) for pop in h])
    ys = {label: np_history[:, i] for i, label in enumerate(labels)}
    # Compute number of unique individuals, plot
    ratio_unique = [len(set(ind.graph.descriptive_id for ind in pop)) / len(pop) for pop in h]

    fig, ax = plt.subplots()
    fig.suptitle('Population diversity')
    ax.set_xlabel('Generation')
    ax.set_ylabel('Std')
    ax.grid()

    for label, metric_std in ys.items():
        ax.plot(xs, metric_std, label=label)

    ax2 = ax.twinx()
    ax2.set_ylabel('Unique ratio')
    ax2.set_ylim(0.25, 1.0)
    ax2.plot(xs, ratio_unique, label='unique ratio', color='tab:gray')

    # ask matplotlib for the plotted objects and their labels
    # to put them into single legend for both axes
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2,
               loc='upper left', bbox_to_anchor=(0., 1.15))

    if show or save_path:
        show_or_save_figure(fig, save_path, dpi)