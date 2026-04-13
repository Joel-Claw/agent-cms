FROM python:3.12-slim

WORKDIR /app

# Install rsync for deploy
RUN apt-get update && apt-get install -y rsync openssh-client git && rm -rf /var/lib/apt/lists/*

# Copy CMS
COPY . .

# Generate auth key on first run
RUN python3 build.py --show-key > /app/.cms_auth || true

# Build site
CMD ["python3", "build.py"]