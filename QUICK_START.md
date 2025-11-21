# Quick Start Guide

## TL;DR - Get Running in 5 Minutes

### 1. Prerequisites Check
```bash
# Make sure you have these installed:
minikube status          # Kubernetes cluster
argocd version           # ArgoCD CLI
docker --version         # Docker

# If ArgoCD isn't installed:
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Port-forward ArgoCD
kubectl port-forward svc/argocd-server -n argocd 8080:443 &
```

### 2. Login to ArgoCD
```bash
# Get password
argocd admin initial-password -n argocd

# Login
argocd login localhost:8080 --grpc-web --insecure
```

### 3. Create ArgoCD Application
```bash
kubectl apply -f argocd-app-helm.yaml
```

### 4. Deploy Everything
```bash
./deploy-all.sh
```

### 5. Test It
```bash
./test-update-flow.sh
```

## What Just Happened?

1. **Mock GCC API** was deployed - simulates your control center
2. **WrkTalk Agent** was deployed - polls GCC and manages deployments
3. Agent is now polling every 10 seconds for updates

## Manual Trigger

```bash
# Get GCC pod
GCC_POD=$(kubectl get pod -l app=mock-gcc -o jsonpath='{.items[0].metadata.name}')

# Trigger deployment to v2.0.0
kubectl exec -i $GCC_POD -- curl -X POST http://localhost:5000/api/v1/admin/trigger-deployment \
  -H "Content-Type: application/json" \
  -d '{"image_tag": "v2.0.0"}'

# Watch agent logs
kubectl logs -f deployment/wrktalk-agent
```

## Verify

```bash
# Check application version
argocd app get wrktalk-test-app --grpc-web | grep "image.tag"

# Check pods
kubectl get pods -l app=wrktalk-test

# Check deployment status
kubectl exec -i $GCC_POD -- curl -s http://localhost:5000/api/v1/admin/status | jq
```

## Common Commands

```bash
# View agent logs
kubectl logs -f deployment/wrktalk-agent

# View GCC logs
kubectl logs -f deployment/mock-gcc

# Check ArgoCD app status
argocd app get wrktalk-test-app --grpc-web

# List all pods
kubectl get pods

# Restart agent
kubectl rollout restart deployment/wrktalk-agent

# Delete everything
kubectl delete deployment mock-gcc wrktalk-agent
kubectl delete service mock-gcc-service
kubectl delete configmap wrktalk-agent-config
kubectl delete secret wrktalk-agent-secret
kubectl delete serviceaccount wrktalk-agent
```

## Troubleshooting

### Agent not starting?
```bash
kubectl describe pod -l app=wrktalk-agent
kubectl logs deployment/wrktalk-agent
```

### GCC not reachable?
```bash
kubectl get svc mock-gcc-service
kubectl exec -it deployment/wrktalk-agent -- curl http://mock-gcc-service.default.svc.cluster.local:5000/health
```

### ArgoCD connection issues?
```bash
kubectl exec -it deployment/wrktalk-agent -- argocd version --grpc-web --insecure
```

## Directory Structure

```
.
├── mock-gcc/
│   ├── mock_gcc.py              # GCC API code
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── k8s/
│   │   └── deployment.yaml      # K8s manifests for GCC
│   └── README.md
│
├── wrktalk-agent/
│   ├── agent.py                 # Agent code
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── k8s/
│   │   ├── configmap.yaml       # Agent configuration
│   │   ├── secret.yaml          # ArgoCD token (template)
│   │   ├── serviceaccount.yaml  # Service account
│   │   └── deployment.yaml      # Agent deployment
│   └── README.md
│
├── deploy-all.sh                # One-command deployment
├── test-update-flow.sh          # End-to-end test
├── DEPLOYMENT_README.md         # Comprehensive guide
└── QUICK_START.md              # This file
```

## Next Steps

See [DEPLOYMENT_README.md](DEPLOYMENT_README.md) for:
- Architecture details
- Production considerations
- Advanced configuration
- Troubleshooting guide
