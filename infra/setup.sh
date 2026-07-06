#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -euo pipefail

# Get directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
REGION="${REGION:-us-central1}"
DATASET_NAME="${DATASET_NAME:-doc_processing}"
TABLE_NAME="${TABLE_NAME:-metadata}"
SERVICE_NAME="${SERVICE_NAME:-doc-processor}"

# Retrieve GCP Project Info
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "${PROJECT_ID}" ]; then
  echo "Error: No active GCP project configured. Run 'gcloud config set project <project>' first." >&2
  exit 1
fi

PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
BUCKET_NAME="${BUCKET_NAME:-doc-processing-ingest-${PROJECT_ID}}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-doc-processor-sa}"
TRIGGER_ACCOUNT_NAME="${TRIGGER_ACCOUNT_NAME:-doc-trigger-sa}"

echo "============================================================"
echo "Setting up Serverless Event-Driven Pipeline on Google Cloud"
echo "Project ID:      ${PROJECT_ID}"
echo "Project Number:  ${PROJECT_NUMBER}"
echo "Region:          ${REGION}"
echo "Bucket Name:     gs://${BUCKET_NAME}"
echo "BQ Table:        ${PROJECT_ID}:${DATASET_NAME}.${TABLE_NAME}"
echo "Cloud Run:       ${SERVICE_NAME}"
echo "============================================================"

# 1. Enable Required GCP APIs
echo "Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  pubsub.googleapis.com \
  eventarc.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  logging.googleapis.com \
  iam.googleapis.com \
  cloudbuild.googleapis.com

# 2. Create Cloud Storage Bucket
echo "Creating Cloud Storage bucket..."
if gcloud storage buckets describe "gs://${BUCKET_NAME}" &>/dev/null; then
  echo "Bucket gs://${BUCKET_NAME} already exists."
else
  gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${REGION}"
  echo "Bucket gs://${BUCKET_NAME} created."
fi

# 3. Create BigQuery Dataset and Table
echo "Creating BigQuery dataset..."
if bq show --dataset "${PROJECT_ID}:${DATASET_NAME}" &>/dev/null; then
  echo "Dataset ${DATASET_NAME} already exists."
else
  bq mk --location="${REGION}" --dataset "${PROJECT_ID}:${DATASET_NAME}"
  echo "Dataset ${DATASET_NAME} created."
fi

echo "Creating BigQuery table..."
if bq show "${PROJECT_ID}:${DATASET_NAME}.${TABLE_NAME}" &>/dev/null; then
  echo "Table ${TABLE_NAME} already exists."
else
  # Schema definition:
  # filename: STRING
  # date: TIMESTAMP
  # tags: STRING (repeated/array)
  # word_count: INTEGER
  bq mk --table \
    --time_partitioning_field date \
    --time_partitioning_type DAY \
    "${PROJECT_ID}:${DATASET_NAME}.${TABLE_NAME}" \
    "${SCRIPT_DIR}/schema.json"
  echo "Table ${TABLE_NAME} created."
fi

# 4. Create Service Accounts
echo "Creating Service Accounts..."
# Processor Service Account
if gcloud iam service-accounts describe "${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" &>/dev/null; then
  echo "Service account ${SERVICE_ACCOUNT_NAME} already exists."
else
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
    --display-name="Document Processor Service Account"
fi

# Trigger Service Account
if gcloud iam service-accounts describe "${TRIGGER_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" &>/dev/null; then
  echo "Service account ${TRIGGER_ACCOUNT_NAME} already exists."
else
  gcloud iam service-accounts create "${TRIGGER_ACCOUNT_NAME}" \
    --display-name="Eventarc Trigger Service Account"
fi

# 5. Grant Permissions to Processor Service Account
echo "Granting permissions to Processor Service Account..."
# BigQuery Data Editor (to insert data)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor" \
  --condition=None

# BigQuery Job User (needed to execute streaming inserts/jobs)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser" \
  --condition=None

# GCS Storage Object Viewer (to read uploaded files)
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# 6. Grant Permissions to Trigger Service Account
echo "Granting permissions to Trigger Service Account..."
# Event Receiver
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${TRIGGER_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/eventarc.eventReceiver" \
  --condition=None

# 7. Grant Pub/Sub Publisher to GCS Service Agent
echo "Granting Pub/Sub Publisher role to GCS Service Agent..."
# GCS Service Agent format is service-PROJECT_NUMBER@gs-project-accounts.iam.gserviceaccount.com
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher" \
  --condition=None

# 8. Create Artifact Registry Repository for Docker Image
echo "Creating Artifact Registry repository..."
if gcloud artifacts repositories describe doc-processor-repo --location="${REGION}" &>/dev/null; then
  echo "Artifact Registry repository doc-processor-repo already exists."
else
  gcloud artifacts repositories create doc-processor-repo \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Docker repository for document processor service"
fi

echo "============================================================"
echo "Infrastructure Setup Complete!"
echo "Next steps:"
echo "1. Build and push the Cloud Run Docker image."
echo "2. Run deployment command to deploy Cloud Run service."
echo "3. Run 'gcloud eventarc triggers create' to hook up GCS to Cloud Run."
echo "============================================================"
