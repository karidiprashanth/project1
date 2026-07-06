#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -euo pipefail

# Configuration
REGION="${REGION:-us-central1}"
DATASET_NAME="${DATASET_NAME:-doc_processing}"
TABLE_NAME="${TABLE_NAME:-metadata}"

# Retrieve GCP Project Info
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "${PROJECT_ID}" ]; then
  echo "Error: No active GCP project configured. Run 'gcloud config set project <project>' first." >&2
  exit 1
fi

BUCKET_NAME="${BUCKET_NAME:-doc-processing-ingest-${PROJECT_ID}}"
TEST_FILE="test_sample_invoice.txt"

echo "============================================================"
echo "Testing Serverless Event-Driven Pipeline on Google Cloud"
echo "Project ID:  ${PROJECT_ID}"
echo "Bucket Name: gs://${BUCKET_NAME}"
echo "BQ Table:    ${PROJECT_ID}:${DATASET_NAME}.${TABLE_NAME}"
echo "============================================================"

# 1. Create a local sample text file matching OCR trigger keywords
echo "Creating local sample test file: ${TEST_FILE}..."
cat <<EOF > "${TEST_FILE}"
This is a sample document for testing the document processing pipeline.
It contains invoice details and a total amount of \$500.00.
We need to verify that this is correctly classified and indexed in BigQuery.
EOF

# 2. Upload file to the Cloud Storage Bucket
echo "Uploading test file to GCS..."
gcloud storage cp "${TEST_FILE}" "gs://${BUCKET_NAME}/${TEST_FILE}"

# 3. Wait for event processing
echo "Waiting 15 seconds for Eventarc -> Cloud Run -> BigQuery pipeline execution..."
sleep 15

# 4. Query BigQuery for the results
echo "Querying BigQuery table for metadata of ${TEST_FILE}..."
QUERY="SELECT filename, date, tags, word_count FROM \`${PROJECT_ID}.${DATASET_NAME}.${TABLE_NAME}\` WHERE filename = '${TEST_FILE}' ORDER BY date DESC LIMIT 1"
bq query --use_legacy_sql=false --format=pretty "${QUERY}"

# 5. Clean up
echo "Cleaning up local test file..."
rm -f "${TEST_FILE}"

echo "Cleaning up GCS test file..."
gcloud storage rm "gs://${BUCKET_NAME}/${TEST_FILE}"

echo "============================================================"
echo "Test execution complete!"
echo "============================================================"
