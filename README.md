# OSPF Convergence Simulator

A Python-based simulator for modelling and analysing OSPF (Open Shortest Path First) network convergence behaviour. Built to support academic research into convergence bottlenecks, subsystem analysis, and optimisation techniques across multiple network topologies.

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Modules](#modules)
  - [OSPFSimulator](#ospfsimulator)
  - [Router](#router)
  - [TopologyGenerator](#topologygenerator)
  - [TopologyResult](#topologyresult)
- [Topologies](#topologies)
- [Metrics](#metrics)
- [Limitations & Simplifications](#limitations--simplifications)

---

## Overview

This simulator models the three phases of OSPF convergence following a link failure:

1. **Failure Detection** — configurable dead timer delay mimicking OSPF Hello/Dead timer expiry or BFD-assisted detection
2. **LSA Flooding** — Link State Advertisement generation and propagation across all routers in the topology, with simulated per-router delay
3. **SPF Recomputation** — Dijkstra shortest-path recalculation on every router, tracked per run

Rather than replicate the full OSPF protocol stack, the simulator exposes every internal variable (LSA count, SPF runs, CPU load, memory usage) to allow controlled, reproducible experiments at arbitrary network scale — something not easily achievable with Cisco Packet Tracer or GNS3.

---

## Project Structure

```
.
├── main.py                  # Entry point — runs all topologies and comparisons
├── OSPFSimulator.py         # Core simulator: failure injection, metrics, plotting
├── routers.py               # Router class: SPF execution, LSDB, resource tracking
├── topology_generator.py    # Topology builder: 5 topology types
└── topology_result.py       # Result object returned by TopologyGenerator methods
```

---

## Installation

**Requirements:** Python 3.8+

```bash
pip install networkx matplotlib
```

No other dependencies are needed.

---

## Modules

### OSPFSimulator

**`OSPFSimulator(propagation_delay=0.001)`**

The central simulator class. Manages the network graph, failure events, LSA tracking, and all metric collection.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `propagation_delay` | float | `0.001` | Per-router delay in seconds applied after each LSA flood and SPF round. Set to `0.0` to disable. |

#### Methods

| Method | Description |
|---|---|
| `add_router(name)` | Registers a router node in the network graph |
| `add_link(r1, r2, cost=1)` | Adds a weighted bidirectional edge between two routers |
| `initial_convergence()` | Runs SPF on all routers to establish baseline routing tables |
| `fail_link(r1, r2, dead_timer=0.0)` | Removes a link, optionally waits for dead timer, then triggers LSA flood and SPF recomputation |
| `generate_lsa(source)` | Floods an LSA from the given source router to all others, incrementing CPU load and updating LSDB |
| `recompute_all_spf()` | Re-runs Dijkstra on every router after a topology change |
| `simulate_traffic(iterations=100)` | Randomly selects source/destination pairs and counts dropped packets when no path exists |
| `record_cpu_usage()` | Snapshots the total CPU load across all routers at the current moment |
| `get_metrics_summary()` | Returns all current metrics as a dictionary — used for cross-topology comparison |
| `show_metrics()` | Prints a formatted metrics report to stdout, including per-failure breakdown |
| `plot_cpu_usage()` | Line chart of CPU load snapshots over time |
| `plot_convergence()` | Line chart of convergence time per failure event |
| `plot_comparison(results)` | **Static.** 2×2 bar chart grid comparing metrics across multiple topologies |

---

### Router

**`Router(name)`**

Represents a single OSPF router. Tracks its own routing table, LSDB, and resource usage. Instantiated automatically by `OSPFSimulator.add_router()`.

| Attribute | Description |
|---|---|
| `routing_table` | Dict of `{destination: cost}` from the last SPF run |
| `lsdb` | Dict of `{router_name: "UPDATED"}` — simulates the Link State Database |
| `spf_runs` | Counter incremented on every Dijkstra execution |
| `cpu_load` | Cumulative CPU load units — +5 per SPF run, +2 per LSA received |
| `memory_usage` | Approximated as `len(lsdb) * 10` bytes |
| `converged` | Boolean — `True` if the last SPF run completed without error |

| Method | Description |
|---|---|
| `run_spf(graph)` | Runs `nx.single_source_dijkstra_path_length` from this router's perspective |
| `update_memory()` | Recalculates `memory_usage` based on current LSDB size |

---

### TopologyGenerator

**`TopologyGenerator(sim)`**

Builds network topologies directly into an `OSPFSimulator` instance by calling `sim.add_router()` and `sim.add_link()`. Returns a `TopologyResult` from every method.

All methods accept `num_routers` as their first argument and print a `[TOPOLOGY]` summary line on completion.

| Method | Primary Links | Backup Links | Minimum Routers |
|---|---|---|---|
| `linear()` | Sequential chain R1→R2→…→Rn | Skip-hop (configurable stride) | 2 |
| `ring()` | Bidirectional ring | Diameter chord shortcuts | 3 |
| `full_mesh()` | All pairs connected | None (all links are primary) | 2 |
| `partial_mesh()` | Random spanning tree | Random extras to target density | 2 |
| `hub_spoke()` | Hub R1 → all spokes | Spoke-to-spoke backup ring | 3 |
| `tree()` | Breadth-first k-ary tree | Adjacent leaf cross-links | 2 |

#### `linear(num_routers, primary_cost, backup_cost, backup_stride)`

```
Primary:  R1─R2─R3─R4─R5─R6
Backup:   R1─R3, R2─R4, R3─R5, R4─R6   (stride=2)
```

#### `ring(num_routers, primary_cost, chord_cost, add_chords)`

```
Primary:  R1─R2─R3─R4─R5─R6─R7─R8─R1
Chords:   R1─R5, R2─R6, R3─R7, R4─R8
```

#### `full_mesh(num_routers, base_cost, cost_jitter, seed)`

Every router connected to every other. Link count = n(n-1)/2. Recommended n ≤ 10; warns above this threshold.

#### `partial_mesh(num_routers, connectivity, primary_cost, backup_cost, seed)`

`connectivity` controls link density — `0.0` produces a spanning tree, `1.0` produces a full mesh. A random spanning tree is always built first to guarantee full connectivity before extra links are added.

#### `hub_spoke(num_routers, hub_cost, spoke_cost)`

```
Hub R1 connected to all spokes.
Spoke ring: R2─R3─R4─R5─R6─R7─R2   (backup)
```

#### `tree(num_routers, branching_factor, primary_cost, leaf_link_cost, connect_leaves)`

```
Binary tree (branching_factor=2):
        R1
       /  \
      R2   R3
     / \  / \
    R4 R5 R6 R7
Leaf links: R4─R5, R5─R6, R6─R7   (backup)
```

---

### TopologyResult

Returned by every `TopologyGenerator` method. Provides access to the built topology without reaching into the simulator directly.

| Attribute | Type | Description |
|---|---|---|
| `topology` | str | Topology type name e.g. `"Linear"` |
| `routers` | list | Ordered list of router name strings `["R1", "R2", …]` |
| `primary_links` | list | List of `(r1, r2, cost)` tuples for primary links |
| `backup_links` | list | List of `(r1, r2, cost)` tuples for backup/redundancy links |
| `all_links` | list | `primary_links + backup_links` |
| `num_routers` | int | `len(routers)` |
| `num_links` | int | `len(all_links)` |
| `hub` | str | Hub router name *(hub_spoke only)* |
| `spokes` | list | Spoke router names *(hub_spoke only)* |
| `root` | str | Root router name *(tree only)* |
| `leaves` | list | Leaf router names *(tree only)* |

---

## Topologies

The five topology types model different real-world network architectures:

| Topology | Real-world analogue | Redundancy model |
|---|---|---|
| Linear | Serial WAN links, branch office chains | Skip-hop backup paths |
| Ring | Metro Ethernet rings, SDH/SONET | Two paths always available |
| Full Mesh | Small core networks, data centre spine | Maximum redundancy, high overhead |
| Partial Mesh | ISP backbone, enterprise WAN | Tunable cost/redundancy trade-off |
| Hub Spoke | Data centre / remote site WAN star | Hub is single point of failure |
| Tree | Hierarchical campus networks | Leaf cross-links prevent stranded subtrees |

---

## Metrics

`get_metrics_summary()` returns the following dict — also printed by `show_metrics()`:

| Key | Unit | Description |
|---|---|---|
| `num_routers` | count | Total routers in the topology |
| `num_links` | count | Total links currently in the graph |
| `spf_recalculations` | count | Sum of `spf_runs` across all routers |
| `lsa_count` | count | Total LSAs generated across all failures |
| `lsa_rate` | LSAs/sec | Flood rate — `lsa_count / elapsed_time` between first and last LSA timestamp |
| `avg_convergence_sec` | seconds | Mean convergence time across all failure events |
| `avg_cpu` | units | Mean total CPU load across all `record_cpu_usage()` snapshots |
| `total_memory` | bytes (approx.) | Sum of `memory_usage` across all routers |
| `packet_loss_pct` | % | `(dropped / sent) * 100` from all `simulate_traffic()` calls |
| `failures` | count | Number of `fail_link()` events recorded |

---

## Limitations & Simplifications

| Simplification | Real OSPF behaviour |
|---|---|
| Single OSPF area | Real networks use multi-area OSPF with ABRs and ASBRs |
| Generic LSAs (no type) | OSPF defines Type 1–7 LSAs with different flooding scopes |
| CPU load is cumulative units, not % | Real routers measure CPU as percentage utilisation over an interval |
| Memory approximated as `len(lsdb) * 10` | Real LSDB memory depends on LSA size, age, and checksum fields |
| SPF runs on every router simultaneously | Real networks have asynchronous SPF execution with backoff timers |
| Propagation delay is uniform per router | Real delay depends on link bandwidth, queuing, and geographic distance |
| No Hello/Dead timer negotiation | Dead timer is injected as a fixed sleep, not a protocol exchange |
| No LSA sequence numbers or aging | Real OSPF LSAs carry sequence numbers and expire after 3600s |

Goal is a controlled mathematical model of convergence dynamics rather than a full protocol implementation.