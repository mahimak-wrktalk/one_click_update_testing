#!/usr/bin/env python3
"""
Mock GCC (Global Control Center) API
This simulates the central API that manages deployment updates across multiple clients.
"""

from flask import Flask, request, jsonify
from datetime import datetime
import os

app = Flask(__name__)

# Simulated state (in production, this would be a database)
pending_update = None
deployment_status = {}

@app.route('/api/v1/clients/<int:client_id>/updates', methods=['GET'])
def get_updates(client_id):
    """
    Agent polls this endpoint to check for pending updates

    Response format:
    {
        "has_update": true,
        "deployment_id": "dpl-20250120123456",
        "component": "backend",
        "target_version": {
            "tag": "v2.0.0"
        },
        "action": "deploy"
    }
    """
    global pending_update

    if pending_update:
        return jsonify({
            'has_update': True,
            'deployment_id': pending_update['deployment_id'],
            'component': 'backend',
            'target_version': {
                'tag': pending_update['image_tag']
            },
            'action': 'deploy'
        })

    return jsonify({'has_update': False})

@app.route('/api/v1/clients/<int:client_id>/status', methods=['POST'])
def report_status(client_id):
    """
    Agent reports deployment status here

    Expected payload:
    {
        "deployment_id": "dpl-20250120123456",
        "client_id": 101,
        "status": "in_progress|success|failed",
        "message": "Status message",
        "deployed_version": "v2.0.0" (optional, on success)
    }
    """
    data = request.json

    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] Status Report from Client {client_id}:")
    print(f"  Deployment ID: {data.get('deployment_id')}")
    print(f"  Status: {data.get('status')}")
    print(f"  Message: {data.get('message')}")
    if 'deployed_version' in data:
        print(f"  Deployed Version: {data.get('deployed_version')}")
    print(f"{'='*60}\n")

    # Store deployment status
    deployment_status[data.get('deployment_id')] = {
        **data,
        'reported_at': datetime.now().isoformat()
    }

    # Clear pending update on success
    if data.get('status') == 'success':
        global pending_update
        pending_update = None

    return jsonify({'status': 'received'})

@app.route('/api/v1/admin/trigger-deployment', methods=['POST'])
def trigger_deployment():
    """
    Admin endpoint to trigger a new deployment
    Simulates action from GCC UI

    Payload:
    {
        "image_tag": "v2.0.0"
    }
    """
    global pending_update

    data = request.json
    image_tag = data.get('image_tag', 'v2.0.0')

    pending_update = {
        'deployment_id': f"dpl-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'image_tag': image_tag,
        'created_at': datetime.now().isoformat()
    }

    print(f"\n{'='*60}")
    print(f"Deployment Triggered:")
    print(f"  Deployment ID: {pending_update['deployment_id']}")
    print(f"  Target Tag: {image_tag}")
    print(f"{'='*60}\n")

    return jsonify({
        'success': True,
        'deployment_id': pending_update['deployment_id'],
        'message': f'Deployment to tag {image_tag} triggered'
    })

@app.route('/api/v1/admin/status', methods=['GET'])
def get_deployment_status():
    """
    Admin endpoint to check overall deployment status
    """
    return jsonify({
        'pending_update': pending_update,
        'deployment_history': deployment_status
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    print("=" * 60)
    print("Mock GCC API Starting...")
    print("=" * 60)
    print("Endpoints:")
    print("  GET  /api/v1/clients/<id>/updates        - Agent polls here")
    print("  POST /api/v1/clients/<id>/status         - Agent reports here")
    print("  POST /api/v1/admin/trigger-deployment    - Trigger update")
    print("  GET  /api/v1/admin/status                - Check status")
    print("  GET  /health                             - Health check")
    print("=" * 60)

    port = int(os.getenv('PORT', 5000))
    print(f"\nListening on http://0.0.0.0:{port}")
    print("=" * 60)

    app.run(host='0.0.0.0', port=port, debug=True)
