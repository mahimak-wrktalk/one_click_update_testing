#!/usr/bin/env python3
"""
WrkTalk Deployment Agent

This agent polls the GCC (Global Control Center) API for pending updates
and executes deployments via ArgoCD when new versions are available.
"""

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
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '10'))  # seconds
ARGOCD_APP_NAME = os.getenv('ARGOCD_APP_NAME', 'wrktalk-test-app')
ARGOCD_SERVER = os.getenv('ARGOCD_SERVER', 'localhost:8083')
ARGOCD_AUTH_TOKEN = os.getenv('ARGOCD_AUTH_TOKEN', '')

def log(message):
    """Print log message with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}", flush=True)

def poll_for_updates():
    """
    Poll GCC for pending updates

    Returns:
        dict: Update data if available, None otherwise
    """
    try:
        response = requests.get(
            f"{GCC_API_URL}/clients/{CLIENT_ID}/updates",
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            log(f"Error polling: HTTP {response.status_code}")
            return None
    except Exception as e:
        log(f"Failed to poll GCC: {e}")
        return None

def execute_deployment(update_data):
    """
    Execute deployment using ArgoCD

    Args:
        update_data (dict): Update information from GCC

    Returns:
        bool: True if deployment succeeded, False otherwise
    """

    deployment_id = update_data['deployment_id']
    target_tag = update_data['target_version']['tag']

    log("=" * 60)
    log("🚀 DEPLOYMENT STARTING")
    log(f"Deployment ID: {deployment_id}")
    log(f"Target Version: {target_tag}")
    log("=" * 60)

    try:
        # Step 1: Report in_progress
        report_status(deployment_id, 'in_progress', 'Updating ArgoCD application')

        # Step 2: Update ArgoCD application
        log(f"Step 1: Setting image tag to {target_tag}...")

        cmd = build_argocd_command([
            'app', 'set', ARGOCD_APP_NAME,
            '--helm-set', f'image.tag={target_tag}'
        ])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"ArgoCD set failed: {result.stderr}")

        log("✓ Image tag updated in ArgoCD")

        # Step 3: Trigger sync
        log("Step 2: Triggering ArgoCD sync...")

        cmd = build_argocd_command([
            'app', 'sync', ARGOCD_APP_NAME
        ])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"ArgoCD sync failed: {result.stderr}")

        log("✓ ArgoCD sync triggered")

        # Step 4: Wait for sync to complete and be healthy
        log("Step 3: Waiting for deployment to complete...")
        report_status(deployment_id, 'in_progress', 'Waiting for pods to be healthy')

        max_attempts = 60  # 10 minutes
        for attempt in range(max_attempts):
            cmd = build_argocd_command([
                'app', 'get', ARGOCD_APP_NAME,
                '-o', 'json'
            ])

            result = subprocess.run(cmd, capture_output=True, text=True)

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
    """
    Report status back to GCC

    Args:
        deployment_id (str): Deployment identifier
        status (str): Status (in_progress, success, failed)
        message (str): Status message
        **kwargs: Additional fields to include
    """

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

def build_argocd_command(args):
    """
    Build ArgoCD CLI command with authentication

    Args:
        args (list): Command arguments

    Returns:
        list: Complete command with auth parameters
    """
    cmd = ['argocd'] + args

    # Add server if specified
    if ARGOCD_SERVER:
        cmd.extend(['--server', ARGOCD_SERVER])

    # Add auth token if specified
    if ARGOCD_AUTH_TOKEN:
        cmd.extend(['--auth-token', ARGOCD_AUTH_TOKEN])

    # Use gRPC web for compatibility
    cmd.append('--grpc-web')

    # Skip server certificate verification in dev/test environments
    # In production, remove this and use proper certificates
    if os.getenv('ARGOCD_INSECURE', 'false').lower() == 'true':
        cmd.append('--insecure')

    return cmd

def verify_prerequisites():
    """
    Verify that required tools and configuration are available

    Returns:
        bool: True if all prerequisites are met
    """
    # Check if argocd CLI is available
    try:
        result = subprocess.run(['argocd', 'version'], capture_output=True, text=True)
        if result.returncode != 0:
            log("ERROR: argocd CLI not found or not working")
            return False
        log(f"✓ ArgoCD CLI found")
    except FileNotFoundError:
        log("ERROR: argocd CLI not found in PATH")
        return False

    # Verify GCC API is reachable
    try:
        response = requests.get(f"{GCC_API_URL.split('/api')[0]}/health", timeout=5)
        if response.status_code == 200:
            log(f"✓ GCC API reachable at {GCC_API_URL}")
        else:
            log(f"WARNING: GCC API returned status {response.status_code}")
    except Exception as e:
        log(f"WARNING: Could not reach GCC API: {e}")
        log("Agent will continue but may not work correctly")

    return True

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

    # Verify prerequisites
    if not verify_prerequisites():
        log("ERROR: Prerequisites check failed. Exiting.")
        sys.exit(1)

    log("Starting polling loop...")
    log("=" * 60)

    consecutive_errors = 0
    max_consecutive_errors = 10

    while True:
        try:
            # Poll for updates
            update_data = poll_for_updates()

            if update_data and update_data.get('has_update'):
                log("\n📦 New deployment detected!")
                success = execute_deployment(update_data)

                if success:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1

                log("\nResuming polling...")
            else:
                # Print a dot to show we're still alive
                print(".", end="", flush=True)
                consecutive_errors = 0

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log("\n\nAgent stopped by user")
            sys.exit(0)
        except Exception as e:
            log(f"\nError in agent loop: {e}")
            consecutive_errors += 1

            if consecutive_errors >= max_consecutive_errors:
                log(f"ERROR: Too many consecutive errors ({consecutive_errors}). Exiting.")
                sys.exit(1)

            time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main()
