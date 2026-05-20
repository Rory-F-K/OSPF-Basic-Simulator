import networkx as nx

"""
This module defines a Router class that simulates OSPF SPF recalculation and tracks resource usage.
"""
class Router:
    def __init__(self, name):
        self.name = name
        self.routing_table = {}
        self.lsdb = {}
        self.spf_runs = 0
        self.cpu_load = 0
        self.memory_usage = 0
        self.converged = False

    def run_spf(self, graph):
        """
        Simulates OSPF SPF recalculation using Dijkstra.
        """
        self.spf_runs += 1
        self.cpu_load += 5

        try:
            paths = nx.single_source_dijkstra_path_length(
                graph,
                self.name,
                weight='weight'
            )
            self.routing_table = paths
            self.converged = True

        except Exception:
            self.routing_table = {}
            self.converged = False

    def update_memory(self):
        """
        Approximate LSDB memory usage.
        """
        self.memory_usage = len(self.lsdb) * 10
