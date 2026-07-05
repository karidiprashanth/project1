#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -euo pipefail

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

BUCKET_NAME="${BUCKET_NAME:-doc-processing-ingest-${PROJECT_ID}}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-doc-processor-sa}"
TRIGGER_ACCOUNT_NAME="${TRIGGER_ACCOUNT_NAME:-doc-trigger-sa}"
TRIGGER_NAME="${TRIGGER_NAME:-doc-processor-trigger}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/doc-processor-repo/${SERVICE_NAME}:latest"

echo "============================================================"
echo "Deploying Serverless Event-Driven Pipeline to Google Cloud"
echo "Project ID:      ${PROJECT_ID}"
echo "Region:          ${REGION}"
echo "Cloud Run:       ${SERVICE_NAME}"
echo "Image URI:       ${IMAGE_URI}"
echo "Trigger Name:    ${TRIGGER_NAME}"
echo "Bucket Filter:   ${BUCKET_NAME}"
echo "============================================================"

# 1. Build and push Docker image via Cloud Build
echo "Building and pushing container image via Cloud Build..."
gcloud builds submit --tag "${IMAGE_URI}" ./processor

# 2. Deploy Cloud Run service
echo "Deploying service to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE_URI}" \
  --region="${REGION}" \
  --service-account="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --update-env-vars PROJECT_ID="${PROJECT_ID}",DATASET_NAME="${DATASET_NAME}",TABLE_NAME="${TABLE_NAME}" \
  --no-allow-unauthenticated

# 3. Setup Eventarc trigger
echo "Configuring Eventarc trigger..."

# Check if trigger already exists
if gcloud eventarc triggers describe "${TRIGGER_NAME}" --location="${REGION}" &>/dev/null; then
  echo "Eventarc trigger '${TRIGGER_NAME}' already exists. Recreating to ensure latest config..."
  gcloud eventarc triggers delete "${TRIGGER_NAME}" --location="${REGION}" --quiet
fi

# Create trigger
gcloud eventarc triggers create "${TRIGGER_NAME}" \
  --location="${REGION}" \
  --destination-run-service="${SERVICE_NAME}" \
  --destination-run-region="${REGION}" \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=${BUCKET_NAME}" \
  --service-account="${TRIGGER_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "============================================================"
echo "Deployment Complete!"
echo "Your serverless pipeline is now active."
echo "============================================================"
