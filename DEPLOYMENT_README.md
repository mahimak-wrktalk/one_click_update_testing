# WrkTalk Deployment System - Complete Guide

This guide explains the complete automated deployment system using GCC (Global Control Center), Agent, and ArgoCD.

## Architecture Overview

```
┌─────────────────┐
│   GCC API       │ ← Admin triggers deployment via REST API
│  (Mock/Real)    │
└────────┬────────┘
         │
         │ HTTP Polling (every 10s)
         │
         ↓
┌─────────────────┐
│  Agent (Pod)    │ ← Polls for updates
│                 │ ← Reports deployment status
└────────┬────────┘
         │
         │ ArgoCD CLI Commands
         │
         ↓
┌─────────────────┐
│    ArgoCD       │ ← Manages k8s deployments
│                 │ ← Syncs Helm charts
└────────┬────────┘
         │
         │ Kubernetes API
         │
         ↓
┌─────────────────┐
│  Application    │ ← Rolling updates
│    (Pods)       │ ← New image versions
└─────────────────┘
```

## Components

### 1. Mock GCC API (Global Control Center)
- Flask-based REST API
- Simulates the central control system
- Manages deployment triggers and status tracking
- Endpoints:
  - `GET /api/v1/clients/{id}/updates` - Agent polls for updates
  - `POST /api/v1/clients/{id}/status` - Agent reports status
  - `POST /api/v1/admin/trigger-deployment` - Trigger deployment
  - `GET /api/v1/admin/status` - Check deployment status

### 2. WrkTalk Agent
- Python application running in Kubernetes
- Polls GCC API every 10 seconds
- Executes deployments via ArgoCD CLI
- Reports status back to GCC
- Monitors deployment health

### 3. ArgoCD
- GitOps deployment tool
- Manages application deployments
- Performs rolling updates
- Health monitoring

## Quick Start

### Prerequisites

1. **Kubernetes cluster** (minikube, kind, or production cluster)
   ```bash
   minikube start
   ```

2. **ArgoCD installed**
   ```bash
   kubectl create namespace argocd
   kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
   ```

3. **ArgoCD CLI installed**
   ```bash
   # macOS
   brew install argocd

   # Linux
   curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
   chmod +x /usr/local/bin/argocd
   ```

4. **ArgoCD port-forward** (for local testing)
   ```bash
   kubectl port-forward svc/argocd-server -n argocd 8080:443 &
   ```

5. **ArgoCD login**
   ```bash
   # Get initial password
   argocd admin initial-password -n argocd

   # Login
   argocd login localhost:8080 --grpc-web --insecure --username admin
   ```

6. **Create ArgoCD application** (if not already exists)
   ```bash
   kubectl apply -f argocd-app-helm.yaml
   ```

### One-Command Deployment

```bash
./deploy-all.sh
```

This script will:
1. Build Docker images for GCC and Agent
2. Load images into your cluster (if using minikube)
3. Generate ArgoCD auth token
4. Deploy Mock GCC API
5. Deploy WrkTalk Agent
6. Configure all necessary secrets and configmaps

## Manual Deployment Steps

### Step 1: Build Docker Images

```bash
# Build Mock GCC
cd mock-gcc
docker build -t mock-gcc:latest .

# Build Agent
cd ../wrktalk-agent
docker build -t wrktalk-agent:latest .
```

### Step 2: Load Images (if using minikube)

```bash
minikube image load mock-gcc:latest
minikube image load wrktalk-agent:latest
```

### Step 3: Get ArgoCD Auth Token

```bash
# Generate token for the agent
argocd account generate-token --account admin
```

### Step 4: Deploy Mock GCC

```bash
kubectl apply -f mock-gcc/k8s/deployment.yaml
kubectl wait --for=condition=available --timeout=60s deployment/mock-gcc
```

### Step 5: Create Secret with ArgoCD Token

```bash
kubectl create secret generic wrktalk-agent-secret \
    --from-literal=ARGOCD_AUTH_TOKEN="your-token-here"
```

### Step 6: Deploy Agent

```bash
kubectl apply -f wrktalk-agent/k8s/configmap.yaml
kubectl apply -f wrktalk-agent/k8s/serviceaccount.yaml
kubectl apply -f wrktalk-agent/k8s/deployment.yaml
```

## Testing the Deployment Flow

### Automated Test

```bash
./test-update-flow.sh
```

This will:
1. Check current application version
2. Trigger a deployment to a new version
3. Watch agent logs
4. Monitor deployment progress
5. Verify successful update

### Manual Testing

#### 1. Check Agent Logs
```bash
kubectl logs -f deployment/wrktalk-agent
```

You should see polling activity (dots) every 10 seconds.

#### 2. Check Current Application Version
```bash
argocd app get wrktalk-test-app --grpc-web | grep "image.tag"
```

#### 3. Trigger Deployment

Get the GCC pod name:
```bash
GCC_POD=$(kubectl get pod -l app=mock-gcc -o jsonpath='{.items[0].metadata.name}')
```

Trigger deployment to v2.0.0:
```bash
kubectl exec -i $GCC_POD -- curl -X POST http://localhost:5000/api/v1/admin/trigger-deployment \
  -H "Content-Type: application/json" \
  -d '{"image_tag": "v2.0.0"}'
```

#### 4. Watch the Agent

In the agent logs, you should see:
- "📦 New deployment detected!"
- "🚀 DEPLOYMENT STARTING"
- "Setting image tag to v2.0.0..."
- "Triggering ArgoCD sync..."
- "Waiting for deployment to complete..."
- "✅ DEPLOYMENT SUCCESSFUL"

#### 5. Watch Pods Rolling Update
```bash
kubectl get pods -l app=wrktalk-test -w
```

#### 6. Verify New Version
```bash
argocd app get wrktalk-test-app --grpc-web | grep "image.tag"
# Should show v2.0.0
```

#### 7. Check GCC Status
```bash
kubectl exec -i $GCC_POD -- curl -s http://localhost:5000/api/v1/admin/status | jq
```

## Configuration

### Agent Configuration (ConfigMap)

Edit `wrktalk-agent/k8s/configmap.yaml`:

```yaml
data:
  CLIENT_ID: "101"                    # Unique client identifier
  GCC_API_URL: "http://..."           # GCC API endpoint
  ARGOCD_APP_NAME: "wrktalk-test-app" # ArgoCD application name
  ARGOCD_SERVER: "argocd-server..."   # ArgoCD server address
  POLL_INTERVAL: "10"                 # Poll interval in seconds
  ARGOCD_INSECURE: "true"             # Skip TLS verification (dev only)
```

### ArgoCD Authentication

The agent needs an ArgoCD auth token. Generate it:

```bash
# For admin account
argocd account generate-token --account admin

# For a service account (recommended for production)
argocd account create deployment-agent
argocd account generate-token --account deployment-agent
```

## Troubleshooting

### Agent Not Detecting Updates

1. Check agent logs:
   ```bash
   kubectl logs deployment/wrktalk-agent
   ```

2. Verify GCC is accessible:
   ```bash
   kubectl exec -it deployment/wrktalk-agent -- curl http://mock-gcc-service.default.svc.cluster.local:5000/health
   ```

3. Check if update is pending:
   ```bash
   GCC_POD=$(kubectl get pod -l app=mock-gcc -o jsonpath='{.items[0].metadata.name}')
   kubectl exec -i $GCC_POD -- curl http://localhost:5000/api/v1/admin/status
   ```

### ArgoCD Sync Failing

1. Check ArgoCD application status:
   ```bash
   argocd app get wrktalk-test-app --grpc-web
   ```

2. Check ArgoCD connectivity from agent:
   ```bash
   kubectl exec -it deployment/wrktalk-agent -- argocd version --grpc-web --insecure
   ```

3. Verify auth token is correct:
   ```bash
   kubectl get secret wrktalk-agent-secret -o jsonpath='{.data.ARGOCD_AUTH_TOKEN}' | base64 -d
   ```

### Pods Not Updating

1. Check if images exist:
   ```bash
   kubectl describe pod <pod-name> | grep -A 5 "Events:"
   ```

2. Verify Helm values:
   ```bash
   argocd app get wrktalk-test-app --grpc-web -o json | jq '.spec.source.helm.parameters'
   ```

3. Force sync:
   ```bash
   argocd app sync wrktalk-test-app --grpc-web --force
   ```

## Production Considerations

### 1. Security

- **Use proper TLS certificates** for ArgoCD (remove `ARGOCD_INSECURE`)
- **Use service accounts** instead of admin tokens
- **Implement RBAC** for ArgoCD operations
- **Secure GCC API** with authentication
- **Use Kubernetes secrets** for sensitive data
- **Network policies** to restrict traffic

### 2. Reliability

- **Multiple agent replicas** for high availability (with leader election)
- **Persistent storage** for GCC state (use database instead of in-memory)
- **Retry logic** with exponential backoff
- **Circuit breakers** for API calls
- **Health checks** and liveness probes

### 3. Monitoring

- **Prometheus metrics** from agent and GCC
- **Logging** to centralized system (ELK, Loki)
- **Alerts** for deployment failures
- **Dashboards** for deployment tracking

### 4. Scalability

- **Multiple clients** (different namespaces)
- **Batch deployments** (staggered rollouts)
- **Rate limiting** for API calls
- **Database backend** for GCC (PostgreSQL, MySQL)

## Development

### Local Development (Outside K8s)

#### Run Mock GCC Locally
```bash
cd mock-gcc
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python mock_gcc.py
```

#### Run Agent Locally
```bash
cd wrktalk-agent
pip install -r requirements.txt

# Set environment variables
export CLIENT_ID=101
export GCC_API_URL=http://localhost:5000/api/v1
export ARGOCD_APP_NAME=wrktalk-test-app
export ARGOCD_SERVER=localhost:8080
export ARGOCD_AUTH_TOKEN=your-token
export ARGOCD_INSECURE=true
export POLL_INTERVAL=10

python agent.py
```

### Testing Locally

In one terminal (GCC):
```bash
cd mock-gcc && source venv/bin/activate && python mock_gcc.py
```

In another terminal (Agent):
```bash
cd wrktalk-agent && python agent.py
```

In a third terminal (Testing):
```bash
# Trigger deployment
curl -X POST http://localhost:5000/api/v1/admin/trigger-deployment \
  -H "Content-Type: application/json" \
  -d '{"image_tag": "v2.0.0"}'

# Watch agent terminal for deployment activity
```

## Next Steps

1. **Multiple Clients**: Extend to support multiple clients with different deployments
2. **Rollback**: Implement automatic rollback on failure
3. **Blue-Green Deployments**: Support blue-green deployment strategy
4. **Canary Releases**: Implement progressive delivery
5. **Database Backend**: Replace in-memory state with PostgreSQL
6. **Authentication**: Add proper authentication to GCC API
7. **Webhooks**: Support webhook notifications for deployment events
8. **UI Dashboard**: Build a web UI for GCC to visualize deployments

## Support

For issues or questions:
1. Check logs: `kubectl logs deployment/wrktalk-agent`
2. Check status: `argocd app get wrktalk-test-app --grpc-web`
3. Review this documentation
4. Check ArgoCD docs: https://argo-cd.readthedocs.io/

## Success Criteria

Your deployment is successful if:

- ✅ Agent polls GCC every 10 seconds
- ✅ Agent detects new deployment when triggered
- ✅ Agent updates ArgoCD with new image tag
- ✅ Agent triggers ArgoCD sync
- ✅ ArgoCD performs rolling update
- ✅ New pods created with new version
- ✅ Old pods terminated gracefully
- ✅ Service remains available during update
- ✅ Agent reports success to GCC
- ✅ Application responds with new version
