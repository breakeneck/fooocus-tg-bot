import unittest
from unittest.mock import MagicMock, patch
import asyncio
import sys
import os

# Add parent directory to path to import logic
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic import FooocusLogic

class TestFooocusLogic(unittest.TestCase):
    def setUp(self):
        self.logic = FooocusLogic()
        self.logic.client = MagicMock()

    def test_get_welcome_message(self):
        msg = self.logic.get_welcome_message()
        self.assertIn("Welcome to the Fooocus AI Bot!", msg)

    def test_get_models_keyboard_data(self):
        self.logic.client.get_models.return_value = ["model1.safetensors", "model2.safetensors"]
        data = self.logic.get_models_keyboard_data()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0], ("model1.safetensors", "model:0"))
        self.assertEqual(data[1], ("model2.safetensors", "model:1"))

    def test_get_model_by_index(self):
        self.logic.client.get_models.return_value = ["model1.safetensors", "model2.safetensors"]
        model = self.logic.get_model_by_index(1)
        self.assertEqual(model, "model2.safetensors")
        
        model = self.logic.get_model_by_index(5)
        self.assertIsNone(model)

    def test_get_image_count_keyboard_data(self):
        data = self.logic.get_image_count_keyboard_data()
        # Should be list of rows
        self.assertTrue(isinstance(data, list))
        # Check first row
        self.assertEqual(data[0][0], ("1", "img_count:1"))

    def test_get_progress_bar(self):
        bar = self.logic.get_progress_bar(50, length=10)
        self.assertIn("█████░░░░░", bar)

    async def async_test_generate_stream(self):
        # Mock client responses
        self.logic.client.generate_image.return_value = {"job_id": "123"}
        
        # Mock query_job to return progress then finish
        # We need 3 returns:
        # 1. Loop: Running
        # 2. Loop: Finished (breaks loop)
        # 3. After loop: Finished (to get result)
        finished_response = {"job_status": "Finished", "job_progress": 100, "job_result": {"base64": "SGVsbG8="}}
        self.logic.client.query_job.side_effect = [
            {"job_status": "Running", "job_progress": 50, "job_stage": "Denoising"},
            finished_response,
            finished_response
        ]

        events = []
        async for event in self.logic.generate_image_stream("test prompt", "model1", 1):
            events.append(event)
        
        # Verify events
        self.assertTrue(any(e["type"] == "status" for e in events))
        self.assertTrue(any(e["type"] == "progress" for e in events))
        self.assertTrue(any(e["type"] == "image" for e in events))

    def test_generate_stream(self):
        asyncio.run(self.async_test_generate_stream())

if __name__ == '__main__':
    unittest.main()
