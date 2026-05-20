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

# Pre-download NLTK tokenizer data so it is baked into the image
# and does not need a network call on first request
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True)"

# Copy the rest of the application code
COPY . .

EXPOSE 5001
CMD ["python", "app.py"]