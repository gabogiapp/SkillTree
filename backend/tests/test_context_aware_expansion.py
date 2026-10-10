import unittest
from fastapi.testclient import TestClient

from backend.main import app, graph_engine, bridge_engine
from backend.services.graph_engine import slugify


class TestContextAwareExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        graph_engine.load_ground_truth()
        cls.client = TestClient(app)

    def test_01_graph_neighborhood_injection(self):
        # 1. Test existing child node in graph (e.g. "oil painting" has parent "painting")
        ctx_oil = graph_engine.get_graph_neighborhood_context("oil-painting")
        self.assertIn("painting", ctx_oil.lower())
        self.assertIn("oil painting", ctx_oil.lower())
        print(f"\n[Test Context] Neighborhood for 'oil-painting': {ctx_oil}")

        # 2. Test "Python" has parent "computer coding"
        ctx_python = graph_engine.get_graph_neighborhood_context("python")
        self.assertIn("computer coding", ctx_python.lower())
        print(f"[Test Context] Neighborhood for 'python': {ctx_python}")

    def test_02_expansion_italian_language_no_tech_hallucination(self):
        # The user's exact scenario: An ambiguous node "Italian"
        # Injected with Language context: "[Language Skills -> Spoken Languages -> Italian]"
        domain_ctx = "[Language Skills -> Spoken Languages -> Italian]"
        italian_id = slugify("Italian")

        res = bridge_engine.expand_frontier(
            skill_id=italian_id,
            count=3,
            domain_context=domain_ctx,
        )

        self.assertIsNotNone(res)
        self.assertEqual(res.domain_context, domain_ctx)

        generated_labels = [n.label for n in res.new_nodes]
        print(f"\n[Test Language Expansion] Generated skills for 'Italian' in context {domain_ctx}:")
        for g in generated_labels:
            print(f"  - {g}")

        # Verify NO corporate or tech jargon
        for label in generated_labels:
            lower = label.lower()
            self.assertNotIn("systems integration", lower)
            self.assertNotIn("automation", lower)
            self.assertNotIn("distributed", lower)
            self.assertNotIn("toolchain", lower)

        # Verify language-appropriate terms (vocabulary, grammar, fluency, pronunciation, reading, etc.)
        all_text = " ".join(generated_labels).lower()
        has_language_terms = any(term in all_text for term in ["vocabulary", "grammar", "fluency", "comprehension", "literature", "phonics", "idiom", "italian", "spoken", "sentence"])
        self.assertTrue(has_language_terms, f"Generated skills must align with Language Domain. Got: {generated_labels}")

    def test_03_api_route_context_aware_expansion(self):
        # Test API endpoint injects neighborhood context and returns it
        res = self.client.post("/api/skills/oil-painting/expand", json={"count": 3})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("domain_context", data)
        self.assertTrue(len(data["domain_context"]) > 0)
        print(f"\n[Test API Expand] Oil painting domain_context returned: {data['domain_context']}")

        # Ensure no tech jargon in painting
        for n in data["new_nodes"]:
            lower = n["label"].lower()
            self.assertNotIn("systems integration", lower)
            self.assertNotIn("automation", lower)


if __name__ == "__main__":
    unittest.main()
