import networkx as nx
import json
import os

class DAGValidator:
    def validate(self, json_data, video_id):
        G = nx.DiGraph()
        concepts = json_data.get("concepts", [])

        # Support both integer IDs and string names in prerequisites
        name_to_id = {c["standard_term"].lower(): c["id"] for c in concepts}
        valid_ids  = {c["id"] for c in concepts}

        def _resolve(prereq):
            if isinstance(prereq, int):
                return prereq if prereq in valid_ids else None
            return name_to_id.get(str(prereq).lower())

        # Build the graph logically
        for concept in concepts:
            G.add_node(concept["id"])
            for raw_prereq in concept.get("prerequisites", []):
                prereq_id = _resolve(raw_prereq)
                if prereq_id is not None and prereq_id != concept["id"]:
                    G.add_edge(prereq_id, concept["id"])

        # Check for cycles
        is_dag = nx.is_directed_acyclic_graph(G)
        
        if not is_dag:
            cycles = list(nx.simple_cycles(G))
            print(f"  [!] VALIDATION FAILED for {video_id}: Circular dependency detected! Cycles: {cycles}")
            return False, cycles
        
        print(f"  [✓] VALIDATION PASSED for {video_id}: No circular loops found.")
        return True, []