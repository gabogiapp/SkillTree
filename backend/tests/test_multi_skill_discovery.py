import unittest
from fastapi.testclient import TestClient

from backend.main import app, graph_engine
from backend.services.bridge_engine import SYSTEM_PROMPT_MULTI_SKILL_EXPAND


class TestMultiSkillDiscovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        graph_engine.load_ground_truth()
        cls.client = TestClient(app)

    def test_01_multi_skill_system_prompt(self):
        """Verify prompt has multi-skill synthesis and schema constraints."""
        self.assertIn("curriculum architect", SYSTEM_PROMPT_MULTI_SKILL_EXPAND)
        self.assertIn("suggested_skills", SYSTEM_PROMPT_MULTI_SKILL_EXPAND)
        self.assertIn("required_input_skills", SYSTEM_PROMPT_MULTI_SKILL_EXPAND)

    def test_02_suggest_next_steps_from_multiple_skills(self):
        """
        Verify that passing multiple skills suggests new emergent skills
        with directed prerequisite edges pointing from the current skills to the new skills.
        """
        payload = {
            "skill_ids": ["painting", "computer-coding"],
            "count": 3,
        }
        res = self.client.post("/api/skills/suggest-next-steps", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("new_nodes", data)
        self.assertIn("new_edges", data)
        self.assertIn("source_skills", data)
        self.assertTrue(len(data["new_nodes"]) >= 2)
        self.assertTrue(len(data["new_edges"]) >= 2)

        # Verify edge directions: sources must include at least one input skill
        sources = {e["source"] for e in data["new_edges"]}
        self.assertTrue(len(sources.intersection({"painting", "computer-coding"})) > 0)

        # Verify target is among the new nodes
        new_ids = {n["id"] for n in data["new_nodes"]}
        targets = {e["target"] for e in data["new_edges"]}
        self.assertTrue(len(targets.intersection(new_ids)) > 0)

        print(f"\n[Test Multi-Skill] Suggested {len(data['new_nodes'])} skills from {[s['label'] for s in data['source_skills']]}:")
        for n in data["new_nodes"]:
            print(f"  - {n['label']} ({n['category']})")

    def test_03_suggest_next_steps_validation(self):
        """Verify validation error on empty skill_ids."""
        res = self.client.post("/api/skills/suggest-next-steps", json={"skill_ids": []})
        self.assertIn(res.status_code, [400, 422])

