"""
Study Path Generator — Phase 6 of the Pedagogical Flow Extraction Pipeline.

Consumes the validated DAG JSON produced by Phase 4 and emits a structured
JSON document that describes:
  • A single recommended (topologically sorted) learning sequence
  • Parallel learning groups (concepts that share no dependency — learnable
    simultaneously)
  • Per-concept ordering explanations
  • Separate handling of disconnected graph components
"""

import json
import os
from collections import deque

import networkx as nx


class StudyPathGenerator:
    """Generates recommended study paths from a concept DAG."""

    #  Public API                                     

    def generate(self, json_data: dict, topic_id: str) -> dict:
        """
        Build a study-path report from a validated DAG JSON.

        Parameters
        ----------
        json_data : dict
            Structured data as produced by ConceptExtractor — must contain
            a ``"concepts"`` list where each item has at least:
            ``id``, ``standard_term``, ``description``,
            ``prerequisites`` (list of IDs), ``relative_importance``.
        topic_id : str
            Identifier used for labelling (e.g. "deadlock_os").

        Returns
        -------
        dict
            Fully structured study-path output (see module docstring).
        """
        concepts = json_data.get("concepts", [])
        if not concepts:
            return {"error": "No concepts found in the provided data."}

        G = self._build_graph(concepts)
        id_to_concept = {c["id"]: c for c in concepts}

        # ── 1. Single recommended sequence (standard topo-sort) ──────── #
        try:
            topo_order = list(nx.topological_sort(G))
        except nx.NetworkXUnfeasible:
            return {"error": "Graph contains a cycle — cannot produce a study path."}

        recommended_sequence = self._build_sequence(topo_order, id_to_concept, G)

        # ── 2. Parallel learning groups (BFS level-by-level) ─────────── #
        parallel_groups = self._build_parallel_groups(G, id_to_concept)

        # ── 3. Disconnected components ───────────────────────────────── #
        components = self._build_components(G, id_to_concept)

        # ── 4. Assemble final output ──────────────────────────────────── #
        result = {
            "topic": topic_id,
            "video_summary": json_data.get("video_summary", ""),
            "total_concepts": len(concepts),
            "recommended_sequence": recommended_sequence,
            "parallel_groups": parallel_groups,
            "components": components,
            "metadata": {
                "algorithm": "Kahn's BFS topological sort",
                "handles_disconnected_components": True,
                "total_parallel_groups": len(parallel_groups),
                "total_components": len(components),
            },
        }
        return result

    #  Private helpers                                               

    @staticmethod
    def _build_graph(concepts: list) -> nx.DiGraph:
        """Construct a NetworkX DiGraph from the concepts list.

        Handles prerequisites given as either integer IDs or string names,
        so phantom duplicate nodes are never created.
        """
        G = nx.DiGraph()
        name_to_id = {c["standard_term"].lower(): c["id"] for c in concepts}
        valid_ids  = {c["id"] for c in concepts}

        for c in concepts:
            G.add_node(c["id"])

        for c in concepts:
            for raw_prereq in c.get("prerequisites", []):
                if isinstance(raw_prereq, int):
                    prereq_id = raw_prereq if raw_prereq in valid_ids else None
                else:
                    prereq_id = name_to_id.get(str(raw_prereq).lower())
                if prereq_id is not None and prereq_id != c["id"]:
                    # prereq → concept  (prerequisite must come first)
                    G.add_edge(prereq_id, c["id"])
        return G

    def _build_sequence(
        self,
        topo_order: list,
        id_to_concept: dict,
        G: nx.DiGraph,
    ) -> list:
        """
        Annotate every node in topological order with a human-readable
        explanation of *why* it comes at that position.
        """
        sequence = []
        for step, node_id in enumerate(topo_order, start=1):
            concept = id_to_concept.get(node_id, {})
            prereq_ids = list(G.predecessors(node_id))
            successor_ids = list(G.successors(node_id))

            explanation = self._explain_position(
                concept, prereq_ids, successor_ids, id_to_concept
            )

            sequence.append(
                {
                    "step": step,
                    "concept_id": node_id,
                    "concept": concept.get("standard_term", str(node_id)),
                    "description": concept.get("description", ""),
                    "relative_importance": concept.get("relative_importance", 5),
                    "prerequisites": [
                        id_to_concept[p]["standard_term"]
                        for p in prereq_ids
                        if p in id_to_concept
                    ],
                    "unlocks": [
                        id_to_concept[s]["standard_term"]
                        for s in successor_ids
                        if s in id_to_concept
                    ],
                    "reason": explanation,
                }
            )
        return sequence

    @staticmethod
    def _explain_position(
        concept: dict,
        prereq_ids: list,
        successor_ids: list,
        id_to_concept: dict,
    ) -> str:
        """Generate a one-sentence rationale for the ordering decision."""
        name = concept.get("standard_term", "This concept")
        importance = concept.get("relative_importance", 5)

        if not prereq_ids:
            if not successor_ids:
                return (
                    f"'{name}' is an isolated foundational concept with no "
                    "prerequisites and no dependents."
                )
            unlocks = [
                id_to_concept[s]["standard_term"]
                for s in successor_ids
                if s in id_to_concept
            ]
            return (
                f"'{name}' is a root concept (no prerequisites) and must be "
                f"understood first because it directly enables: "
                f"{', '.join(unlocks)}."
            )

        prereq_names = [
            id_to_concept[p]["standard_term"]
            for p in prereq_ids
            if p in id_to_concept
        ]
        base = (
            f"'{name}' builds upon {', '.join(prereq_names)} "
            f"(importance {importance}/10)"
        )

        if successor_ids:
            unlocks = [
                id_to_concept[s]["standard_term"]
                for s in successor_ids
                if s in id_to_concept
            ]
            return base + f" and is required before studying: {', '.join(unlocks)}."
        return base + " and is a terminal concept in this learning path."

    @staticmethod
    def _build_parallel_groups(G: nx.DiGraph, id_to_concept: dict) -> list:
        """
        Level-by-level BFS (Kahn's algorithm) to identify concepts that can
        be studied simultaneously within each level.
        """
        in_degree = {node: G.in_degree(node) for node in G.nodes()}
        queue = deque(
            node for node, deg in in_degree.items() if deg == 0
        )
        groups = []
        level = 1

        while queue:
            level_size = len(queue)
            level_concepts = []

            for _ in range(level_size):
                node = queue.popleft()
                concept = id_to_concept.get(node, {})
                level_concepts.append(
                    {
                        "concept_id": node,
                        "concept": concept.get("standard_term", str(node)),
                        "relative_importance": concept.get("relative_importance", 5),
                    }
                )
                for successor in G.successors(node):
                    in_degree[successor] -= 1
                    if in_degree[successor] == 0:
                        queue.append(successor)

            level_label = (
                "Foundation"
                if level == 1
                else f"Level {level}"
            )
            note = (
                "These are entry-point concepts — start here."
                if level == 1
                else (
                    f"All {len(level_concepts)} concept(s) at this level can be "
                    "studied in parallel once the previous level is complete."
                    if len(level_concepts) > 1
                    else "Study after completing the previous level."
                )
            )

            groups.append(
                {
                    "group": level,
                    "level_label": level_label,
                    "concepts": level_concepts,
                    "parallel_count": len(level_concepts),
                    "note": note,
                }
            )
            level += 1

        return groups

    @staticmethod
    def _build_components(G: nx.DiGraph, id_to_concept: dict) -> list:
        """
        Detect weakly-connected components and return a separate
        topological sequence for each one.
        """
        components = []
        undirected = G.to_undirected()

        for comp_idx, node_set in enumerate(
            nx.connected_components(undirected), start=1
        ):
            subgraph = G.subgraph(node_set)
            try:
                sub_topo = list(nx.topological_sort(subgraph))
            except nx.NetworkXUnfeasible:
                sub_topo = list(node_set)  # fallback; cycle should not reach here

            sequence = [
                {
                    "step": i,
                    "concept_id": nid,
                    "concept": id_to_concept.get(nid, {}).get(
                        "standard_term", str(nid)
                    ),
                }
                for i, nid in enumerate(sub_topo, start=1)
            ]

            components.append(
                {
                    "component_id": comp_idx,
                    "concept_count": len(node_set),
                    "is_isolated": len(node_set) == 1,
                    "sequence": sequence,
                }
            )

        return components


#  Stand-alone utility — generate & save path for an existing JSON file    

def generate_and_save(json_path: str, output_dir: str = "output/study_paths") -> str:
    """
    Load a structured-data JSON, generate its study path, and write the
    result to ``output_dir/<topic_id>_study_path.json``.

    Returns the path to the written file.
    """
    os.makedirs(output_dir, exist_ok=True)
    topic_id = os.path.splitext(os.path.basename(json_path))[0]

    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    generator = StudyPathGenerator()
    result = generator.generate(json_data, topic_id)

    out_path = os.path.join(output_dir, f"{topic_id}_study_path.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    return out_path
