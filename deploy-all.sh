#!/bin/bash
set -e

echo "================================"
echo "WrkTalk Complete Deployment"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${GREEN}==>${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

# Check prerequisites
print_step "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    print_error "Docker not found. Please install Docker."
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    print_error "kubectl not found. Please install kubectl."
    exit 1
fi

if ! command -v argocd &> /dev/null; then
    print_error "argocd CLI not found. Please install ArgoCD CLI."
    exit 1
fi

print_step "All prerequisites found!"
echo ""

# Get ArgoCD auth token
print_step "Getting ArgoCD auth token..."
ARGOCD_SERVER=$(kubectl get svc argocd-server -n argocd -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "localhost")
if [ "$ARGOCD_SERVER" == "localhost" ]; then
    print_warning "Using localhost for ArgoCD server"
    ARGOCD_SERVER="localhost:8080"
fi

# Try to get existing token or prompt for login
print_warning "Please ensure you're logged in to ArgoCD"
echo "Run: argocd login $ARGOCD_SERVER --grpc-web --insecure"
echo ""
read -p "Press Enter when logged in..."

# Generate a token for the agent
print_step "Generating auth token for agent..."
ARGOCD_TOKEN=$(argocd account generate-token --account admin 2>/dev/null || echo "")
if [ -z "$ARGOCD_TOKEN" ]; then
    print_error "Failed to generate ArgoCD token. Make sure you're logged in."
    exit 1
fi

# Build Docker images
print_step "Building Docker images..."

print_step "Building Mock GCC image..."
docker build -t mock-gcc:latest ./mock-gcc

print_step "Building WrkTalk Agent image..."
docker build -t wrktalk-agent:latest ./wrktalk-agent

# Load images into minikube if using minikube
if kubectl config current-context | grep -q "minikube"; then
    print_step "Detected minikube, loading images..."
    minikube image load mock-gcc:latest
    minikube image load wrktalk-agent:latest
fi

echo ""

# Deploy Mock GCC
print_step "Deploying Mock GCC API..."
kubectl apply -f mock-gcc/k8s/

# Wait for GCC to be ready
print_step "Waiting for Mock GCC to be ready..."
kubectl wait --for=condition=available --timeout=60s deployment/mock-gcc

echo ""

# Create secret with ArgoCD token
print_step "Creating secret with ArgoCD token..."
kubectl delete secret wrktalk-agent-secret --ignore-not-found=true
kubectl create secret generic wrktalk-agent-secret \
    --from-literal=ARGOCD_AUTH_TOKEN="$ARGOCD_TOKEN"

# Update ConfigMap with correct ArgoCD server
print_step "Updating ConfigMap..."
ARGOCD_K8S_SERVER="argocd-server.argocd.svc.cluster.local"
kubectl apply -f wrktalk-agent/k8s/configmap.yaml
kubectl apply -f wrktalk-agent/k8s/serviceaccount.yaml

# Deploy Agent
print_step "Deploying WrkTalk Agent..."
kubectl apply -f wrktalk-agent/k8s/deployment.yaml

# Wait for agent to be ready
print_step "Waiting for Agent to be ready..."
kubectl wait --for=condition=available --timeout=60s deployment/wrktalk-agent

echo ""
echo "================================"
echo -e "${GREEN}Deployment Complete!${NC}"
echo "================================"
echo ""
echo "Services deployed:"
echo "  - Mock GCC API: mock-gcc-service.default.svc.cluster.local:5000"
echo "  - WrkTalk Agent: Running and polling"
echo ""
echo "Next steps:"
echo "  1. Check agent logs: kubectl logs -f deployment/wrktalk-agent"
echo "  2. Check GCC logs: kubectl logs -f deployment/mock-gcc"
echo "  3. Run test: ./test-update-flow.sh"
echo ""
