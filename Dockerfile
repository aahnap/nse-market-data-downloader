FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Files land in /app/data, logs in /app/logs -- mount these as volumes to
# persist them on the host, e.g.:
#   docker run -v $(pwd)/data:/app/data -v $(pwd)/logs:/app/logs nse-downloader
ENTRYPOINT ["python", "main.py"]
