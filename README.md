# ComfyAutomate

A clean, modular system for automating ComfyUI workflows with load balancing and observability.

## Project Structure

```
comfyautomate/
├── sdk/                    # Client SDK for end users
│   └── client.py          # ComfyUISDK class
│
├── gateway/               # FastAPI backend service
│   ├── main.py           # App entry point
│   ├── api/              # API route handlers
│   │   ├── workflow.py   # Workflow execution endpoints
│   │   └── servers.py    # Server management endpoints
│   ├── core/             # Core business logic
│   │   ├── comfyui_client.py  # Low-level ComfyUI client
│   │   ├── load_balancer.py   # Server selection
│   │   ├── storage.py         # Image storage
│   │   └── logs/              # Generated log files
│   │       └── prompts/       # Per-prompt JSONL logs
│   ├── observability/    # Logging & monitoring
│   │   ├── history_logger.py  # Automatic log creation
│   │   ├── prompt_logger.py   # Manual logging (legacy)
│   │   └── log_reader.py      # Log analysis & parsing
│   └── models/           # Pydantic schemas
│       ├── requests.py
│       └── responses.py
│
├── tests/                # Test scripts
├── docs/                 # Documentation
├── examples/             # Usage examples
└── workflows/            # Example workflow JSONs
```

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Start the Gateway

```bash
source .venv/bin/activate
uv run run_gateway.py
```

### 3. Use the SDK

```python
from sdk import ComfyUISDK
import json

# Initialize SDK
sdk = ComfyUISDK(gateway_url="http://localhost:8000")

# Register a ComfyUI server
sdk.register_server(
    name="My Server",
    address="127.0.0.1:8188"
)

# Execute a workflow (automatic logging included!)
with open('workflows/my_workflow.json') as f:
    workflow = json.load(f)

result = sdk.execute_workflow(workflow)
print(f"Images: {result['images']}")
print(f"Log: {result['log_file_path']}")  # Automatic log file
```

## Features

- **Load Balancing** - Automatically selects the best available server based on queue load
- **Image Storage** - Downloads and serves generated images via URLs
- **Automatic Logging** - Every workflow execution is logged automatically (JSONL format)
- **Sync & Async Modes** - Block for results or poll asynchronously
- **Clean Architecture** - Modular design with clear separation of concerns

## Automatic Logging

Every workflow execution is automatically logged without any manual setup:

```python
# Logs are created automatically
result = sdk.execute_workflow(workflow)

# Access log file path
print(result['log_file_path'])
# Output: gateway/core/logs/prompts/20250124_123456_abc123.jsonl

# Retrieve logs via API
import requests
logs = requests.get(f"http://localhost:8000/workflow/logs/{result['job_id']}").json()
print(f"Total events: {logs['entry_count']}")
```

Logs contain:
- Workflow definition
- Execution timeline
- Node outputs
- Error details (if any)
- ComfyUI history data

Perfect for debugging failed workflows! See [Logging Guide](docs/LOGGING.md) for details.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and data flows
- [Logging Guide](docs/LOGGING.md) - Automatic logging explained
- [API Reference](docs/ComfyUI_API_Documentation.md) - Complete API docs

## Development

```bash
# Start gateway
uv run run_gateway.py

# Run tests
python tests/test_sync_async_execution.py

# Check server health
curl http://localhost:8000/servers/health

# View logs
ls gateway/core/logs/prompts/

# View images
ls gateway/core/generated_images/
```
