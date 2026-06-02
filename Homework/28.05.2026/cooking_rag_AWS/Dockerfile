FROM python:3.11-slim

# Keeps Python from writing .pyc files and enables unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Copy requirements first so Docker caches this layer -
# pip install only re-runs when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .
# Use the EC2-safe config (no secrets — credentials come from the EC2 IAM role)
COPY env.ec2 .env

EXPOSE 5001
CMD ["python", "app.py"]