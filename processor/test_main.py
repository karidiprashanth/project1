import json
import base64
import unittest
from unittest.mock import MagicMock, patch

# Mock GCP clients before importing main to avoid initialization issues
with patch('google.cloud.storage.Client'), patch('google.cloud.bigquery.Client'):
    import main

class TestDocumentProcessor(unittest.TestCase):

    def test_health_check(self):
        response = main.health_check()
        self.assertEqual(response["status"], "healthy")
        self.assertIn("timestamp", response)

    def test_simulate_ocr_text_file(self):
        text_content = b"This is a contract containing the word invoice and agreement."
        filename = "agreement_doc.txt"
        
        result = main.simulate_ocr(text_content, filename)
        
        self.assertIn("txt", result["tags"])
        self.assertIn("contract", result["tags"])
        self.assertIn("invoice", result["tags"])
        self.assertTrue(result["word_count"] > 0)

    def test_simulate_ocr_binary_file(self):
        # Simulated binary content (PDF signature)
        pdf_content = b"%PDF-1.4 ... binary data ... receipt, bill, amount"
        filename = "receipt.pdf"
        
        result = main.simulate_ocr(pdf_content, filename)
        
        self.assertIn("pdf", result["tags"])
        self.assertIn("receipt", result["tags"])
        self.assertIn("invoice", result["tags"])  # bill/amount map to invoice
        self.assertTrue(result["word_count"] > 0)

    @patch('main.storage_client')
    @patch('main.stream_metadata_to_bigquery')
    def test_process_event_binary_cloudevent(self, mock_bq, mock_storage):
        # Mock storage client download behavior
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = b"Hello world! This is a simple report."
        mock_bucket.blob.return_value = mock_blob
        mock_storage.bucket.return_value = mock_bucket

        # Mock FastAPI request object
        mock_request = MagicMock()
        
        async def mock_json():
            return {
                "bucket": "my-bucket",
                "name": "reports/report.txt"
            }
        mock_request.json = mock_json

        # Run process_event and wait (since it is an async endpoint)
        import asyncio
        response = asyncio.run(main.process_event(mock_request))

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["processed_file"], "gs://my-bucket/reports/report.txt")
        self.assertEqual(response["word_count"], 7)
        self.assertIn("txt", response["tags"])
        self.assertIn("report", response["tags"])

        # Verify BigQuery insertion was called
        mock_bq.assert_called_once()
        args, kwargs = mock_bq.call_args
        self.assertEqual(kwargs["filename"], "reports/report.txt")
        self.assertEqual(kwargs["word_count"], 7)
        self.assertIn("report", kwargs["tags"])

    @patch('main.storage_client')
    @patch('main.stream_metadata_to_bigquery')
    def test_process_event_pubsub_envelope(self, mock_bq, mock_storage):
        # Mock GCS download
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = b"Import python and build a fastapi class."
        mock_bucket.blob.return_value = mock_blob
        mock_storage.bucket.return_value = mock_bucket

        # Base64 encode Pub/Sub GCS event data
        gcs_event_data = {
            "bucket": "another-bucket",
            "name": "scripts/app.py"
        }
        encoded_data = base64.b64encode(json.dumps(gcs_event_data).encode("utf-8")).decode("utf-8")

        mock_request = MagicMock()
        async def mock_json():
            return {
                "message": {
                    "data": encoded_data,
                    "messageId": "12345"
                }
            }
        mock_request.json = mock_json

        import asyncio
        response = asyncio.run(main.process_event(mock_request))

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["processed_file"], "gs://another-bucket/scripts/app.py")
        self.assertIn("py", response["tags"])
        self.assertIn("code", response["tags"])
        
        mock_bq.assert_called_once()

if __name__ == '__main__':
    unittest.main()
