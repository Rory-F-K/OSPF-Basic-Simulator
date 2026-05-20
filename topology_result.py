class TopologyResult:
    def __init__(
        self,
        topology: str,
        routers: list,
        primary_links: list,
        backup_links: list,
        **extras,
    ):
        self.topology = topology
        self.routers = routers
        self.primary_links = primary_links
        self.backup_links = backup_links
 
        # topology-specific attributes
        for key, value in extras.items():
            setattr(self, key, value)

    @property
    def all_links(self) -> list:
        """All primary and backup links combined."""
        return self.primary_links + self.backup_links
 
    @property
    def num_routers(self) -> int:
        return len(self.routers)

    def summary(self) -> str:
        return (
            f"[TOPOLOGY] {self.topology}: {len(self.routers)} routers | "
            f"{len(self.primary_links)} primary links | "
            f"{len(self.backup_links)} backup links | "
            f"{len(self.all_links)} total links"
        )

    def __repr__(self) -> str:
        return f"<TopologyResult topology={self.topology!r} \nrouters={len(self.routers)} \nlinks={len(self.all_links)}>"
