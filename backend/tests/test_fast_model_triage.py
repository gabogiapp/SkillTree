import json
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app, graph_engine, bridge_engine
from backend.services.bridge_engine import BridgeEngine
from backend.models.schemas import IntermediateNode, ExpandNodeRequest


class TestFastModelTriage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        graph_engine.load_ground_truth()
        cls.client = TestClient(app)

    def test_01_config_constraints(self):
        """Rule 2: Verify strict LLM API constraints in configuration."""
        self.assertEqual(settings.LLM_MAX_TOKENS, 250, "max_tokens must be strictly set to 250")
        self.assertEqual(settings.LLM_TEMPERATURE, 0.3, "temperature must be strictly set to 0.3")

    def test_02_context_injection_limit(self):
        """Rule 3: Verify tight context injection (3-5 immediate parent nodes)."""
        # Node with known parent: oil-painting has parent 'painting'
        ctx_oil = graph_engine.get_immediate_parents_context("oil-painting")
        self.assertTrue(ctx_oil.startswith("Domain Context: ["), f"Should start with 'Domain Context: [', got: {ctx_oil}")
        self.assertTrue(ctx_oil.endswith("]"), f"Should end with ']', got: {ctx_oil}")
        self.assertIn("painting", ctx_oil.lower())

        # Count parents injected in context
        content = ctx_oil.replace("Domain Context: [", "").rstrip("]")
        parents = [p.strip() for p in content.split(",") if p.strip()]
        self.assertLessEqual(len(parents), 5, "Context must not dump more than 5 parents")
        self.assertGreaterEqual(len(parents), 1, "Context must contain at least 1 parent reference")
        print(f"\n[Test Context Limit] Tightly bounded context: {ctx_oil}")

    def test_03_caching_layer_leaf_node_then_hit(self):
        """Rule 1: Leaf node calls LLM/synthesis once, writes to graph, then hits cache on 2nd click."""
        leaf_id = "test-origami-robotics"
        # Ensure fresh leaf node with 0 outgoing edges
        graph_engine.merge_subgraph(
            intermediate_nodes=[
                IntermediateNode(
                    id=leaf_id,
                    label="Origami Robotics",
                    category="Robotics & Paper Craft",
                    description="Kinematic paper mechanisms",
                )
            ],
            connecting_edges=[],
            is_ground_truth=False,
        )
        self.assertEqual(graph_engine.graph.out_degree(leaf_id), 0, "Must start as a leaf node with 0 outgoing edges")

        # First expansion: cache miss (leaf node) -> synthesizes and writes to graph
        res1 = self.client.post(f"/api/skills/{leaf_id}/expand", json={"count": 3})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertFalse(data1.get("cached", False), "First expansion of leaf node must not be cached")
        self.assertGreater(len(data1["new_nodes"]), 0)
        self.assertGreater(len(data1["new_edges"]), 0)

        # Graph should now contain the new outgoing edges written immediately
        self.assertGreater(graph_engine.graph.out_degree(leaf_id), 0, "Graph DB must have written outgoing edges")

        # Second expansion on the same node: must hit cache immediately (0 LLM calls)
        res2 = self.client.post(f"/api/skills/{leaf_id}/expand", json={"count": 3})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertTrue(data2.get("cached", False), "Second expansion must hit the cache")
        self.assertIn("Cache Hit", data2["message"])
        print(f"\n[Test Caching] First expansion: cached={data1['cached']}, Second expansion: cached={data2['cached']}")

    def test_04_caching_layer_ground_truth_hub(self):
        """Rule 1: A ground-truth node with existing outgoing edges hits cache immediately."""
        # 'painting' already has 80 outgoing edges in ground-truth graph
        res = self.client.post("/api/skills/painting/expand", json={"count": 3})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("cached", False), "'painting' has outgoing edges, so it must hit cache immediately")
        self.assertGreater(len(data["new_nodes"]), 0)
        self.assertIn("Cache Hit", data["message"])
        print(f"[Test Cache Hit Hub] Painting hit cache: {len(data['new_nodes'])} cached skills returned")

    def test_05_expand_node_endpoint(self):
        """Deliverable: Verify POST /api/expand-node works with node_id and skill_id."""
        # Test with node_id
        res_node = self.client.post("/api/expand-node", json={"node_id": "painting", "count": 3})
        self.assertEqual(res_node.status_code, 200)
        data_node = res_node.json()
        self.assertEqual(data_node["source_node"]["id"], "painting")
        self.assertTrue(data_node["cached"])

        # Test with skill_id alias
        res_skill = self.client.post("/api/expand-node", json={"skill_id": "painting", "count": 3})
        self.assertEqual(res_skill.status_code, 200)
        data_skill = res_skill.json()
        self.assertEqual(data_skill["source_node"]["id"], "painting")

        # Test validation error on missing id
        res_empty = self.client.post("/api/expand-node", json={})
        self.assertEqual(res_empty.status_code, 400)

    def test_06_malformed_json_resilience(self):
        """Verify robust try/catch handling when LLM returns malformed JSON."""
        test_node = graph_engine.get_node("painting")
        
        # Mock client to return malformed JSON
        mock_choice = MagicMock()
        mock_choice.message.content = "INVALID_NOT_JSON {{{ broken"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(BridgeEngine, "client", new_callable=unittest.mock.PropertyMock) as mock_prop:
            mock_prop.return_value = mock_client
            # Expanding with malformed JSON must not crash; fallback catches it safely
            result = bridge_engine._synthesize_expansion_llm(
                node=test_node,
                graph_neighborhood="Domain Context: [Art]",
                count=3,
                direction="both",
            )
            self.assertIsNotNone(result)
            self.assertGreater(len(result.intermediate_nodes), 0)
            print(f"[Test Malformed JSON Resilience] Handled gracefully without crash, {len(result.intermediate_nodes)} nodes generated.")


if __name__ == "__main__":
    unittest.main()
