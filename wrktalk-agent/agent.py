#!/usr/bin/env python3

import requests
import subprocess
import json
import time
import sys
import os
from datetime import datetime

# Configuration from environment variables
CLIENT_ID = int(os.getenv('CLIENT_ID', '101'))
GCC_API_URL = os.getenv('GCC_API_URL', 'http://localhost:5000/api/v1')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '10'))

# ArgoCD Configuration
ARGOCD_SERVER = os.getenv('ARGOCD_SERVER', 'localhost:8080')
ARGOCD_USERNAME = os.getenv('ARGOCD_USERNAME', 'admin')
ARGOCD_PASSWORD = os.getenv('ARGOCD_PASSWORD', '')
ARGOCD_APP_NAME = os.getenv('ARGOCD_APP_NAME', 'wrktalk-test-app')

def log(message):
    """Print log message with timestamp"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

def check_argocd_cli():
    """Check if ArgoCD CLI is installed and working"""
    try:
        result = subprocess.run(
            ['argocd', 'version', '--client'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def check_gcc_connectivity():
    """Check if GCC API is reachable"""
    try:
        health_url = GCC_API_URL.replace('/api/v1', '') + '/health'
        response = requests.get(health_url, timeout=5)
        return response.status_code == 200
    except:
        return False

def login_to_argocd():
    """Login to ArgoCD"""
    try:
        log("Logging in to ArgoCD...")
        cmd = [
            'argocd', 'login', ARGOCD_SERVER,
            '--username', ARGOCD_USERNAME,
            '--password', ARGOCD_PASSWORD,
            '--insecure'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            log("✓ Logged in to ArgoCD")
            return True
        else:
            log(f"❌ Failed to login to ArgoCD: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        log("❌ ArgoCD login timeout")
        return False
    except Exception as e:
        log(f"❌ ArgoCD login error: {e}")
        return False

def poll_for_updates():
    """Poll GCC for pending updates"""
    try:
        response = requests.get(
            f"{GCC_API_URL}/clients/{CLIENT_ID}/updates",
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        log(f"Failed to poll GCC: {e}")
        return None

def execute_deployment(update_data):
    """Execute deployment using ArgoCD"""
    
    deployment_id = update_data['deployment_id']
    target_tag = update_data['target_version']['tag']
    
    log("=" * 60)
    log("🚀 DEPLOYMENT STARTING")
    log(f"Deployment ID: {deployment_id}")
    log(f"Target Version: {target_tag}")
    log("=" * 60)
    
    try:
        # Login to ArgoCD (session may have expired)
        if not login_to_argocd():
            raise Exception("Failed to authenticate with ArgoCD")
        
        report_status(deployment_id, 'in_progress', 'Updating ArgoCD application')
        
        # Step 1: Update ArgoCD application
        log(f"Step 1: Setting image tag to {target_tag}...")
        cmd = [
            'argocd', 'app', 'set', ARGOCD_APP_NAME,
            '--helm-set', f'image.tag={target_tag}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise Exception(f"ArgoCD set failed: {result.stderr}")
        
        log("✓ Image tag updated in ArgoCD")

        # Step 2: Manually trigger sync
        log("Step 2: Triggering manual sync...")
        cmd = [
            'argocd', 'app', 'sync', ARGOCD_APP_NAME,
            '--prune'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            raise Exception(f"ArgoCD sync failed: {result.stderr}")

        log("✓ Sync triggered successfully")
        time.sleep(5)
        
        # Step 3: Monitor deployment
        log("Step 3: Monitoring deployment progress...")
        report_status(deployment_id, 'in_progress', 'Waiting for pods to be healthy')
        
        max_attempts = 60  # 10 minutes
        for attempt in range(max_attempts):
            cmd = [
                'argocd', 'app', 'get', ARGOCD_APP_NAME,
                '-o', 'json'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                app_status = json.loads(result.stdout)
                
                sync_status = app_status['status']['sync']['status']
                health_status = app_status['status']['health']['status']
                
                log(f"  Status: Sync={sync_status}, Health={health_status}")
                
                if sync_status == 'Synced' and health_status == 'Healthy':
                    log("✓ Deployment synced and healthy!")
                    break
                
                if health_status == 'Degraded':
                    raise Exception("Deployment health degraded")
            
            time.sleep(10)
        else:
            raise Exception("Timeout waiting for deployment")
        
        # Success!
        log("=" * 60)
        log("✅ DEPLOYMENT SUCCESSFUL")
        log("=" * 60)
        
        report_status(
            deployment_id,
            'success',
            'Deployment completed successfully',
            deployed_version=target_tag
        )
        
        return True
        
    except Exception as e:
        log(f"❌ DEPLOYMENT FAILED: {e}")
        report_status(
            deployment_id,
            'failed',
            f'Deployment failed: {str(e)}'
        )
        return False

def report_status(deployment_id, status, message, **kwargs):
    """Report status back to GCC"""
    
    payload = {
        'deployment_id': deployment_id,
        'client_id': CLIENT_ID,
        'status': status,
        'message': message,
        **kwargs
    }
    
    try:
        response = requests.post(
            f"{GCC_API_URL}/clients/{CLIENT_ID}/status",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            log(f"✓ Status '{status}' reported to GCC")
        else:
            log(f"Failed to report status: HTTP {response.status_code}")
    except Exception as e:
        log(f"Error reporting status: {e}")

def main():
    """Main agent loop"""
    
    log("=" * 60)
    log("WrkTalk Deployment Agent Starting")
    log("=" * 60)
    log(f"Client ID: {CLIENT_ID}")
    log(f"GCC API: {GCC_API_URL}")
    log(f"ArgoCD App: {ARGOCD_APP_NAME}")
    log(f"ArgoCD Server: {ARGOCD_SERVER}")
    log(f"Poll Interval: {POLL_INTERVAL}s")
    log("=" * 60)
    
    # Pre-flight checks
    log("Running pre-flight checks...")
    
    if not check_argocd_cli():
        log("ERROR: argocd CLI not found or not working")
        log("ERROR: Prerequisites check failed. Exiting.")
        sys.exit(1)
    
    log("✓ ArgoCD CLI found")
    
    # Check GCC connectivity
    if check_gcc_connectivity():
        log(f"✓ GCC API reachable at {GCC_API_URL}")
    else:
        log(f"⚠️  Warning: Cannot reach GCC API at {GCC_API_URL}")
        log("⚠️  Will continue and retry connections...")
    
    # Initial login
    log("Attempting initial ArgoCD login...")
    if not login_to_argocd():
        log("⚠️  Warning: Initial ArgoCD login failed")
        log("⚠️  Will retry on first deployment...")
    
    log("Starting polling loop...")
    log("=" * 60)
    
    while True:
        try:
            # Poll for updates
            update_data = poll_for_updates()
            
            if update_data and update_data.get('has_update'):
                log("\n📦 New deployment detected!")
                execute_deployment(update_data)
                log("\nResuming polling...")
            else:
                print(".", end="", flush=True)
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            log("\n\nAgent stopped by user")
            sys.exit(0)
        except Exception as e:
            log(f"\nError in agent loop: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main()