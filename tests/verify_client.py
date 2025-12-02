import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path to import client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client import FooocusClient

class TestFooocusClient(unittest.TestCase):
    def setUp(self):
        self.client = FooocusClient(base_url="http://test-url:8888")

    @patch('client.requests.get')
    def test_ping(self, mock_get):
        mock_get.return_value.status_code = 200
        self.assertTrue(self.client.ping())
        
        mock_get.return_value.status_code = 500
        self.assertFalse(self.client.ping())

    @patch('client.requests.get')
    def test_get_models(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "model_filenames": ["model1.safetensors", "model2.safetensors"]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        models = self.client.get_models()
        self.assertEqual(models, ["model1.safetensors", "model2.safetensors"])
        mock_get.assert_called_with("http://test-url:8888/v1/engines/all-models", timeout=10)

    @patch('client.requests.post')
    def test_generate_image(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = [{"base64": "fake_base64_data"}]
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.client.generate_image(prompt="test prompt", model_name="test_model")
        
        self.assertEqual(result, [{"base64": "fake_base64_data"}])
        
        # Verify payload
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['prompt'], "test prompt")
        self.assertEqual(kwargs['json']['base_model_name'], "test_model")
        self.assertEqual(kwargs['json']['async_process'], False)

if __name__ == '__main__':
    unittest.main()
