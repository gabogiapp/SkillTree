import unittest
from fastapi.testclient import TestClient

from backend.main import app, graph_engine, bridge_engine
from backend.services.bridge_engine import SYSTEM_PROMPT_SYNTHESIZE


class TestNodeSynthesis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        graph_engine.load_ground_truth()
        cls.client = TestClient(app)

    def test_01_system_prompt_contents(self):
        """Verify the exact prompt requirements."""
        self.assertIn("determinist Graph API", SYSTEM_PROMPT_SYNTHESIZE)
        self.assertIn("synthesized_node", SYSTEM_PROMPT_SYNTHESIZE)
        self.assertIn("Do not output generic combinations", SYSTEM_PROMPT_SYNTHESIZE)

    def test_02_synthesize_skills_new_pair_then_cache_hit(self):
        """
        Verify Many-to-1 Node Synthesis:
        1. Synthesizes painting + computer coding into an emergent hybrid (e.g. Creative Coding).
        2. Merges Node C and two edges (painting -> C, computer coding -> C) into graph database.
        3. Immediate second call queries cache and returns cached == True.
        """
        payload = {
            "source_node_1": "painting",
            "source_node_2": "computer-coding",
        }

        # 1. First synthesis: cache miss -> generates hybrid and writes to graph
        res1 = self.client.post("/api/synthesize-skills", json=payload)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()

        self.assertIn("synthesized_node", data1)
        synth_node = data1["synthesized_node"]
        self.assertTrue(len(synth_node["label"]) > 0)
        self.assertEqual(data1["cached"], False)
        self.assertEqual(len(data1["edges"]), 2)

        # Check edge directions: source1 -> C and source2 -> C
        edge_sources = {e["source"] for e in data1["edges"]}
        edge_targets = {e["target"] for e in data1["edges"]}
        self.assertIn("painting", edge_sources)
        self.assertIn("computer-coding", edge_sources)
        self.assertIn(synth_node["id"], edge_targets)

        print(f"\n[Test Synthesis] '{data1['source_node_1']['label']}' + '{data1['source_node_2']['label']}' -> '{synth_node['label']}'")

        # 2. Second synthesis: must hit cache immediately
        res2 = self.client.post("/api/synthesize-skills", json=payload)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertTrue(data2["cached"], "Second call must hit the database caching layer")
        self.assertEqual(data2["synthesized_node"]["id"], synth_node["id"])
        print(f"[Test Synthesis Cache] Hit cache for hybrid '{data2['synthesized_node']['label']}' (0 tokens)")

    def test_03_synthesize_validation_errors(self):
        """Verify validation errors on empty or identical nodes."""
        # Empty payload
        res_empty = self.client.post("/api/synthesize-skills", json={"source_node_1": "", "source_node_2": "painting"})
        self.assertEqual(res_empty.status_code, 400)

        # Identical nodes
        res_same = self.client.post("/api/synthesize-skills", json={"source_node_1": "painting", "source_node_2": "painting"})
        self.assertEqual(res_same.status_code, 400)


if __name__ == "__main__":
    unittest.main()
