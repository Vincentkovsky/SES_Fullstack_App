# Use Python 3.9 slim image as base
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements files
COPY requirements.txt requirements.txt
COPY requirements_fastapi.txt requirements_fastapi.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements_fastapi.txt

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "fastapi_app:app", "--host", "0.0.0.0", "--port", "8000"] 