import os
import unittest
from pathlib import Path

from backend.config import settings
from backend.services.graph_engine import GraphEngine, slugify
from backend.services.bridge_engine import BridgeEngine
from backend.models.schemas import IntermediateNode, ConnectingEdge, BridgeResponse


class TestGraphAndBridgeEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize Graph Engine with the datasets
        cls.graph_engine = GraphEngine(settings.CSV_PATHS)
        cls.edges_count = cls.graph_engine.load_ground_truth()
        cls.bridge_engine = BridgeEngine(cls.graph_engine)

    def test_01_slugify_robustness(self):
        self.assertEqual(slugify("Normalise Data"), "normalise-data")
        self.assertEqual(slugify("C++ & Python: Web Dev!"), "c-plus-plus-and-python-web-dev")
        self.assertEqual(slugify("  AI / Machine Learning  "), "ai-machine-learning")
        self.assertEqual(slugify(""), "")

    def test_02_graph_loading(self):
        stats = self.graph_engine.get_stats()
        self.assertGreater(stats.total_nodes, 1000, "Graph should load at least 1,000 nodes")
        self.assertGreater(stats.total_edges, 1000, "Graph should load at least 1,000 edges")
        self.assertEqual(stats.ground_truth_nodes, stats.total_nodes)
        self.assertEqual(stats.ai_generated_nodes, 0)
        print(f"\n[Test] Loaded {stats.total_nodes} nodes and {stats.total_edges} edges from {settings.CSV_PATH.name} successfully.")

    def test_03_fuzzy_search(self):
        # Search for a skill in the dataset
        results = self.graph_engine.search_skills("painting", limit=5)
        self.assertGreater(results.total_matches, 0)
        top = results.results[0]
        self.assertIn("painting", top.label.lower())
        print(f"[Test] Fuzzy search for 'painting' found {len(results.results)} matches. Top: '{top.label}' (id: {top.id})")

    def test_04_neighbors_retrieval(self):
        # "painting" -> "oil painting"
        parent_id = slugify("painting")
        neighbors = self.graph_engine.get_neighbors(parent_id)
        self.assertIsNotNone(neighbors)
        self.assertTrue(len(neighbors.unlocked) > 0 or len(neighbors.prerequisites) > 0)
        print(f"[Test] Neighbors of '{parent_id}': {len(neighbors.prerequisites)} prereqs, {len(neighbors.unlocked)} unlocked.")

    def test_05_ground_truth_pathfinding(self):
        # Direct relationship from CSV: "painting" -> "oil painting"
        start_id = slugify("painting")
        target_id = slugify("oil painting")
        found, nodes, edges = self.graph_engine.find_path(start_id, target_id)
        self.assertTrue(found, "Should find direct path between connected skills")
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(edges), 1)
        self.assertTrue(nodes[0].is_ground_truth)
        self.assertTrue(edges[0].is_ground_truth)
        print(f"[Test] Direct path found: {nodes[0].label} -> {nodes[1].label}")

    def test_06_bridge_synthesizer_disconnected_skills(self):
        # Disconnected skills: "painting" and "computer coding"
        start_id = slugify("painting")
        target_id = slugify("computer coding")

        # Verify disconnected initially
        direct_found, _, _ = self.graph_engine.find_path(start_id, target_id)
        self.assertFalse(direct_found, "Skills should not have a direct path initially")

        # Call Bridge Engine
        response = self.bridge_engine.bridge_pathway(start_id, target_id)
        self.assertTrue(response.found)
        self.assertEqual(response.path_type, "DIRECTED_SYNTHESIZED")
        self.assertGreater(len(response.nodes), 2)
        self.assertGreater(response.synthesized_count, 0)

        # Verify start and target nodes
        self.assertEqual(response.nodes[0].id, start_id)
        self.assertEqual(response.nodes[-1].id, target_id)

        # Verify synthesized nodes flagged is_ground_truth=False
        synth_nodes = [n for n in response.nodes if not n.is_ground_truth]
        self.assertTrue(len(synth_nodes) > 0)
        print(f"[Test] Synthesized Bridge: {[n.label for n in response.nodes]}")
        print(f"[Test] Number of AI-generated stepping stones: {len(synth_nodes)}")

        # Verify graph now finds the path via standard pathfinder
        recheck_found, recheck_nodes, recheck_edges = self.graph_engine.find_path(start_id, target_id)
        self.assertTrue(recheck_found, "Graph must now contain the merged path")
        self.assertEqual(len(recheck_nodes), len(response.nodes))

    def test_07_infinite_craft_frontier_expansion(self):
        skill_id = slugify("singing")
        expansion = self.bridge_engine.expand_frontier(skill_id, count=3)
        self.assertIsNotNone(expansion)
        self.assertGreater(len(expansion.new_nodes) + len(expansion.linked_existing_nodes), 0)
        self.assertGreater(len(expansion.new_edges), 0)
        print(f"[Test] Frontier expanded for '{skill_id}': discovered {len(expansion.new_nodes)} new skills, {len(expansion.linked_existing_nodes)} linked existing skills.")


if __name__ == "__main__":
    unittest.main()
