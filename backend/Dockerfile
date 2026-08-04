FROM python:3.11-slim

# Install system dependencies required for USB HID & Serial hardware access
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libhidapi-dev \
    libusb-1.0-0-dev \
    udev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

EXPOSE 8000

CMD ["python", "server.py"]
