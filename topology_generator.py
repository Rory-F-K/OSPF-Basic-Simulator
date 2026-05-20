import random
import math

from topology_result import TopologyResult

"""
This module generates random network topologies for testing OSPF simulations. 
It creates a specified number of routers and randomly connects them with links of varying costs. 

The generated topology is represented as an adjacency list, which can be easily integrated into the OSPF simulator for testing purposes.

5 Topologies made:
    - Linear      : Chain with skip-hop backup links.
    - Ring        : Bidirectional ring with optional diameter chord shortcuts.
    - Full Mesh   : Every router connected to every other router.
    - Partial Mesh: Guaranteed-connected spanning tree + random extra links.
    - Hub Spoke   : Central hub connected to all spokes; spokes form a backup ring.
    - Tree        : Balanced k-ary tree with optional leaf cross-links.
"""


class TopologyGenerator:
    def __init__(self, sim):
        """
        Args:
            sim (OSPFSimulator): The simulator instance to build the topology into.
        """
        self.sim = sim

    def linear(
        self,
        num_routers=5,
        primary_cost: int = 1,
        backup_cost: int = 2,
        backup_stride: int = 2,
    ) -> "TopologyResult":
        """
        Generates a linear topology where each router is connected to the next one in a line.
        Optionally adds backup links with higher costs.

        Primary:  R1-R2-R3- ... -Rn
        Backup:   R1-R3, R2-R4, ...  (skip backup_stride routers)

        Args:
            num_routers (int): Number of routers in the topology.
            primary_cost (int): Cost of primary links.
            backup_cost (int): Cost of backup links.
            backup_stride (int): Interval at which backup links are added.
        Returns:
            TopologyResult: The generated topology result.
        """
        self._validate(num_routers, primary_cost, backup_cost, backup_stride)
        routers = self._make_routers(num_routers)
        primary_links, backup_links = [], []

        # Primary chain
        for i in range(len(routers) - 1):
            self.sim.add_link(routers[i], routers[i + 1], primary_cost)
            primary_links.append((routers[i], routers[i + 1], primary_cost))

        # Skip-hop backup links
        for i in range(len(routers) - backup_stride):
            self.sim.add_link(routers[i], routers[i + backup_stride], backup_cost)
            backup_links.append((routers[i], routers[i + backup_stride], backup_cost))

        result = TopologyResult(
            topology="Linear",
            routers=routers,
            primary_links=primary_links,
            backup_links=backup_links,
        )

        print(result.summary())
        return result

    def ring(
        self,
        num_routers: int = 6,
        primary_cost: int = 1,
        chord_cost: int = 2,
        add_chords: bool = True,
    ) -> "TopologyResult":
        """
        Generates a ring topology where every router is connected to its two neighbours,
        with optional chord (shortcut) links across the ring for redundancy.

        Primary:  R1-R2- ... -Rn-R1
        Chords:   Each router to its diametrically opposite router.

        Args:
            num_routers (int): Number of routers in the topology (minimum 3).
            primary_cost (int): Cost of ring edge links.
            chord_cost (int): Cost of chord (shortcut) links.
            add_chords (bool): Whether to add diameter chords for redundancy.
        Returns:
            TopologyResult: The generated topology result.
        """
        self._validate(num_routers, primary_cost, chord_cost, minimum=3)
        routers = self._make_routers(num_routers)
        primary_links, backup_links = [], []

        # Ring edges
        for i in range(num_routers):
            a, b = routers[i], routers[(i + 1) % num_routers]
            self.sim.add_link(a, b, primary_cost)
            primary_links.append((a, b, primary_cost))

        # Diameter chord shortcuts
        if add_chords:
            for i in range(num_routers // 2):
                opposite = i + num_routers // 2
                if opposite < num_routers:
                    self.sim.add_link(routers[i], routers[opposite], chord_cost)
                    backup_links.append((routers[i], routers[opposite], chord_cost))

        result = TopologyResult(
            topology="Ring",
            routers=routers,
            primary_links=primary_links,
            backup_links=backup_links,
        )

        print(result.summary())
        return result

    def full_mesh(
        self,
        num_routers: int = 5,
        base_cost: int = 1,
        cost_jitter: bool = False,
        seed: int = None,
    ) -> "TopologyResult":
        """
        Generates a full-mesh topology where every router is connected to every other router.
        Link count grows as O(n^2); recommended for n <= 10.

        Args:
            num_routers (int): Number of routers in the topology (recommended <= 10).
            base_cost (int): Base link cost; upper bound when cost_jitter is True.
            cost_jitter (bool): If True, randomises each link cost in [1, base_cost * 3].
            seed (int): Random seed for reproducible jitter.
        Returns:
            TopologyResult: The generated topology result.
        """
        self._validate(num_routers, base_cost)
        if num_routers > 10:
            max_links = num_routers * (num_routers - 1) // 2
            print(
                f"[WARNING] Full-mesh with {num_routers} routers creates {max_links} links. "
                "Consider partial_mesh() for large topologies."
            )

        if seed is not None:
            random.seed(seed)

        routers = self._make_routers(num_routers)
        primary_links = []

        for i in range(num_routers):
            for j in range(i + 1, num_routers):
                cost = random.randint(1, base_cost * 3) if cost_jitter else base_cost
                self.sim.add_link(routers[i], routers[j], cost)
                primary_links.append((routers[i], routers[j], cost))

        result = TopologyResult(
            topology="Full Mesh",
            routers=routers,
            primary_links=primary_links,
            backup_links=[],
        )

        print(result.summary())
        return result

    def partial_mesh(
        self,
        num_routers: int = 8,
        connectivity: float = 0.4,
        primary_cost: int = 1,
        backup_cost: int = 2,
        seed: int = None,
    ) -> "TopologyResult":
        """
        Generates a partial-mesh topology using a random spanning tree for primary links,
        then adds extra random links until the target link density is reached.

        Args:
            num_routers (int): Number of routers in the topology.
            connectivity (float): Fraction of all possible links to include (0.0 to 1.0).
                                  0.0 = spanning tree only; 1.0 = full mesh.
            primary_cost (int): Cost of spanning-tree (guaranteed) links.
            backup_cost (int): Cost of extra random links.
            seed (int): Random seed for reproducibility.
        Returns:
            TopologyResult: The generated topology result.
        """
        self._validate(num_routers, primary_cost, backup_cost)
        if not 0.0 <= connectivity <= 1.0:
            raise ValueError("connectivity must be between 0.0 and 1.0.")

        if seed is not None:
            random.seed(seed)

        routers = self._make_routers(num_routers)
        primary_links, backup_links = [], []

        # Step 1 - random spanning tree guarantees full connectivity
        shuffled = routers[:]
        random.shuffle(shuffled)
        connected = {shuffled[0]}

        for r in shuffled[1:]:
            anchor = random.choice(list(connected))
            self.sim.add_link(anchor, r, primary_cost)
            primary_links.append((anchor, r, primary_cost))
            connected.add(r)

        # Step 2 - top up with random extra links to reach the connectivity target
        existing = {tuple(sorted((a, b))) for a, b, _ in primary_links}
        candidates = [
            (routers[i], routers[j])
            for i in range(num_routers)
            for j in range(i + 1, num_routers)
            if tuple(sorted((routers[i], routers[j]))) not in existing
        ]
        random.shuffle(candidates)

        total_possible = num_routers * (num_routers - 1) // 2
        target_extras = max(0, int(connectivity * total_possible) - len(primary_links))

        for a, b in candidates[:target_extras]:
            self.sim.add_link(a, b, backup_cost)
            backup_links.append((a, b, backup_cost))

        result = TopologyResult(
            topology="Partial Mesh",
            routers=routers,
            primary_links=primary_links,
            backup_links=backup_links,
        )

        print(result.summary())
        return result

    def hub_spoke(
        self,
        num_routers: int = 6,
        hub_cost: int = 1,
        spoke_cost: int = 2,
    ) -> "TopologyResult":
        """
        Generates a hub-and-spoke topology. R1 is the central hub connected to all others.
        Adjacent spokes are also cross-linked in a ring for backup paths.

        Args:
            num_routers (int): Total routers including the hub (minimum 3).
            hub_cost (int): Cost for hub-to-spoke links.
            spoke_cost (int): Cost for spoke-to-spoke backup ring links.
        Returns:
            TopologyResult: The generated topology result, with result.hub and result.spokes.
        """
        self._validate(num_routers, hub_cost, spoke_cost, minimum=3)
        routers = self._make_routers(num_routers)
        hub = routers[0]
        spokes = routers[1:]
        primary_links, backup_links = [], []

        # Hub to all spokes
        for spoke in spokes:
            self.sim.add_link(hub, spoke, hub_cost)
            primary_links.append((hub, spoke, hub_cost))

        # Spoke backup ring: adjacent spokes cross-linked
        for i in range(len(spokes) - 1):
            self.sim.add_link(spokes[i], spokes[i + 1], spoke_cost)
            backup_links.append((spokes[i], spokes[i + 1], spoke_cost))

        # Close the ring if there are more than 2 spokes
        if len(spokes) > 2:
            self.sim.add_link(spokes[-1], spokes[0], spoke_cost)
            backup_links.append((spokes[-1], spokes[0], spoke_cost))

        result = TopologyResult(
            topology="Hub Spoke",
            routers=routers,
            primary_links=primary_links,
            backup_links=backup_links,
            hub=hub,
            spokes=spokes,
        )

        print(result.summary())
        return result

    def tree(
        self,
        num_routers: int = 7,
        branching_factor: int = 2,
        primary_cost: int = 1,
        leaf_link_cost: int = 2,
        connect_leaves: bool = True,
    ) -> "TopologyResult":
        """
        Generates a balanced k-ary tree topology with optional leaf-level cross-links.
        The tree is built breadth-first. Leaves are optionally connected in pairs
        to provide backup paths (important since leaves otherwise have only one parent).

        Args:
            num_routers (int): Total number of routers.
            branching_factor (int): Number of children per internal node (k in k-ary tree).
            primary_cost (int): Cost for parent-to-child links.
            leaf_link_cost (int): Cost for adjacent leaf cross-links.
            connect_leaves (bool): Connect adjacent leaves as backup paths.
        Returns:
            TopologyResult: The generated topology result, with result.root and result.leaves.
        """
        self._validate(num_routers, primary_cost, leaf_link_cost)
        if branching_factor < 2:
            raise ValueError("branching_factor must be >= 2.")

        routers = self._make_routers(num_routers)
        primary_links, backup_links = [], []

        # Build tree edges breadth-first
        for i in range(num_routers):
            for k in range(1, branching_factor + 1):
                child_idx = branching_factor * i + k
                if child_idx < num_routers:
                    self.sim.add_link(routers[i], routers[child_idx], primary_cost)
                    primary_links.append((routers[i], routers[child_idx], primary_cost))

        # Leaves: nodes with no children in the tree
        leaves = [
            routers[i]
            for i in range(num_routers)
            if all(
                branching_factor * i + k >= num_routers
                for k in range(1, branching_factor + 1)
            )
        ]

        # Connect adjacent leaves for backup paths
        if connect_leaves:
            for i in range(len(leaves) - 1):
                self.sim.add_link(leaves[i], leaves[i + 1], leaf_link_cost)
                backup_links.append((leaves[i], leaves[i + 1], leaf_link_cost))

        result = TopologyResult(
            topology="Tree",
            routers=routers,
            primary_links=primary_links,
            backup_links=backup_links,
            root=routers[0],
            leaves=leaves,
        )

        print(result.summary())
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_routers(self, n: int) -> list:
        """
        Creates n routers named R1...Rn, registers them with the simulator,
        and returns the ordered list of names.
        """
        names = [f"R{i}" for i in range(1, n + 1)]
        for name in names:
            self.sim.add_router(name)
        return names

    def _validate(self, num_routers: int, *costs: int, minimum: int = 2) -> None:
        """
        Validates common arguments shared across all topology methods.

        Args:
            num_routers (int): Must be >= minimum.
            *costs (int):      Any number of cost values; each must be >= 1.
            minimum (int):     Minimum acceptable router count (default 2).
        Raises:
            ValueError: If any argument is out of range.
        """
        if num_routers < minimum:
            raise ValueError(
                f"num_routers must be >= {minimum}; got {num_routers}."
            )
        for cost in costs:
            if isinstance(cost, int) and cost < 1:
                raise ValueError(
                    f"Link costs must be >= 1; got {cost}."
                )