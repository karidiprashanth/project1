# Use official lightweight Python image
FROM python:3.11-slim as builder

# Set build directory
WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed python packages from builder
COPY --from=builder /root/.local /root/.local
COPY main.py .

# Update PATH to include user local bin
ENV PATH=/root/.local/bin:$PATH
# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Force stdout/stderr streams to be unbuffered
ENV PYTHONUNBUFFERED=1

# Expose port (Cloud Run defaults to 8080)
EXPOSE 8080

# Command to run FastAPI server using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
