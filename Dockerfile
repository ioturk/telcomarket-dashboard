FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Streamlit's default port for Cloud Run
EXPOSE 8080

# Run Streamlit on Cloud Run's port (8080) and bind to 0.0.0.0
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
