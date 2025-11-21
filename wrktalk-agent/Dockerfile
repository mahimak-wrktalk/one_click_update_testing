FROM python:3.11-slim

# Install required system packages
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install ArgoCD CLI
RUN curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64 && \
    chmod +x /usr/local/bin/argocd

# Verify ArgoCD CLI installation
RUN argocd version --client

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY agent.py .

# Run as non-root user
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

# Run agent
CMD ["python", "-u", "agent.py"]