import json
from pathlib import Path
from typing import Dict, List, Optional

import igraph as ig


class ZomboidModGraph:
    """A directed dependency graph for Project Zomboid mods.

    This class represents the dependency relationships between mods used in Project Zomboid,
    using a directed graph (via `igraph`). Mods can be added or updated using metadata,
    and their dependencies or dependents can be queried by mod name or workshop ID.
    The graph can also be saved or loaded in GraphML and JSON formats.

    Attributes:
        graph (igraph.Graph): A directed graph representing the mod dependencies.
        mod_data (dict): A dictionary mapping workshop IDs to mod metadata.

    Args:
        mod_data (Optional[Dict[str, dict]]): Optional dictionary containing mod metadata
            keyed by workshop ID. Each mod entry may contain:
                - 'mod_name': Display name of the mod
                - 'url': URL to the mod (e.g., Steam Workshop)
                - 'mod_id': Internal mod identifier(s)
                - 'required': List of workshop IDs this mod depends on
    """

    def __init__(self, mod_data: Optional[Dict[str, dict]] = None):
        """Initialize the ZomboidModGraph with optional mod metadata.

        Args:
            mod_data (Optional[Dict[str, dict]]): A dictionary where keys are workshop IDs and
                values are dictionaries with mod metadata. Metadata can include:
                - 'mod_name': Name of the mod
                - 'url': URL to the mod
                - 'mod_id': List of internal mod identifiers
                - 'required': List of workshop IDs that this mod depends on
        """
        self.graph = ig.Graph(directed=True)
        self.mod_data = {}

        if mod_data:
            self.mod_data = mod_data
            self._build_graph()

    def _build_graph(self) -> None:
        """Internal method to construct the dependency graph from `self.mod_data`.

        Adds vertices for each mod and creates directed edges for required dependencies.
        """
        vertices = list(self.mod_data.keys())
        self.graph.add_vertices(vertices)

        for vid in vertices:
            info = self.mod_data[vid]
            v = self.graph.vs.find(vid)
            v["name"] = vid
            v["mod_name"] = info.get("mod_name", "")
            v["url"] = info.get("url", "")
            v["mod_id"] = info.get("mod_id", [])

        edges = []
        for mod_id, info in self.mod_data.items():
            for req in info.get("required", []):
                if req in self.mod_data:
                    edges.append((mod_id, req))
        self.graph.add_edges(edges)

    def get_mod_names(self) -> List[str]:
        """Retrieve the list of mod names from the graph.

        Returns:
            List[str]: A list of mod names stored in the graph.
        """
        return self.graph.vs["mod_name"]

    def get_dependencies(self, identifier: str) -> List[str]:
        """Get the mods that a given mod depends on.

        Args:
            identifier (str): The mod's workshop ID or mod name.

        Returns:
            List[str]: A list of workshop IDs that the mod depends on.

        Raises:
            ValueError: If the identifier is not found or is ambiguous.
        """
        matched = None

        # Try by workshop_id first
        if identifier in self.graph.vs["name"]:
            matched = self.graph.vs.find(name=identifier)
        else:
            # Try by mod_name (case-insensitive match)
            matches = [v for v in self.graph.vs if v["mod_name"].lower() == identifier.lower()]
            if len(matches) == 1:
                matched = matches[0]
            elif len(matches) > 1:
                raise ValueError(f"Ambiguous mod name '{identifier}'; multiple mods matched.")
            else:
                raise ValueError(f"No mod found with name or ID '{identifier}'.")

        successors = self.graph.successors(matched.index)
        return [self.graph.vs[idx]["name"] for idx in successors]

    def get_dependents(self, identifier: str) -> None:
        """Get the mods that depend on the given mod.

        Args:
            identifier (str): The mod's workshop ID or mod name.

        Returns:
            List[str]: A list of workshop IDs for mods that require the specified mod.

        Raises:
            ValueError: If the identifier is not found or is ambiguous.
        """
        matched = None

        # Try by workshop_id first
        if identifier in self.graph.vs["name"]:
            matched = self.graph.vs.find(name=identifier)
        else:
            # Try by mod_name (case-insensitive match)
            matches = [v for v in self.graph.vs if v["mod_name"].lower() == identifier.lower()]
            if len(matches) == 1:
                matched = matches[0]
            elif len(matches) > 1:
                raise ValueError(f"Ambiguous mod name '{identifier}'; multiple mods matched.")
            else:
                raise ValueError(f"No mod found with name or ID '{identifier}'.")

        predecessors = self.graph.predecessors(matched.index)
        return [self.graph.vs[idx]["name"] for idx in predecessors]

    def print_dependency_tree(self) -> None:
        """Print a simple text-based tree showing each mod and its direct dependencies."""
        for v in self.graph.vs:
            deps = [self.graph.vs[nei]["mod_name"] for nei in self.graph.successors(v.index)]
            print(f"{v['mod_name']} requires {deps if deps else 'nothing'}")

    def summary(self) -> str:
        """Return a summary string of the current graph.

        Returns:
            str: A textual summary of the graph including node and edge counts.
        """
        return self.graph.summary()

    def save(self, graphml_path: Optional[str] = None, meta_path: Optional[str] = None) -> None:
        """Save the graph and optional metadata to files.

        Args:
            graphml_path (Optional[str]): Path to save the graph in compressed GraphML format (.graphml).
            meta_path (Optional[str]): Path to save the mod metadata as a JSON file.

        Raises:
            ValueError: If neither `graphml_path` nor `meta_path` is specified.
            ValueError: If `graphml_path` does not end with `.graphml`.
        """
        if not graphml_path and not meta_path:
            raise ValueError("Must specify between graphml_path or meta_path")

        if graphml_path:
            if not graphml_path.endswith(".graphml"):
                raise ValueError("Graph file must have a .graphml extension.")
            self.graph.write_graphmlz(graphml_path)

        if meta_path and self.mod_data:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(self.mod_data, f, indent=2)

    @classmethod
    def load(cls, graphml_path: Optional[str] = None, meta_path: Optional[str] = None) -> "ZomboidModGraph":
        """Load a graph and optional metadata from files.

        Args:
            graphml_path (Optional[str]): Path to a saved .graphml file.
            meta_path (Optional[str]): Path to a saved mod metadata .json file.

        Returns:
            ZomboidModGraph: An instance of the class with the loaded graph and/or metadata.

        Raises:
            ValueError: If neither path is specified or if `graphml_path` has invalid extension.
            FileNotFoundError: If the specified `graphml_path` does not exist.
        """
        if not graphml_path and not meta_path:
            raise ValueError("Must specify between graphml_path or meta_path")

        instance = cls()

        if graphml_path:
            if not graphml_path.endswith(".graphml"):
                raise ValueError("Graph file must have a .graphml extension.")
            if not Path(graphml_path).exists():
                raise FileNotFoundError(f"Graph file not found: {graphml_path}")
            instance.graph = ig.Graph.Read_GraphMLz(graphml_path)

        if meta_path and Path(meta_path).exists():
            with open(meta_path, encoding="utf-8") as f:
                instance.mod_data = json.load(f)
                instance._build_graph()

        return instance

    def update_by_metadata(self, new_mod_data: Dict[str, dict]) -> None:
        """Update the graph with new or updated mod metadata.

        Adds new nodes and edges for new mods and their dependencies,
        or updates existing nodes' attributes.

        Args:
            new_mod_data (Dict[str, dict]): New mod metadata to be merged into the graph.
        """
        existing_nodes = set(self.graph.vs["name"]) if self.graph.vcount() > 0 else set()

        for workshop_id, data in new_mod_data.items():
            # Update or insert mod data
            self.mod_data[workshop_id] = data

            # Add node if not exists
            if workshop_id not in existing_nodes:
                self.graph.add_vertex(
                    name=workshop_id,
                    mod_name=data.get("mod_name", ""),
                    url=data.get("url", ""),
                    mod_id=data.get("mod_id", []),
                )
                existing_nodes.add(workshop_id)
            else:
                # Update attributes
                v = self.graph.vs.find(name=workshop_id)
                v["mod_name"] = data.get("mod_name", "")
                v["url"] = data.get("url", "")
                v["mod_id"] = data.get("mod_id", [])

            # Add edges for dependencies
            required_ids = data.get("required", [])
            for dep_id in required_ids:
                if dep_id not in existing_nodes:
                    self.graph.add_vertex(name=dep_id, mod_name="", url="", mod_id=[])
                    existing_nodes.add(dep_id)

                source_idx = self.graph.vs.find(name=workshop_id).index
                target_idx = self.graph.vs.find(name=dep_id).index

                if not self.graph.are_connected(source_idx, target_idx):
                    self.graph.add_edge(source_idx, target_idx)

    def to_dict(self) -> dict:
        """Reconstruct the internal `mod_data` dictionary from the current state of the graph.

        Useful if the graph has been modified externally or loaded from GraphML and needs to
        regenerate the associated metadata.
        """
        mod_data = {}
        for v in self.graph.vs:
            required = [self.graph.vs[edge.target]["name"] for edge in self.graph.es.select(_source=v.index)]
            mod_data[v["name"]] = {
                "url": v["url"] if "url" in v.attributes() else "",
                "mod_name": v["mod_name"] if "mod_name" in v.attributes() else "",
                "workshop_id": v["name"],
                "mod_id": v["mod_id"] if "mod_id" in v.attributes() else [],
                "required": required,
            }
        return mod_data
