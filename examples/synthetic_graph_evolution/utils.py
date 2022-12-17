from collections.abc import Sequence
from datetime import datetime
from functools import partial

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from networkx import gn_graph, gnp_random_graph

from examples.synthetic_graph_evolution.graph_metrics import (
    get_edit_dist_metric,
    spectral_dist, spectral_dists_all
)
from golem.core.adapter.nx_adapter import BaseNetworkxAdapter
from golem.core.optimisers.objective import Objective
from golem.visualisation.graph_viz import GraphVisualizer


def plot_nx_graph(g: nx.DiGraph, ax: plt.Axes = None):
    adapter = BaseNetworkxAdapter()
    GraphVisualizer.draw_nx_dag(adapter.adapt(g), ax,
                                node_size_scale=0.2, font_size_scale=0.25,
                                edge_curvature_scale=0.5)


def draw_graphs_subplots(*graphs: Sequence[nx.Graph],
                         draw_fn=nx.draw_kamada_kawai,
                         size=10):
    ncols = int(np.ceil(np.sqrt(len(graphs))))
    nrows = len(graphs) // ncols
    aspect = nrows / ncols
    figsize = (size, int(size * aspect))
    fig, axs = plt.subplots(nrows, ncols, figsize=figsize)
    for ax, graph in zip(axs, graphs):
        draw_fn(graph, arrows=True, ax=ax)
    plt.show()


def measure_graphs(target_graph, graph, vis=False):
    ged = get_edit_dist_metric(target_graph, timeout=None)
    objective = Objective(quality_metrics={
        # 'edit_distance': ged,
        # 'matrix_edit_dist': partial(matrix_edit_dist, target_graph),
        'spectral_adjacency': partial(spectral_dist, target_graph, kind='adjacency'),
        'spectral_laplacian': partial(spectral_dist, target_graph, kind='laplacian'),
        'spectral_laplacian_norm': partial(spectral_dist, target_graph, kind='laplacian_norm'),
    })

    start = datetime.now()
    print("Computing metric...")
    # fitness = objective(graph)
    fitness = spectral_dists_all(target_graph, graph)
    fitness2 = spectral_dists_all(target_graph, graph, match_size=False)
    fitness3 = spectral_dists_all(target_graph, graph, k=10)
    end = datetime.now() - start
    print(f'metrics: {fitness}, computed for '
          f'size {len(target_graph.nodes)} in {end.seconds} sec.')
    print(f'metrics2: {fitness2}')
    print(f'metrics3: {fitness3}')

    if vis:
        # 2 subplots
        fig, axs = plt.subplots(nrows=1, ncols=2)
        for g, ax in zip((target_graph, graph), axs):
            plot_nx_graph(g, ax)

        plt.title(f'metrics: {fitness.values}')
        plt.show()


def try_random(n=100, it=1):
    for i in range(it):
        for p in [0.05, 0.15, 0.3]:
            # g1 = gnp_random_graph(n, p)
            g1 = gn_graph(n)
            # g2 = gnp_random_graph(n, p)
            # measure_graphs(g1, g2, vis=False)
            g2small = gnp_random_graph(n // 2, p)
            measure_graphs(g1, g2small, vis=False)


if __name__ == "__main__":
    try_random(n=30, it=3)
