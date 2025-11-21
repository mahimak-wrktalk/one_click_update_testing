# WrkTalk Deployment Agent

Agent that polls GCC for updates and deploys them via ArgoCD.

## Prerequisites

- ArgoCD CLI installed
- Access to ArgoCD server
- Access to GCC API

## Configuration

Set these environment variables:

```bash
export CLIENT_ID=101
export GCC_API_URL=http://localhost:5000/api/v1
export ARGOCD_APP_NAME=wrktalk-test-app
export ARGOCD_SERVER=localhost:8080
export ARGOCD_AUTH_TOKEN=your-token-here
export ARGOCD_INSECURE=true  # Only for dev/test
export POLL_INTERVAL=10  # seconds
```

## Local Development

```bash
cd wrktalk-agent
pip install -r requirements.txt
python agent.py
```

## Docker Build

```bash
docker build -t wrktalk-agent:latest .
```

## Kubernetes Deployment

```bash
kubectl apply -f k8s/
```

## How It Works

1. Agent polls GCC API every POLL_INTERVAL seconds
2. When a new deployment is detected:
   - Updates ArgoCD application with new image tag
   - Triggers ArgoCD sync
   - Monitors deployment progress
   - Reports status back to GCC
3. On success, clears the pending update
4. On failure, reports error to GCC
