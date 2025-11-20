# ArgoCD Image Update Testing Guide

## Prerequisites
- Minikube running
- ArgoCD installed in minikube
- kubectl configured to access minikube cluster

## Step 1: Setup Git Repository (Required for ArgoCD)

ArgoCD needs to pull manifests from a Git repository. You have two options:

### Option A: Use Local Git Repository (Quick Testing)
```bash
# Initialize git repo in current directory
cd /Users/admin/Documents/vscode_testing/Logging_monitoring/argocd/new_plan/testing
git init
git add deployment.yaml service.yaml
git commit -m "Initial nginx deployment"

# You'll need to push to a remote (GitHub/GitLab) for ArgoCD to access
```

### Option B: Create GitHub Repository
1. Create a new repository on GitHub
2. Push your manifests:
```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

3. Update `argocd-application.yaml` with your repo URL

## Step 2: Deploy Application via ArgoCD

### 2.1 Login to ArgoCD
```bash
# Get ArgoCD admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

# Port forward ArgoCD server
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Login via CLI (in another terminal)
argocd login localhost:8080 --username admin --password <password-from-above> --insecure
```

### 2.2 Create ArgoCD Application
```bash
# Apply the ArgoCD application manifest
kubectl apply -f argocd-application.yaml

# OR create via ArgoCD CLI
argocd app create sample-nginx-app \
  --repo https://github.com/YOUR_USERNAME/YOUR_REPO.git \
  --path . \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace default
```

### 2.3 Initial Sync
```bash
# Sync the application
argocd app sync sample-nginx-app

# Wait for it to become healthy
argocd app wait sample-nginx-app --health
```

### 2.4 Verify Initial Deployment
```bash
# Check application status
argocd app get sample-nginx-app

# Check pods
kubectl get pods -l app=sample-nginx

# Check current image version
kubectl get deployment sample-nginx -o jsonpath='{.spec.template.spec.containers[0].image}'
# Should show: nginx:1.25.0
```

## Step 3: Manual Image Update Test

### 3.1 Update Image Tag Using ArgoCD CLI
```bash
# Set new image tag (simulating what your agent will do)
argocd app set sample-nginx-app --parameter image.tag=1.25.1 --grpc-web

# Note: If using plain manifests (not Helm), use:
argocd app set sample-nginx-app --kustomize-image nginx=nginx:1.25.1 --grpc-web
```

### 3.2 Sync the Application
```bash
# Trigger sync
argocd app sync sample-nginx-app --grpc-web

# Wait for sync and health
argocd app wait sample-nginx-app --health --timeout 300
```

### 3.3 Alternative: Direct Manifest Update (More Realistic for Your Use Case)

Since you're NOT using separate values.yaml files, you'll likely update the deployment.yaml directly:

```bash
# Update deployment.yaml with new image tag
sed -i '' 's/nginx:1.25.0/nginx:1.25.1/g' deployment.yaml

# Commit and push
git add deployment.yaml
git commit -m "Update nginx to 1.25.1"
git push

# ArgoCD will auto-detect changes (if auto-sync enabled)
# OR manually sync:
argocd app sync sample-nginx-app --grpc-web
argocd app wait sample-nginx-app --health
```

## Step 4: Verification Steps

### 4.1 Check Deployment Update
```bash
# Watch pods being recreated
kubectl get pods -l app=sample-nginx -w

# Verify new image
kubectl get deployment sample-nginx -o jsonpath='{.spec.template.spec.containers[0].image}'
# Should show: nginx:1.25.1

# Check pod image
kubectl get pods -l app=sample-nginx -o jsonpath='{.items[0].spec.containers[0].image}'
```

### 4.2 Check ArgoCD Application Health
```bash
# Get full application status
argocd app get sample-nginx-app

# Look for:
# - Sync Status: Synced
# - Health Status: Healthy

# Get detailed sync result
argocd app get sample-nginx-app -o json | jq '.status.sync'
```

### 4.3 Check Application Functionality
```bash
# Get service URL
minikube service sample-nginx --url

# Test the service
curl $(minikube service sample-nginx --url)

# OR port-forward and test
kubectl port-forward svc/sample-nginx 8081:80
curl localhost:8081
```

## Step 5: What to Observe for Agent Development

### Key Observations:
1. **Command Output Format**: Note the exact output of each argocd command
2. **Sync Duration**: How long does sync take?
3. **Status Transitions**: What statuses appear during deployment?
4. **Health Check Timing**: How long until "Healthy" status?
5. **Error Scenarios**: What happens if image doesn't exist?

### Capture Command Outputs:
```bash
# Get sync status
argocd app get sample-nginx-app --output json | jq '.status.sync.status'
# Output: "Synced" or "OutOfSync"

# Get health status
argocd app get sample-nginx-app --output json | jq '.status.health.status'
# Output: "Healthy", "Progressing", "Degraded", etc.

# Get operation state
argocd app get sample-nginx-app --output json | jq '.status.operationState.phase'
# Output: "Running", "Succeeded", "Failed"
```

## Step 6: Test Failure Scenarios

### 6.1 Invalid Image Tag
```bash
# Try to update with non-existent image
sed -i '' 's/nginx:1.25.1/nginx:999.999.999/g' deployment.yaml
git add deployment.yaml && git commit -m "Test invalid image" && git push

argocd app sync sample-nginx-app --grpc-web

# Observe:
# - What status does ArgoCD show?
# - How do pods behave? (ImagePullBackOff)
# - What does 'argocd app get' show?
```

### 6.2 Check Failure Detection
```bash
# Get health status
argocd app get sample-nginx-app

# Check pod status
kubectl get pods -l app=sample-nginx

# This will help you understand what to check in your agent
```

## Step 7: Agent Command Simulation

Here's what your Python agent will need to execute:

```bash
# 1. Login (if not already authenticated)
argocd login <argocd-server> --username <user> --password <pass> --grpc-web --insecure

# 2. Update manifest in Git (your agent will do this)
# - Clone repo
# - Update deployment.yaml with new image tag
# - Commit and push

# 3. Trigger sync
argocd app sync sample-nginx-app --grpc-web

# 4. Wait for completion
argocd app wait sample-nginx-app --health --timeout 300

# 5. Get final status
argocd app get sample-nginx-app --output json

# 6. Report back to GCC
# Parse JSON output and send status to your backend
```

## Key Learnings for Agent Development

1. **Authentication**: How will agent authenticate with ArgoCD?
   - Service account token
   - Username/password
   - API token

2. **Git Operations**: Agent needs to:
   - Clone repo
   - Update manifests
   - Commit & push

3. **Status Polling**: Agent should poll:
   - Every 5-10 seconds
   - Check both sync and health status
   - Timeout after X minutes

4. **Error Handling**: Agent must detect:
   - Sync failures
   - Health degradation
   - Timeout scenarios

## Next Steps

Once manual testing works:
1. Note all command outputs
2. Document timing (how long each step takes)
3. Identify what status checks are needed
4. Plan agent logic based on these observations
5. Start writing Python agent code

## Questions to Answer During Testing

- [ ] How long does a typical sync take?
- [ ] What's the exact JSON structure of status responses?
- [ ] How do you detect deployment completion?
- [ ] What errors can occur and how are they reported?
- [ ] Do readiness probes affect "Healthy" status timing?
- [ ] Can you run multiple syncs in parallel?
- [ ] What's the best way to authenticate agents?
