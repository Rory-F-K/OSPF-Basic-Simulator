import networkx as nx
import matplotlib.pyplot as plt

from routers import Router
import time, random


class OSPFSimulator:

    def __init__(self, propagation_delay: float = 0.001):
        """
        Args:
            propagation_delay (float): Simulated per-router LSA flood and SPF delay in seconds. 
                Scales with router count to mimic real network propagation time. 
                Default 0.001s (1ms).
                Set to 0.0 to disable.
        """
        self.graph = nx.Graph()
        self.routers = {}

        self.current_time = 0

        self.lsa_count = 0
        self.lsa_timestamps = []

        self.packet_sent = 0
        self.packet_dropped = 0

        self.cpu_history = []
        self.convergence_history = []

        self.propagation_delay = propagation_delay

        # Tracks each failure event for detailed reporting
        self.failure_log = []

    # Add router to the network
    def add_router(self, name):
        self.graph.add_node(name)
        self.routers[name] = Router(name)

    # Add bidirectional link between routers with a cost
    def add_link(self, r1, r2, cost=1):
        self.graph.add_edge(r1, r2, weight=cost)

    # Simulate initial convergence by running SPF on all routers
    def initial_convergence(self):

        for router in self.routers.values():
            router.run_spf(self.graph)

    # Link failure simulation
    def fail_link(self, r1, r2, dead_timer: float = 0.0):
        """
        Simulates a link failure between two routers.

        Args:
            r1 (str): First router name.
            r2 (str): Second router name.
            dead_timer (float): Seconds to wait before the failure is detected, simulating the OSPF Hello/Dead timer expiry window.
                Real OSPF default is 40s; BFD-assisted detection
                can reduce this to ~1s or less. Default 0.0 (instant).
        """
        if not self.graph.has_edge(r1, r2):
            print(f"[WARNING] fail_link({r1}, {r2}): "
                  f"link does not exist or was already removed.")
            return

        print(f"\n[EVENT] Link failure: {r1} <-> {r2}")

        self.graph.remove_edge(r1, r2)

        # Simulate Hello/Dead timer expiry before failure is detected
        if dead_timer > 0:
            print(f"[INFO] Waiting for Dead timer ({dead_timer:.1f}s)...")
            time.sleep(dead_timer)

        failure_start = time.perf_counter()

        self.generate_lsa(r1)
        self.generate_lsa(r2)

        self.recompute_all_spf()

        failure_end = time.perf_counter()

        # Total convergence = dead timer wait + LSA flood + SPF recomputation
        convergence_time = (dead_timer +
                            (failure_end - failure_start))

        self.convergence_history.append(convergence_time)

        # Log the event for get_metrics_summary
        self.failure_log.append({
            "link": (r1, r2),
            "dead_timer": dead_timer,
            "convergence_time": convergence_time,
        })

        print(f"[INFO] Convergence Time: {convergence_time:.6f} sec"
              f" (dead timer: {dead_timer:.1f}s)")

    # Generate LSA updates for a given source router
    def generate_lsa(self, source):

        self.lsa_count += 1
        self.lsa_timestamps.append(time.perf_counter())

        for router in self.routers.values():
            router.cpu_load += 2
            router.lsdb[source] = "UPDATED"
            router.update_memory()

        # Simulate LSA flood propagation delay across all routers
        if self.propagation_delay > 0:
            flood_time = self.propagation_delay * len(self.routers)
            time.sleep(flood_time)

    # Simulate SPF recalculation on all routers after a topology change
    def recompute_all_spf(self):

        for router in self.routers.values():
            router.run_spf(self.graph)

        # Simulate SPF computation delay per router
        if self.propagation_delay > 0:
            spf_time = self.propagation_delay * len(self.routers)
            time.sleep(spf_time)

    # Traffic simulation to measure packet loss due to topology changes
    def simulate_traffic(self, iterations=100):

        router_names = list(self.routers.keys())

        for _ in range(iterations):

            src = random.choice(router_names)
            dst = random.choice(router_names)

            if src == dst:
                continue

            self.packet_sent += 1

            try:
                nx.shortest_path(self.graph, src, dst, weight='weight')

            except nx.NetworkXNoPath:
                self.packet_dropped += 1

    # CPU usage recording after each event
    def record_cpu_usage(self):

        total_cpu = sum(r.cpu_load
                        for r in self.routers.values())

        self.cpu_history.append(total_cpu)

    def get_metrics_summary(self) -> dict:
        """
        Returns a snapshot of all current metrics as a dictionary.

        Returns:
            dict: Keys are metric names, values are the computed results.
        """
        total_spf = sum(r.spf_runs for r in self.routers.values())

        avg_conv = (sum(self.convergence_history) /
                    len(self.convergence_history)
                    ) if self.convergence_history else 0.0

        loss = ((self.packet_dropped / self.packet_sent) * 100
                ) if self.packet_sent > 0 else 0.0

        avg_cpu = (sum(self.cpu_history) /
                   len(self.cpu_history)
                   ) if self.cpu_history else 0.0

        total_memory = sum(r.memory_usage for r in self.routers.values())

        if len(self.lsa_timestamps) >= 2:
            elapsed = self.lsa_timestamps[-1] - self.lsa_timestamps[0]
            lsa_rate = self.lsa_count / max(elapsed, 1e-6)
        else:
            lsa_rate = 0.0

        return {
            "num_routers":          len(self.routers),
            "num_links":            self.graph.number_of_edges(),
            "spf_recalculations":   total_spf,
            "lsa_count":            self.lsa_count,
            "lsa_rate":             round(lsa_rate, 2),
            "avg_convergence_sec":  round(avg_conv, 6),
            "avg_cpu":              round(avg_cpu, 2),
            "total_memory":         total_memory,
            "packet_loss_pct":      round(loss, 2),
            "failures":             len(self.failure_log),
        }

    # Display collected metrics in a readable format
    def show_metrics(self):
        print("\nOSPF PERFORMANCE METRICS\n\n")

        if self.propagation_delay > 0:
            print(f"Propagation Delay:        {self.propagation_delay * 1000:.1f} ms/router")
        else:
            print("Propagation Delay:        disabled")

        m = self.get_metrics_summary()

        print(f"Total SPF Recalculations: {m['spf_recalculations']}")

        if len(self.lsa_timestamps) >= 2:
            print(f"LSA Rate:                 {m['lsa_rate']:.2f} LSAs/sec")
        elif len(self.lsa_timestamps) == 1:
            print("LSA Rate:                 N/A (only 1 LSA generated)")
        else:
            print("LSA Rate:                 N/A (no failures occurred)")

        print(f"Average CPU Load:         {m['avg_cpu']:.2f}")
        print(f"Total Memory Usage:       {m['total_memory']}")
        print(f"Packet Loss:              {m['packet_loss_pct']:.2f}%")

        if self.convergence_history:
            print(f"Average Convergence Time: {m['avg_convergence_sec']:.6f} sec")

            # Per-event breakdown
            print("\n  Per-failure breakdown:")
            for i, event in enumerate(self.failure_log):
                r1, r2 = event["link"]
                print(f"  [{i + 1}] {r1}<->{r2}  "
                      f"dead_timer={event['dead_timer']:.1f}s  "
                      f"total={event['convergence_time']:.6f}s")
        else:
            print("Average Convergence Time: N/A (no failures occurred)")

    # Plotting functions to visualize metrics over time

    # Plot CPU usage over time
    def plot_cpu_usage(self):

        plt.figure(figsize=(8, 4))
        plt.plot(self.cpu_history, marker='o')
        plt.title("CPU Load During OSPF Events")
        plt.xlabel("Snapshot (record_cpu_usage call)")
        plt.ylabel("CPU Load")
        plt.grid(True)
        plt.show()

    # Plot convergence time per failure event
    def plot_convergence(self):

        plt.figure(figsize=(8, 4))
        plt.plot(self.convergence_history, marker='x')
        plt.title("Convergence Time Per Failure Event")
        plt.xlabel("Failure Event")
        plt.ylabel("Convergence Time (sec)")
        plt.grid(True)
        plt.show()

    # Plot a side-by-side comparison of metrics across topologies
    @staticmethod
    def plot_comparison(results: dict):
        """
        Renders a 2x2 grid of bar charts comparing key metrics across topologies.

        Args:
            results (dict): Mapping of topology name -> get_metrics_summary() dict.
                Built up in main.py after each simulation run.
        """
        labels = list(results.keys())
        metrics = {
            "Avg Convergence (sec)": [results[t]["avg_convergence_sec"] for t in labels],
            "SPF Recalculations":    [results[t]["spf_recalculations"]   for t in labels],
            "LSA Rate (LSAs/sec)":   [results[t]["lsa_rate"]             for t in labels],
            "Packet Loss (%)":       [results[t]["packet_loss_pct"]       for t in labels],
        }

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle("OSPF Topology Comparison", fontsize=14, fontweight="bold")

        for ax, (title, values) in zip(axes.flat, metrics.items()):
            bars = ax.bar(labels, values, color="steelblue", edgecolor="white")
            ax.set_title(title)
            ax.set_ylabel(title)
            ax.tick_params(axis="x", rotation=15)
            ax.grid(axis="y", linestyle="--", alpha=0.5)

            # Label each bar with its value
            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(values) * 0.01,
                    f"{val:.4f}" if val < 1 else f"{val:.1f}",
                    ha="center", va="bottom", fontsize=8,
                )

        plt.tight_layout()
        plt.show()