import unittest
from fastapi.testclient import TestClient

from backend.main import app, graph_engine


class TestApiRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Trigger startup manually for test client
        graph_engine.load_ground_truth()
        cls.client = TestClient(app)

    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_stats(self):
        res = self.client.get("/api/graph/stats")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["total_nodes"], 1000)
        self.assertGreater(data["total_edges"], 1000)

    def test_search(self):
        res = self.client.get("/api/skills/search?q=painting&limit=5")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["total_matches"], 0)
        self.assertTrue(any("painting" in r["label"].lower() for r in data["results"]))

    def test_neighbors(self):
        res = self.client.get("/api/skills/painting/neighbors")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("node", data)
        self.assertIn("prerequisites", data)
        self.assertIn("unlocked", data)

    def test_subgraph(self):
        res = self.client.get("/api/graph/subgraph?max_nodes=15")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertLessEqual(len(data["nodes"]), 15)
        self.assertGreater(len(data["nodes"]), 0)

    def test_bridge_endpoint(self):
        payload = {
            "start_skill_id": "painting",
            "target_skill_id": "computer-coding",
        }
        res = self.client.post("/api/skills/bridge", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["found"])
        self.assertEqual(data["path_type"], "DIRECTED_SYNTHESIZED")
        self.assertGreater(len(data["nodes"]), 2)

    def test_expand_endpoint(self):
        payload = {"count": 3, "direction": "both"}
        res = self.client.post("/api/skills/painting/expand", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("new_nodes", data)
        self.assertIn("new_edges", data)

    def test_custom_skill(self):
        payload = {"label": "Digital Illustration", "category": "Art & Design"}
        res = self.client.post("/api/skills/custom", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["label"].lower(), "digital illustration")


    def test_resume_upload(self):
        payload = {
            "resume_text": "Experienced artist with background in painting, watercolor, color mixing, and computer coding.",
        }
        res = self.client.post("/api/skills/upload-resume", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(len(data["matched_skills"]), 0)
        print(f"\n[Test API] Resume parsed: {len(data['matched_skills'])} matched skills: {[s['label'] for s in data['matched_skills']]}")


if __name__ == "__main__":
    unittest.main()
