#!/bin/bash
set -e

echo "==================================="
echo "WrkTalk Update Flow Test"
echo "==================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${GREEN}==>${NC} $1"
}

print_info() {
    echo -e "${BLUE}INFO:${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Get GCC pod
GCC_POD=$(kubectl get pod -l app=mock-gcc -o jsonpath='{.items[0].metadata.name}')
AGENT_POD=$(kubectl get pod -l app=wrktalk-agent -o jsonpath='{.items[0].metadata.name}')

if [ -z "$GCC_POD" ]; then
    print_error "Mock GCC pod not found. Run ./deploy-all.sh first"
    exit 1
fi

if [ -z "$AGENT_POD" ]; then
    print_error "Agent pod not found. Run ./deploy-all.sh first"
    exit 1
fi

# 1. Check initial version
print_step "Step 1: Checking current application version..."
CURRENT_TAG=$(argocd app get wrktalk-test-app --grpc-web -o json | jq -r '.spec.source.helm.parameters[] | select(.name=="image.tag") | .value' 2>/dev/null || echo "unknown")
print_info "Current image tag: $CURRENT_TAG"
echo ""

# 2. Check current pods
print_step "Step 2: Checking current pods..."
kubectl get pods -l app=wrktalk-test
echo ""

# 3. Trigger deployment
NEW_TAG="v2.0.0"
if [ "$CURRENT_TAG" == "v2.0.0" ]; then
    NEW_TAG="v3.0.0"
fi

print_step "Step 3: Triggering deployment to $NEW_TAG..."
kubectl exec -i $GCC_POD -- curl -s -X POST http://localhost:5000/api/v1/admin/trigger-deployment \
    -H "Content-Type: application/json" \
    -d "{\"image_tag\": \"$NEW_TAG\"}" | jq

echo ""

# 4. Watch agent logs
print_step "Step 4: Watching agent for deployment detection (30 seconds)..."
echo ""
echo "--- Agent Logs ---"
timeout 30s kubectl logs -f $AGENT_POD 2>/dev/null || true
echo ""

# 5. Wait for deployment to complete
print_step "Step 5: Waiting for deployment to complete..."
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    SYNC_STATUS=$(argocd app get wrktalk-test-app --grpc-web -o json 2>/dev/null | jq -r '.status.sync.status' || echo "Unknown")
    HEALTH_STATUS=$(argocd app get wrktalk-test-app --grpc-web -o json 2>/dev/null | jq -r '.status.health.status' || echo "Unknown")

    print_info "Sync: $SYNC_STATUS, Health: $HEALTH_STATUS"

    if [ "$SYNC_STATUS" == "Synced" ] && [ "$HEALTH_STATUS" == "Healthy" ]; then
        print_success "Deployment completed successfully!"
        break
    fi

    sleep 5
    WAITED=$((WAITED + 5))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    print_error "Timeout waiting for deployment"
    exit 1
fi

echo ""

# 6. Verify new version
print_step "Step 6: Verifying new version..."
FINAL_TAG=$(argocd app get wrktalk-test-app --grpc-web -o json | jq -r '.spec.source.helm.parameters[] | select(.name=="image.tag") | .value')
print_info "Final image tag: $FINAL_TAG"

if [ "$FINAL_TAG" == "$NEW_TAG" ]; then
    print_success "Version updated successfully: $CURRENT_TAG -> $FINAL_TAG"
else
    print_error "Version mismatch. Expected: $NEW_TAG, Got: $FINAL_TAG"
    exit 1
fi

echo ""

# 7. Check new pods
print_step "Step 7: Checking updated pods..."
kubectl get pods -l app=wrktalk-test
echo ""

# 8. Check GCC deployment status
print_step "Step 8: Checking GCC deployment status..."
kubectl exec -i $GCC_POD -- curl -s http://localhost:5000/api/v1/admin/status | jq
echo ""

# 9. Check application health
print_step "Step 9: Checking application health..."
APP_POD=$(kubectl get pod -l app=wrktalk-test -o jsonpath='{.items[0].metadata.name}')
if [ -n "$APP_POD" ]; then
    # Test the application endpoint
    kubectl port-forward $APP_POD 3001:3000 &
    PF_PID=$!
    sleep 2

    RESPONSE=$(curl -s http://localhost:3001 || echo "Failed to connect")
    kill $PF_PID 2>/dev/null || true

    print_info "Application response: $RESPONSE"
fi

echo ""
echo "==================================="
print_success "Test Completed Successfully!"
echo "==================================="
echo ""
echo "Summary:"
echo "  Initial Version: $CURRENT_TAG"
echo "  Target Version: $NEW_TAG"
echo "  Final Version: $FINAL_TAG"
echo "  Status: ✅ PASSED"
echo ""
