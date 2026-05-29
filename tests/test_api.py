import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from fastapi.testclient import TestClient

# Override base settings before loading app to use test files
os.environ["DATABASE_PATH"] = "data/test_cognitum.db"
os.environ["PROFILES_DIR"] = "data/test_profiles"
os.environ["POLICIES_DIR"] = "data/test_policies"

from cognitum.main import app
from cognitum.core.profile_store import Profile
from cognitum.core.policy_gate import Policy
from cognitum.core.planner import Plan, PlanStep

class TestCognitumAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        
    def setUp(self):
        # Cleanup test files before each test
        for path_str in [
            "data/test_cognitum.db",
            "data/test_profiles/default.yaml",
            "data/test_policies/default.yaml"
        ]:
            p = Path(path_str)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
                
    def tearDown(self):
        # Cleanup test files after each test
        for path_str in [
            "data/test_cognitum.db",
            "data/test_profiles/default.yaml",
            "data/test_policies/default.yaml"
        ]:
            p = Path(path_str)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
        # Clean up temp test directories if empty
        for dir_str in ["data/test_profiles", "data/test_policies"]:
            d = Path(dir_str)
            if d.exists():
                try:
                    d.rmdir()
                except Exception:
                    pass


    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("cpu_percent", data)
        self.assertIn("memory_percent", data)

    def test_profile_get_and_post(self):
        # Test GET
        get_resp = self.client.get("/profile")
        self.assertEqual(get_resp.status_code, 200)
        profile_data = get_resp.json()
        self.assertEqual(profile_data["name"], "Thiago")
        
        # Test POST update
        new_profile = {
            "name": "Thiago Updated",
            "timezone": "America/New_York",
            "preferences": {"explanations": "English"},
            "objectives": ["Test active objectives"]
        }
        post_resp = self.client.post("/profile", json=new_profile)
        self.assertEqual(post_resp.status_code, 200)
        self.assertEqual(post_resp.json()["name"], "Thiago Updated")
        
        # Verify changes persisted
        get_resp_updated = self.client.get("/profile")
        self.assertEqual(get_resp_updated.json()["name"], "Thiago Updated")

    def test_policy_get_and_check(self):
        # Test GET
        get_resp = self.client.get("/policy")
        self.assertEqual(get_resp.status_code, 200)
        policy_data = get_resp.json()
        self.assertTrue(policy_data["safety_gate_enabled"])
        
        # Test POST check allowed action
        check_payload = {
            "action_type": "read_file",
            "parameters": {"path": "cognitum/config.py"}
        }
        resp = self.client.post("/policy/check", json=check_payload)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["safe"])
        
        # Test POST check denied command
        check_payload_denied = {
            "action_type": "run_command",
            "parameters": {"command": "rm -rf /"}
        }
        resp_denied = self.client.post("/policy/check", json=check_payload_denied)
        self.assertEqual(resp_denied.status_code, 200)
        self.assertFalse(resp_denied.json()["safe"])
        self.assertIn("forbidden keyword", resp_denied.json()["reason"])

    def test_memory_store_and_search(self):
        # Store a memory
        store_payload = {
            "content": "COGNITUM is configured with gemini-2.5-flash",
            "memory_type": "note.idea",
            "metadata": {"tags": ["architecture", "gemini"]}
        }
        resp_store = self.client.post("/memory/store", json=store_payload)
        self.assertEqual(resp_store.status_code, 200)
        self.assertTrue(resp_store.json()["success"])
        self.assertIn("event_id", resp_store.json())
        
        # Search for it
        search_resp = self.client.get("/memory/search?query=configured")
        self.assertEqual(search_resp.status_code, 200)
        results = search_resp.json()["results"]
        self.assertGreater(len(results), 0)
        self.assertIn("gemini-2.5-flash", results[0]["content"])

    @patch("cognitum.api.plan.generate_plan")
    def test_plan_generation(self, mock_generate_plan):
        # Mocking plan response structure
        mock_plan = Plan(
            goal="Configure project environment",
            steps=[
                PlanStep(step_number=1, description="Copy template env", tool_recommendation="cp .env.example .env", expected_outcome="Local .env exists"),
                PlanStep(step_number=2, description="Populate secret variables", expected_outcome="Env variables set")
            ],
            reasoning="Simple setup sequence",
            required_contexts=[".env.example"]
        )
        mock_generate_plan.return_value = mock_plan
        
        plan_payload = {
            "goal": "Configure project environment",
            "use_context": True
        }
        resp = self.client.post("/plan", json=plan_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["goal"], "Configure project environment")
        self.assertEqual(len(data["steps"]), 2)
        self.assertEqual(data["steps"][0]["tool_recommendation"], "cp .env.example .env")

    def test_context_assembly(self):
        context_payload = {"query": "configured"}
        resp = self.client.post("/context", json=context_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("profile", data)
        self.assertIn("policy", data)
        self.assertIn("system_metrics", data)
        self.assertIn("memories", data)

if __name__ == "__main__":
    unittest.main()
