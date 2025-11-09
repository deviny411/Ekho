# ekho-backend/Dockerfile
FROM python:3.11-slim
WORKDIR /app
# Copy requirements file first to optimize caching
COPY ekho-backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# Copy the rest of the application code
COPY ekho-backend/ /app
# Set environment variables from your config file
ENV GOOGLE_CLOUD_PROJECT=ekho-477607 
# The service account file must be available in the container or credentials must be inherited from Cloud Run

# Set the entry point to run Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]