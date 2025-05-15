# Use Python 3.9 image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    proj-bin \
    libproj-dev \
    g++ \
    gdal-bin \
    libgdal-dev

# Set GDAL environment variables
ENV GDAL_VERSION=3.6.2
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Copy requirements files
COPY requirements_fastapi.txt requirements_fastapi.txt

# Install dependencies with pip cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements_fastapi.txt

# Copy application files
COPY api_fastapi/ api_fastapi/
COPY core/ core/
# COPY data/ data/
COPY resources/ resources/
COPY services/ services/
COPY utils/ utils/
COPY fastapi_app.py ./
COPY __init__.py ./

# Expose port
EXPOSE 3000

# Command to run the application
CMD ["uvicorn", "fastapi_app:create_app", "--host", "0.0.0.0", "--port", "3000", "--factory"] 