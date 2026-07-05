import base64
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response
from google.cloud import bigquery, storage
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Document OCR Processor")

# Initialize GCP clients
# Note: Clients will automatically authenticate using Application Default Credentials (ADC)
# or the service account associated with the Cloud Run service.
try:
    storage_client = storage.Client()
    bq_client = bigquery.Client()
    logger.info("GCP clients initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing GCP clients: {e}")
    # In local development, these might fail if not authenticated, which is handled gracefully.
    storage_client = None
    bq_client = None

# Retrieve environment variables
PROJECT_ID = os.getenv("PROJECT_ID")
DATASET_NAME = os.getenv("DATASET_NAME", "doc_processing")
TABLE_NAME = os.getenv("TABLE_NAME", "metadata")

@app.get("/health")
def health_check():
    """Health check endpoint for Cloud Run container status."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gcp_configured": storage_client is not None and bq_client is not None
    }

def simulate_ocr(file_content: bytes, filename: str) -> Dict[str, Any]:
    """Simulates OCR processing, extracting word count and tags from file contents."""
    logger.info(f"Running simulated OCR on: {filename}")
    
    file_ext = os.path.splitext(filename)[1].lower().strip(".")
    tags = []
    if file_ext:
        tags.append(file_ext)
        
    text_content = ""
    try:
        # Attempt to decode as UTF-8 text for analysis
        text_content = file_content.decode("utf-8")
    except UnicodeDecodeError:
        # Binary file (e.g. PDF, Image); use simulated content representation
        logger.info(f"Non-text file detected: {filename}. Simulating text extraction.")
        text_content = f"Simulated binary content for {filename}"

    # Calculate word count
    words = re.findall(r"\b\w+\b", text_content)
    word_count = len(words)
    
    # If binary, generate a pseudo-random word count based on file size
    if not text_content.startswith("Simulated binary content") and word_count == 0:
        word_count = max(1, len(file_content) // 10)
    elif text_content.startswith("Simulated binary content"):
        word_count = max(15, len(file_content) // 25)

    # Keywords for extracting semantic tags
    keyword_map = {
        "invoice": ["invoice", "bill", "payment", "amount", "charge"],
        "receipt": ["receipt", "transaction", "purchase", "store", "cashier"],
        "contract": ["contract", "agreement", "parties", "terms", "signatures", "hereby"],
        "report": ["report", "analysis", "summary", "finding", "result"],
        "resume": ["resume", "cv", "education", "experience", "skills", "employment"],
        "code": ["import", "class", "def", "function", "const", "let", "html", "css"]
    }
    
    content_lower = text_content.lower()
    for tag_name, keywords in keyword_map.items():
        if any(keyword in content_lower for keyword in keywords):
            tags.append(tag_name)
            
    # Default tags if nothing matched
    if len(tags) <= 1: # Only contains the extension tag
        tags.append("document")

    # De-duplicate tags
    tags = list(set(tags))
    
    return {
        "word_count": word_count,
        "tags": tags
    }

def stream_metadata_to_bigquery(filename: str, tags: List[str], word_count: int) -> None:
    """Streams extracted metadata into the BigQuery table using tabledata.insertAll."""
    if not bq_client:
        logger.warning("BigQuery client not initialized. Skipping BigQuery insertion.")
        return

    table_id = f"{PROJECT_ID}.{DATASET_NAME}.{TABLE_NAME}"
    
    row_to_insert = {
        "filename": filename,
        "date": datetime.now(timezone.utc).isoformat(),
        "tags": tags,
        "word_count": word_count
    }
    
    logger.info(f"Streaming metadata to BigQuery table {table_id}: {row_to_insert}")
    
    errors = bq_client.insert_rows_json(table_id, [row_to_insert])
    if errors:
        logger.error(f"Failed to insert row into BigQuery: {errors}")
        raise HTTPException(
            status_code=500,
            detail=f"Error inserting metadata to BigQuery: {errors}"
        )
    logger.info("Metadata successfully written to BigQuery.")

@app.post("/")
async def process_event(request: Request):
    """Processes incoming GCS event (Eventarc or Pub/Sub push notification)."""
    
    # 1. Parse request body
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse request JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    bucket_name = None
    object_name = None
    
    # Check if request is a Pub/Sub push subscription envelope
    if "message" in body and isinstance(body["message"], dict) and "data" in body["message"]:
        logger.info("Detected Pub/Sub message envelope.")
        try:
            # Decode the base64 Pub/Sub payload
            pubsub_data_raw = base64.b64decode(body["message"]["data"]).decode("utf-8")
            pubsub_data = json.loads(pubsub_data_raw)
            bucket_name = pubsub_data.get("bucket")
            object_name = pubsub_data.get("name")
        except Exception as e:
            logger.error(f"Failed to decode Pub/Sub envelope data: {e}")
            raise HTTPException(status_code=400, detail="Failed to parse base64 Pub/Sub payload")
            
    # Check if request is a CloudEvent (Eventarc)
    else:
        logger.info("Checking for Eventarc / CloudEvent payload.")
        # Eventarc binary mode sends GCS metadata directly in the body
        if "bucket" in body and "name" in body:
            bucket_name = body.get("bucket")
            object_name = body.get("name")
        # Eventarc structured mode nests it under data
        elif "data" in body and isinstance(body["data"], dict):
            bucket_name = body["data"].get("bucket")
            object_name = body["data"].get("name")

    if not bucket_name or not object_name:
        logger.error(f"Could not extract bucket or object name from payload. Payload: {body}")
        raise HTTPException(
            status_code=400, 
            detail="Missing bucket or name in Eventarc/PubSub payload"
        )
        
    logger.info(f"Triggered for file: gs://{bucket_name}/{object_name}")

    # Avoid processing directory placeholder objects
    if object_name.endswith("/"):
        logger.info("Ignoring directory placeholder object.")
        return {"status": "skipped", "reason": "directory placeholder"}

    # 2. Download file content from GCS
    if not storage_client:
        logger.warning("GCS client not initialized. Using fallback mock content.")
        file_content = b"This is a fallback dummy content for testing purposes. It contains an invoice keyword."
    else:
        try:
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(object_name)
            
            # Check if blob exists
            if not blob.exists():
                logger.error(f"Blob gs://{bucket_name}/{object_name} does not exist.")
                raise HTTPException(status_code=404, detail="File not found in GCS")
                
            file_content = blob.download_as_bytes()
            logger.info(f"Downloaded {len(file_content)} bytes from GCS.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error downloading file from GCS: {e}")
            raise HTTPException(status_code=500, detail=f"Error reading file from GCS: {str(e)}")

    # 3. Simulate OCR and extract metadata
    ocr_results = simulate_ocr(file_content, object_name)
    word_count = ocr_results["word_count"]
    tags = ocr_results["tags"]

    logger.info(f"Simulated OCR results - Word Count: {word_count}, Tags: {tags}")

    # 4. Write metadata to BigQuery
    try:
        stream_metadata_to_bigquery(
            filename=object_name,
            tags=tags,
            word_count=word_count
        )
    except Exception as e:
        logger.error(f"Error saving to BigQuery: {e}")
        # Re-raise so caller (Eventarc/PubSub) gets a 500 error and can retry if configured
        raise

    return {
        "status": "success",
        "processed_file": f"gs://{bucket_name}/{object_name}",
        "word_count": word_count,
        "tags": tags
    }
