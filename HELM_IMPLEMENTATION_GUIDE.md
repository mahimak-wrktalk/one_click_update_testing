# WrkTalk ArgoCD + Helm Implementation Guide

This guide implements your exact use case:
- **Single values.yaml** for all clients (no per-client values files)
- **Single ArgoCD Application manifest** (no per-client applications)
- **Image tag updates via ArgoCD CLI** using `--helm-set`
- **Agent-based deployment** simulation

---

## Prerequisites

- Minikube running
- ArgoCD installed in minikube
- Docker installed
- kubectl configured
- argocd CLI installed

---

## Phase 1: Build Test Application Images (10 mins)

### Step 1: Navigate to Testing Directory

```bash
cd /Users/admin/Documents/vscode_testing/Logging_monitoring/argocd/new_plan/testing
```

### Step 2: Build Docker Images Inside Minikube

```bash
# Point Docker CLI to Minikube's Docker daemon
eval $(minikube docker-env)

# Build v1.0.0
docker build -t wrktalk-test:v1.0.0 .

# Build v2.0.0 (same Dockerfile, different tag for testing)
docker build -t wrktalk-test:v2.0.0 .

# Verify images exist
docker images | grep wrktalk-test
```

**Expected Output:**
```
wrktalk-test   v2.0.0   <image-id>   X seconds ago   XXX MB
wrktalk-test   v1.0.0   <image-id>   X seconds ago   XXX MB
```

---

## Phase 2: Setup Git Repository (5 mins)

ArgoCD requires a Git repository to pull manifests from.

### Option A: Use GitHub (Recommended)

```bash
# Initialize Git repository
cd /Users/admin/Documents/vscode_testing/Logging_monitoring/argocd/new_plan/testing
git init
git add .
git commit -m "Initial WrkTalk test setup with Helm chart"

# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### Option B: Use Local Git (Quick Testing)

```bash
# Just initialize locally
git init
git add .
git commit -m "Initial WrkTalk test setup"

# Note: You'll need to configure ArgoCD to access local repos
# This is more complex and not recommended for production
```

---

## Phase 3: Update ArgoCD Application Manifest (2 mins)

### Edit the ArgoCD Application File

```bash
# Open argocd-app-helm.yaml and update the repoURL
# Replace:
#   repoURL: https://github.com/YOUR_USERNAME/YOUR_REPO.git
# With your actual GitHub repository URL
```

Or use this command:

```bash
# Replace with your actual repo URL
REPO_URL="https://github.com/YOUR_USERNAME/YOUR_REPO.git"

sed -i '' "s|https://github.com/YOUR_USERNAME/YOUR_REPO.git|$REPO_URL|g" argocd-app-helm.yaml
```

---

## Phase 4: Deploy Application via ArgoCD (5 mins)

### Step 1: Login to ArgoCD

```bash
# Get ArgoCD admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
echo

# Port forward ArgoCD server (in a separate terminal)
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Login via CLI
argocd login localhost:8080 --username admin --password <PASSWORD> --insecure
```

### Step 2: Create ArgoCD Application

```bash
# Apply the ArgoCD application
kubectl apply -f argocd-app-helm.yaml

# Wait for initial sync
sleep 10

# Check application status
argocd app get wrktalk-test-app
```

### Step 3: Wait for Application to Become Healthy

```bash
# Wait for sync and health (timeout 5 mins)
argocd app wait wrktalk-test-app --timeout 300

# Check sync and health status
argocd app get wrktalk-test-app | grep -E "Sync Status|Health Status"
```

**Expected Output:**
```
Sync Status:        Synced
Health Status:      Healthy
```

---

## Phase 5: Verify Initial Deployment (3 mins)

### Step 1: Check Kubernetes Resources

```bash
# Check pods
kubectl get pods -l app=wrktalk-test

# Expected: 2 pods running
# NAME                            READY   STATUS    RESTARTS   AGE
# wrktalk-test-xxxxxxxxxx-xxxxx   1/1     Running   0          XX s
# wrktalk-test-xxxxxxxxxx-xxxxx   1/1     Running   0          XX s

# Check deployment
kubectl get deployment wrktalk-test


# Check service
kubectl get service wrktalk-test
```

### Step 2: Verify Image Version

```bash
# Check current image tag
kubectl get deployment wrktalk-test -o jsonpath='{.spec.template.spec.containers[0].image}'
# Expected: wrktalk-test:v1.0.0

# Check environment variable
kubectl get pods -l app=wrktalk-test -o jsonpath='{.items[0].spec.containers[0].env[?(@.name=="VERSION")].value}'
# Expected: v1.0.0
```

### Step 3: Test Application

```bash
# Port forward the service
kubectl port-forward svc/wrktalk-test 3000:3000 &

# Test the application
curl http://localhost:3000

# Expected Output:
# {
#   "app": "WrkTalk Test",
#   "version": "v1.0.0",
#   "message": "Running version v1.0.0",
#   "timestamp": "2025-XX-XXT..."
# }

# Test health endpoint
curl http://localhost:3000/health

# Expected: {"status":"healthy","version":"v1.0.0"}

# Kill port-forward when done
kill %1
```

---

## Phase 6: Manual Image Update Test (THIS IS WHAT YOUR AGENT WILL DO)

This is the critical test that simulates exactly what your Python agent will execute.

### Step 1: Check Current State

```bash
# Check current image tag parameter in ArgoCD
argocd app get wrktalk-test-app --show-params

# Expected to show: image.tag=v1.0.0
```

### Step 2: Update Image Tag Using ArgoCD CLI

```bash
# THIS IS THE COMMAND YOUR AGENT WILL RUN
argocd app set wrktalk-test-app \
  --helm-set image.tag=v2.0.0 \
  --grpc-web

# Expected Output:
# application 'wrktalk-test-app' updated successfully
```

### Step 3: Trigger Sync

```bash
# Sync the application
argocd app sync wrktalk-test-app --grpc-web

# Expected Output:
# TIMESTAMP            GROUP        KIND         NAMESPACE  NAME          STATUS     HEALTH   HOOK  MESSAGE
# ...
```

### Step 4: Watch the Update Happen

```bash
# In one terminal, watch pods
kubectl get pods -l app=wrktalk-test -w

# You'll see:
# 1. New pods created with v2.0.0
# 2. New pods become Ready
# 3. Old pods terminated
# 4. This is the rolling update in action!
```

### Step 5: Wait for Sync to Complete

```bash
# Wait for application to be synced and healthy
argocd app wait wrktalk-test-app --health --timeout 300

# Get final status
argocd app get wrktalk-test-app
```

**Expected Output:**
```
Name:               wrktalk-test-app
Project:            default
Server:             https://kubernetes.default.svc
Namespace:          default
URL:                https://localhost:8080/applications/wrktalk-test-app
Repo:               https://github.com/...
Target:             HEAD
Path:               helm-chart/wrktalk-test
SyncWindow:         Sync Allowed
Sync Policy:        Automated (Prune)
Sync Status:        Synced to HEAD (xxxxxx)
Health Status:      Healthy
```

---

## Phase 7: Verify Update (3 mins)

### Step 1: Verify New Image Tag

```bash
# Check deployment image
kubectl get deployment wrktalk-test -o jsonpath='{.spec.template.spec.containers[0].image}'
# Expected: wrktalk-test:v2.0.0

# Check pods are using new image
kubectl get pods -l app=wrktalk-test -o jsonpath='{.items[*].spec.containers[0].image}'
# Expected: wrktalk-test:v2.0.0 wrktalk-test:v2.0.0
```

### Step 2: Test Updated Application

```bash
# Port forward again
kubectl port-forward svc/wrktalk-test 3000:3000 &

# Test the application
curl http://localhost:3000

# Expected Output:
# {
#   "app": "WrkTalk Test",
#   "version": "v2.0.0",  <-- CHANGED!
#   "message": "Running version v2.0.0",  <-- CHANGED!
#   "timestamp": "2025-XX-XXT..."
# }

# Kill port-forward
kill %1
```

### Step 3: Verify ArgoCD Status

```bash
# Check ArgoCD application parameters
argocd app get wrktalk-test-app --show-params

# Expected to show: image.tag=v2.0.0

# Get detailed status
argocd app get wrktalk-test-app -o json | jq '{sync: .status.sync.status, health: .status.health.status, imageTag: .spec.source.helm.parameters}'
```

---

## SUCCESS! What You've Proven:

1. ✅ Single Helm chart with single values.yaml works for all clients
2. ✅ No need for per-client values.yaml files
3. ✅ No need for per-client ArgoCD applications
4. ✅ Image tag can be updated via `argocd app set --helm-set`
5. ✅ Rolling updates happen automatically
6. ✅ Health checks work correctly
7. ✅ This is exactly how your agent will work!

---

## Phase 8: What Your Python Agent Will Do

Based on the successful manual test, here's what your agent needs to implement:

### Agent Workflow (Simplified)

```python
# Pseudocode for your agent

def update_client_application(client_id, new_image_tag):
    """
    This function simulates what your agent will do
    """

    # 1. Authenticate with ArgoCD (one-time setup)
    argocd_login(server, username, password)

    # 2. Update the image tag
    result = run_command([
        "argocd", "app", "set", f"wrktalk-{client_id}",
        "--helm-set", f"image.tag={new_image_tag}",
        "--grpc-web"
    ])

    if result.returncode != 0:
        return {"status": "failed", "reason": "Failed to set image tag"}

    # 3. Trigger sync
    result = run_command([
        "argocd", "app", "sync", f"wrktalk-{client_id}",
        "--grpc-web"
    ])

    if result.returncode != 0:
        return {"status": "failed", "reason": "Sync failed"}

    # 4. Wait for healthy status (with timeout)
    result = run_command([
        "argocd", "app", "wait", f"wrktalk-{client_id}",
        "--health",
        "--timeout", "300"
    ])

    if result.returncode != 0:
        return {"status": "failed", "reason": "Health check failed"}

    # 5. Get final status
    status = get_app_status(f"wrktalk-{client_id}")

    # 6. Report back to GCC
    return {
        "status": "success",
        "sync_status": status["sync"],
        "health_status": status["health"],
        "image_tag": new_image_tag
    }
```

---

## Phase 9: Key Observations for Agent Development

### Command Outputs to Parse

#### 1. Set Command Output
```bash
argocd app set wrktalk-test-app --helm-set image.tag=v2.0.0 --grpc-web
```
**Output:** `application 'wrktalk-test-app' updated successfully`
**Exit Code:** 0 (success), non-zero (failure)

#### 2. Sync Command Output
```bash
argocd app sync wrktalk-test-app --grpc-web
```
**Output:** Table with resource sync status
**Exit Code:** 0 (success), non-zero (failure)

#### 3. Wait Command Output
```bash
argocd app wait wrktalk-test-app --health --timeout 300
```
**Output:** Waits silently, returns when healthy or timeout
**Exit Code:** 0 (healthy), non-zero (unhealthy or timeout)

#### 4. Get Status Command (JSON)
```bash
argocd app get wrktalk-test-app -o json
```
**Output:** JSON object with full status

Parse this to extract:
```json
{
  "status": {
    "sync": {
      "status": "Synced"  // or "OutOfSync"
    },
    "health": {
      "status": "Healthy"  // or "Progressing", "Degraded", "Missing"
    },
    "operationState": {
      "phase": "Succeeded"  // or "Running", "Failed"
    }
  }
}
```

---

## Phase 10: Test Failure Scenarios (Important!)

### Test 1: Invalid Image Tag

```bash
# Update to non-existent image
argocd app set wrktalk-test-app --helm-set image.tag=v999.999.999 --grpc-web
argocd app sync wrktalk-test-app --grpc-web

# Watch what happens
kubectl get pods -l app=wrktalk-test -w

# You'll see: ImagePullBackOff

# Check ArgoCD status
argocd app get wrktalk-test-app

# Health Status will show: Progressing or Degraded
```

**Agent Learning:** Your agent must detect this and report failure to GCC.

### Test 2: Rollback to Working Version

```bash
# Rollback to v2.0.0 (working version)
argocd app set wrktalk-test-app --helm-set image.tag=v2.0.0 --grpc-web
argocd app sync wrktalk-test-app --grpc-web
argocd app wait wrktalk-test-app --health --timeout 300

# Verify rollback worked
curl $(kubectl port-forward svc/wrktalk-test 3000:3000 >/dev/null 2>&1 & echo "http://localhost:3000")
```

---

## Phase 11: Multi-Client Simulation (Optional)

Want to test with multiple "clients"? Create multiple ArgoCD applications:

```bash
# Create client-1 application
cat > argocd-app-client1.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: wrktalk-client-1
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_USERNAME/YOUR_REPO.git
    targetRevision: HEAD
    path: helm-chart/wrktalk-test
    helm:
      parameters:
        - name: image.tag
          value: "v1.0.0"
  destination:
    server: https://kubernetes.default.svc
    namespace: client-1
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF

kubectl apply -f argocd-app-client1.yaml

# Update client-1
argocd app set wrktalk-client-1 --helm-set image.tag=v2.0.0 --grpc-web
argocd app sync wrktalk-client-1 --grpc-web
argocd app wait wrktalk-client-1 --health
```

---

## Summary: What You Can Test Manually Before Writing Agent Code

### Checklist

- [x] Build Docker images (v1.0.0, v2.0.0)
- [x] Create Helm chart with single values.yaml
- [x] Deploy via ArgoCD
- [x] Verify initial deployment (v1.0.0)
- [x] Update image tag using `argocd app set --helm-set`
- [x] Trigger sync with `argocd app sync`
- [x] Wait for health with `argocd app wait`
- [x] Verify update worked (v2.0.0)
- [x] Test with invalid image (failure scenario)
- [x] Test rollback to working version
- [x] Parse JSON output from `argocd app get -o json`
- [x] Understand timing (how long syncs take)
- [x] Understand status transitions

### Questions Answered

1. **How long does sync take?** → Measure during your tests
2. **What statuses appear?** → Progressing → Healthy
3. **How to detect completion?** → `argocd app wait --health`
4. **How to detect failure?** → Exit code + Health Status != Healthy
5. **Can agent run in parallel?** → Yes, for different clients
6. **Authentication method?** → Username/password or API token

---

## Next Steps

1. Complete all manual tests above
2. Document all command outputs and timings
3. Create a simple Python script to automate one update
4. Expand to handle multiple clients
5. Add error handling and retry logic
6. Integrate with your GCC backend
7. Add approval workflow before sync

---

## Quick Reference: Agent Commands

```bash
# Login
argocd login <server> --username <user> --password <pass> --insecure

# Update image tag
argocd app set <app-name> --helm-set image.tag=<new-tag> --grpc-web

# Sync
argocd app sync <app-name> --grpc-web

# Wait for healthy
argocd app wait <app-name> --health --timeout 300

# Get status (JSON)
argocd app get <app-name> -o json

# Get status (human-readable)
argocd app get <app-name>
```

Good luck with your testing! 🚀
