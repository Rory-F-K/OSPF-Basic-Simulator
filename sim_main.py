from OSPFSimulator import OSPFSimulator
from topology_generator import TopologyGenerator

def run_simulation(sim, label: str, num_failures: int = 2, dead_timer: float = 0.0):
    """
    Shared simulation steps used for every topology.

    Args:
        sim (OSPFSimulator): Populated simulator instance.
        label (str): Display name for this simulation run.
        num_failures (int): How many link failures to inject (default 2).
        dead_timer (float): OSPF Hello/Dead timer delay in seconds passed to each fail_link call. 0.0 = instant detection.
    """
    print(f"\n{'=' * 50}")
    print(f"  SIMULATION: {label}")
    print(f"{'=' * 50}")

    print("\n[SIMULATION] Initial Convergence")
    sim.initial_convergence()

    # Baseline traffic + CPU snapshot before any failures
    sim.simulate_traffic(iterations=200)
    sim.record_cpu_usage()

    # Inject failures on edges that actually exist in this topology
    for _ in range(num_failures):
        edges = list(sim.graph.edges())
        if not edges:
            print("[INFO] No more links available to fail.")
            break

        r1, r2 = edges[len(edges) // 2]
        sim.fail_link(r1, r2, dead_timer=dead_timer)
        sim.simulate_traffic(iterations=200)
        sim.record_cpu_usage()

    sim.show_metrics()
    sim.plot_cpu_usage()
    sim.plot_convergence()

    return sim.get_metrics_summary()


# Collected results for cross-topology comparison
results = {}


# Example 1 – Linear
sim = OSPFSimulator(propagation_delay=0.001)
topo = TopologyGenerator(sim)
topo.linear(num_routers=6, primary_cost=1, backup_cost=2, backup_stride=2)
results["Linear"] = run_simulation(sim, "Linear (6 routers)", dead_timer=0.0)


# Example 2 – Ring
sim = OSPFSimulator(propagation_delay=0.001)
topo = TopologyGenerator(sim)
topo.ring(num_routers=8, primary_cost=1, chord_cost=2, add_chords=True)
results["Ring"] = run_simulation(sim, "Ring (8 routers + chords)", dead_timer=0.0)


# Example 3 – Partial Mesh
sim = OSPFSimulator(propagation_delay=0.001)
topo = TopologyGenerator(sim)
topo.partial_mesh(num_routers=10, connectivity=0.4, seed=42)
results["Partial Mesh"] = run_simulation(sim, "Partial Mesh (10 routers, 40%)", dead_timer=0.0)


# Example 4 – Hub-and-Spoke
sim = OSPFSimulator(propagation_delay=0.001)
topo = TopologyGenerator(sim)
result = topo.hub_spoke(num_routers=7, hub_cost=1, spoke_cost=2)
print(f"Hub: {result.hub}   Spokes: {result.spokes}")
results["Hub Spoke"] = run_simulation(sim, "Hub-and-Spoke (1 hub + 6 spokes)", dead_timer=0.0)


# Example 5 – Binary Tree
sim = OSPFSimulator(propagation_delay=0.001)
topo = TopologyGenerator(sim)
result = topo.tree(num_routers=7, branching_factor=2, connect_leaves=True)
print(f"Root: {result.root}   Leaves: {result.leaves}")
results["Tree"] = run_simulation(sim, "Binary Tree (7 routers)", dead_timer=0.0)


# Dead timer comparison — Linear topology at 3 timer settings
# Shows how reducing the dead timer (or using BFD) cuts convergence time

print("\n\n" + "=" * 50)
print(" DEAD TIMER COMPARISON (Linear, 6 routers)")
print("=" * 50)

timer_results = {}
for label, timer in [("Instant (0s)", 0.0),
                     ("Reduced (1s)", 1.0),
                     ("Default OSPF (5s)", 5.0)]:
    sim = OSPFSimulator(propagation_delay=0.001)
    topo = TopologyGenerator(sim)
    topo.linear(num_routers=6)
    timer_results[label] = run_simulation(
        sim, f"Linear — dead_timer={timer}s",
        num_failures=2,
        dead_timer=timer,
    )


# Cross-topology comparison chart
OSPFSimulator.plot_comparison(results)

# Dead timer comparison chart
OSPFSimulator.plot_comparison(timer_results)