# Mock GCC API

Mock Global Control Center API for testing deployment updates.

## Setup

```bash
cd mock-gcc
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python mock_gcc.py
```

The API will be available at `http://localhost:5000`

## Test API

```bash
# Check for updates (should be none initially)
curl http://localhost:5000/api/v1/clients/101/updates

# Trigger a deployment
curl -X POST http://localhost:5000/api/v1/admin/trigger-deployment \
  -H "Content-Type: application/json" \
  -d '{"image_tag": "v2.0.0"}'

# Check for updates again (should show pending update)
curl http://localhost:5000/api/v1/clients/101/updates

# Check admin status
curl http://localhost:5000/api/v1/admin/status
```

## Environment Variables

- `PORT`: Port to listen on (default: 5000)
