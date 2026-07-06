# Serverless Event-Driven Document OCR Pipeline

This repository contains a serverless event-driven document processing pipeline deployed to Google Cloud Platform (GCP). It automatically runs a simulated OCR process on files uploaded to a Cloud Storage bucket, extracts metadata (word count and semantic tags), and stores it in a BigQuery table.

## Architecture

1.  **Google Cloud Storage (GCS)**: Ingestion bucket for raw documents.
2.  **Eventarc**: Listens for `object.v1.finalized` events in the bucket and triggers the processing service.
3.  **Cloud Run**: Runs a FastAPI Python service (`processor/`) that processes the document, performs OCR, and streams metadata to BigQuery.
4.  **BigQuery**: Stores the processed metadata (`filename`, `upload_date`, `tags`, `word_count`).
5.  **Streamlit Dashboard**: A local Python dashboard to view logs and analyze tag/word count distributions.

---

## Getting Started

### Prerequisites

Make sure you are authenticated with GCP and have set your active project:
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project <PROJECT_ID>
```

### 1. Set Up Infrastructure

Run the setup script to enable GCP APIs, create the storage bucket, provision BigQuery datasets/tables, and configure service accounts with appropriate IAM roles:
```bash
./infra/setup.sh
```

### 2. Build and Deploy the Pipeline

Deploy the FastAPI processing service to Cloud Run and hook up the Eventarc GCS trigger:
```bash
./infra/deploy.sh
```

### 3. Run End-to-End Tests

Verify the entire pipeline (GCS -> Eventarc -> Cloud Run -> BigQuery) using the integration test script:
```bash
./infra/testcloud.sh
```

### 4. Run the Streamlit Dashboard

Start the Streamlit application locally to visualize the processed documents and filter by tag:
```bash
.venv/bin/streamlit run dashboard/app.py
```
Once started, the dashboard is accessible at `http://localhost:8501`.

---

## File Structure

-   `infra/setup.sh`: Infrastructure provisioning (GCS, BigQuery, IAM).
-   `infra/deploy.sh`: Builds and deploys the Cloud Run service and Eventarc trigger.
-   `infra/schema.json`: BigQuery schema file supporting repeated fields (tags).
-   `infra/testcloud.sh`: End-to-end cloud pipeline integration test script.
-   `processor/main.py`: FastAPI Cloud Run app for OCR processing and BigQuery streaming.
-   `processor/test_main.py`: Local unit tests.
-   `dashboard/app.py`: Streamlit dashboard with custom dark/light theme.