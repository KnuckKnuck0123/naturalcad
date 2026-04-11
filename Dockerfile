FROM python:3.10-slim

# Install system libraries that OpenCascade/Gradio often require
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary directories and set permissions
RUN mkdir -p artifacts/runs artifacts/logs && \
    chmod -R 777 artifacts

# Copy the rest of the application
COPY . .

# Create a non-root user (Hugging Face requirement for some Docker Spaces)
RUN useradd -m -u 1000 user && \
    chown -R user:user /app
USER user

# Hugging Face exposes port 7860 by default
EXPOSE 7860

# Run the app
CMD ["python", "app.py"]
