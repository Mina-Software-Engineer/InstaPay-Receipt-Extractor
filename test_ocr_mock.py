import os
import unittest
from unittest.mock import MagicMock, patch
from services import OcrService

class TestOcrServiceMock(unittest.TestCase):
    @patch('services.genai.Client')
    def test_process_receipt_mock(self, mock_genai_client_class):
        # Setup mock client response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '''
        {
          "money_value": "70",
          "account_name": "mina_remon@instapay",
          "account_number": "BASEL TAMER MOHAMED HASSAN ATTAYA",
          "receipt_number": "957116232041",
          "receipt_date": "01 Aug 2026 08:06 PM",
          "note": "Living Expenses"
        }
        '''
        mock_client.models.generate_content.return_value = mock_response
        mock_genai_client_class.return_value = mock_client

        image_path = "/home/ubuntu/upload/w.jpeg"
        if not os.path.exists(image_path):
            self.skipTest("Sample receipt image w.jpeg not found.")

        result = OcrService.process_receipt(image_path, api_key="dummy_key")

        self.assertEqual(result["money_value"], "70")
        self.assertEqual(result["account_name"], "mina_remon@instapay")
        self.assertEqual(result["account_number"], "BASEL TAMER MOHAMED HASSAN ATTAYA")
        self.assertEqual(result["receipt_number"], "957116232041")
        self.assertEqual(result["receipt_date"], "01 Aug 2026 08:06 PM")
        self.assertEqual(result["note"], "Living Expenses")
        print("Mock OCR Extraction verification passed successfully!")

if __name__ == "__main__":
    unittest.main()
