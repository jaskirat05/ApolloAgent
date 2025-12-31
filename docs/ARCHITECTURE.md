# ComfyUI Gateway Architecture

Complete system architecture and data flow documentation.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER APPLICATION                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                    ComfyUI SDK                              │    │
│  │  (comfyui_sdk.py)                                          │    │
│  │                                                             │    │
│  │  • execute_workflow()                                      │    │
│  │  • execute_workflow_async()                                │    │
│  │  • wait_for_job()                                          │    │
│  │  • get_job_status()                                        │    │
│  │  • download_image()                                        │    │
│  │  • register_server()                                       │    │
│  └─────────────────────┬──────────────────────────────────────┘    │
│                        │ HTTP/REST                                  │
└────────────────────────┼──────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GATEWAY API (FastAPI)                             │
│                    backend/main.py                                   │
│                    Port: 8000                                        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              API Endpoints                                    │  │
│  │                                                               │  │
│  │  POST   /workflow/execute      Execute workflow with auto    │  │
│  │                                 server selection & logging    │  │
│  │  GET    /workflow/status/{id}  Get job status (+ log path)   │  │
│  │  GET    /workflow/logs/{id}    Get log file contents         │  │
│  │  GET    /images/{filename}     Serve generated images        │  │
│  │  POST   /servers/register      Register ComfyUI server       │  │
│  │  GET    /servers               List servers                  │  │
│  │  GET    /servers/health        Get server health             │  │
│  │  POST   /prompt/queue          Queue on specific server      │  │
│  │  GET    /queue/{server}        Get queue status              │  │
│  │  POST   /prompt/{server}/interrupt  Interrupt execution      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐ │
│  │Load Balancer │ │Image Storage │ │ Job Tracker  │ │Auto Logger││
│  │              │ │              │ │              │ │           ││
│  │• Server      │ │• Download    │ │• In-memory   │ │• JSONL    ││
│  │  health      │ │  images      │ │  job status  │ │  logs     ││
│  │• Queue       │ │• Store       │ │• Workflow    │ │• History  ││
│  │  status      │ │  locally     │ │  data        │ │  based    ││
│  │• Select best │ │• Serve URLs  │ │• Prompt IDs  │ │• Zero     ││
│  │  server      │ │              │ │              │ │  config   ││
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────┘ │
│                                                                      │
└──────────────────┬───────────────────────────┬───────────────────┘
                   │                           │
                   │ HTTP                      │ HTTP
                   ▼                           ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│   ComfyUI Server #1          │  │   ComfyUI Server #2          │
│   procure-x.testmcp.org      │  │   localhost:8189             │
│                               │  │                               │
│  • Workflows execution        │  │  • Workflows execution        │
│  • Image generation           │  │  • Image generation           │
│  • Queue management           │  │  • Queue management           │
│  • Custom nodes               │  │  • Mock server (testing)      │
│                               │  │                               │
│  Port: 80/443                 │  │  Port: 8189                   │
└──────────────────────────────┘  └──────────────────────────────┘
```

## Component Details

### 1. SDK Layer (comfyui_sdk.py)

**Purpose**: Simple Python client for end users

**Key Methods**:
```python
sdk = ComfyUISDK(gateway_url="http://localhost:8000")

# Execute workflow (blocking)
result = sdk.execute_workflow(workflow)
# Returns: {"job_id", "status", "server_address", "images": [...]}

# Execute workflow (non-blocking)
job = sdk.execute_workflow_async(workflow)

# Check status
status = sdk.get_job_status(job_id)

# Wait for completion
result = sdk.wait_for_job(job_id, timeout=300)

# Download images
sdk.download_image(url, save_path)

# Server management
sdk.register_server(name, address)
sdk.get_servers_health()
```

**Dependencies**: `requests` library

---

### 2. Gateway API (backend/main.py)

**Purpose**: Central orchestration layer

**Core Components**:

#### A. Load Balancer (backend/load_balancer.py)
```python
# Server selection strategies
load_balancer.get_best_server(strategy="least_loaded")
# Strategies: "least_loaded", "round_robin", "random"

# Health tracking
ServerHealth:
  - is_online: bool
  - queue_running: int
  - queue_pending: int
  - total_load: int
  - last_check: datetime
  - error: Optional[str]
```

#### B. Image Storage (backend/storage.py)
```python
# Download and store images from ComfyUI
stored_images = image_storage.download_and_store_images(
    prompt_id=prompt_id,
    server_address=server_address,
    history_data=history_data
)

# Returns:
# [
#   {
#     "filename": "abc123_xyz.png",
#     "local_path": "/path/to/image",
#     "node_id": "73",
#     "prompt_id": "...",
#     "downloaded_at": "2025-01-01T00:00:00"
#   }
# ]

# Serve images
GET /images/{filename}  # Returns image file
```

#### C. Job Tracker (in-memory dict)
```python
jobs[job_id] = {
    "job_id": "uuid",
    "status": "queued|completed|failed",
    "server_address": "server:port",
    "prompt_id": "comfy_prompt_id",
    "images": ["http://gateway:8000/images/img1.png"],
    "queued_at": "ISO timestamp",
    "completed_at": "ISO timestamp",
    "log_file_path": "/path/to/log.jsonl",  # NEW: Automatic logging
    "workflow": {...},  # Stored for logging
    "error": "error message if failed"
}
```

#### D. Automatic Logging (gateway/observability/history_logger.py)

**Purpose**: Automatically create JSONL logs for every workflow execution

**Key Features**:
- **Zero Configuration** - Logs created automatically without manual setup
- **History-Based** - Created from ComfyUI's `/history/{prompt_id}` after execution
- **JSONL Format** - One JSON object per line for easy parsing
- **Complete Data** - Workflow, outputs, errors, and execution status

**How It Works**:
```python
# After execution completes, gateway calls:
log_file_path = create_log_from_history(
    prompt_id=prompt_id,
    server_address=server_address,
    workflow=workflow,
    history_data=history_data  # From ComfyUI /history endpoint
)

# Log file created at:
# gateway/core/logs/prompts/{timestamp}_{prompt_id}.jsonl
```

**Log Contents**:
- `workflow.submitted` - Initial workflow definition
- `node.executed` - Each node's output
- `execution.complete` - Success status
- `execution.error` - Error details if failed
- `workflow.success` / `workflow.failed` - Final status
- `history.complete` - Full ComfyUI history data

**Benefits**:
- Works for both sync and async execution
- Includes all error information for debugging
- Designed for automated debug agent analysis
- Persistent on disk for later review

**Access Logs**:
```python
# Via SDK response
result = sdk.execute_workflow(workflow)
log_path = result['log_file_path']

# Via API endpoint
GET /workflow/logs/{job_id}
# Returns: {log_entries: [...], entry_count: N}
```

See [Logging Guide](LOGGING.md) for complete documentation.

---

### 3. ComfyUI Client (comfyui_client.py)

**Purpose**: Low-level client for direct ComfyUI communication

**Key Methods**:
```python
client = ComfyUIClient(server_address="server:port")

# Queue workflow
response = client.post_prompt(workflow)
# Returns: {"prompt_id": "...", "number": 123}

# Get history/results
history = client.get_history(prompt_id)

# Queue status
queue = client.get_queue()
# Returns: {"queue_running": [...], "queue_pending": [...]}

# Cancel specific prompt
client.cancel_prompt(prompt_id)

# Global interrupt
client.interrupt()

# Download image from ComfyUI
image_data = client.download_image(filename, subfolder, type)

# Real-time updates
ws = client.track_updates(on_message_callback)
ws.run_forever()

# System info
stats = client.get_system_stats()
nodes = client.get_object_info()
```

---

## Data Flow

### Workflow Execution Flow

```
User Code
   │
   │ sdk.execute_workflow(workflow)
   ▼
┌──────────────────────────────────────────────────────────┐
│ SDK (comfyui_sdk.py)                                     │
│                                                           │
│ 1. POST /workflow/execute                                │
│    Body: {workflow, wait_for_completion, strategy}       │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────┐
│ Gateway (backend/main.py)                                │
│                                                           │
│ 2. Generate job_id                                       │
│ 3. Call load_balancer.get_best_server(strategy)         │
│    ├─> Update all server health                         │
│    ├─> Filter online servers                            │
│    └─> Select server with lowest load                   │
│                                                           │
│ 4. Create job entry (status: "queued")                  │
│                                                           │
│ 5. Call comfyui_client.post_prompt(workflow)            │
└───────────────────────┬──────────────────────────────────┘
                        │
                        │ HTTP POST /prompt
                        ▼
┌──────────────────────────────────────────────────────────┐
│ ComfyUI Server (selected by load balancer)              │
│                                                           │
│ 6. Validate workflow                                     │
│    ├─> Check nodes exist                                │
│    ├─> Check models available                           │
│    └─> Validate parameters                              │
│                                                           │
│ 7. Return prompt_id                                      │
└───────────────────────┬──────────────────────────────────┘
                        │
                        │ Response: {"prompt_id": "..."}
                        ▼
┌──────────────────────────────────────────────────────────┐
│ Gateway (backend/main.py)                                │
│                                                           │
│ 8. Update job with prompt_id                            │
│                                                           │
│ IF wait_for_completion = False:                         │
│   └─> Return job immediately                            │
│                                                           │
│ IF wait_for_completion = True:                          │
│   9. Connect to ComfyUI WebSocket                       │
│   10. Listen for events:                                │
│       ├─> "executing": node updates                     │
│       ├─> "progress": % complete                        │
│       └─> "executed": node completed                    │
│                                                           │
│   11. When execution completes:                         │
│       ├─> Get history (results)                         │
│       ├─> Download images from ComfyUI                  │
│       ├─> Store images locally                          │
│       ├─> Generate image URLs                           │
│       └─> Update job (status: "completed")             │
│                                                           │
│ 12. Return WorkflowExecutionResponse                    │
└───────────────────────┬──────────────────────────────────┘
                        │
                        │ Response: {"job_id", "images": [...]}
                        ▼
┌──────────────────────────────────────────────────────────┐
│ SDK (comfyui_sdk.py)                                     │
│                                                           │
│ 13. Return result to user                               │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ▼
                    User Code
```

### Async Workflow Flow

```
User Code
   │
   │ job = sdk.execute_workflow_async(workflow)
   ▼
SDK → Gateway (wait_for_completion=False)
   │
   │ Returns immediately with job_id
   ▼
User Code
   │
   │ ... do other work ...
   │
   │ status = sdk.get_job_status(job_id)
   ▼
SDK → Gateway GET /workflow/status/{job_id}
   │
   │ Returns: jobs[job_id]
   ▼
User Code
   │
   │ OR: result = sdk.wait_for_job(job_id)
   ▼
SDK (polls every 2 seconds until complete)
```

### Load Balancer Selection

```
load_balancer.get_best_server("least_loaded")
   │
   ├─> For each registered server:
   │   ├─> GET {server}/queue
   │   ├─> Parse queue_running + queue_pending
   │   ├─> Calculate total_load
   │   └─> Mark is_online = True
   │
   ├─> Filter: only online servers
   │
   └─> Select: min(servers, key=total_load)
       ├─> If tie: first registered wins
       └─> Return server address
```

### Image Download & Storage

```
Execution completes on ComfyUI
   │
   ├─> Gateway calls client.get_history(prompt_id)
   │   └─> Returns: {outputs: {node_id: {images: [...]}}}
   │
   ├─> For each image in outputs:
   │   ├─> GET {comfyui}/view?filename=...&type=output
   │   ├─> Download image bytes
   │   ├─> Generate unique filename: {prompt_id}_{uuid}.png
   │   ├─> Save to: backend/generated_images/{filename}
   │   └─> Store metadata
   │
   └─> Generate URLs:
       └─> http://localhost:8000/images/{filename}
```

---

## API Endpoints Reference

### SDK Endpoints (user-facing)

| Endpoint | Purpose |
|----------|---------|
| `POST /workflow/execute` | Execute workflow with auto server selection |
| `GET /workflow/status/{job_id}` | Get job status and results |
| `GET /images/{filename}` | Download generated image |
| `POST /servers/register` | Register new ComfyUI server |
| `GET /servers/health` | Get health of all servers |

### Direct Control Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /prompt/queue` | Queue on specific server |
| `GET /prompt/{server}/{id}` | Get prompt status |
| `GET /queue/{server}` | Get queue for server |
| `POST /prompt/{server}/interrupt` | Interrupt server |
| `GET /system/stats/{server}` | Get system info |
| `GET /system/nodes/{server}` | Get available nodes |

### ComfyUI Native Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /prompt` | Queue workflow |
| `GET /queue` | Get queue status |
| `GET /history/{prompt_id}` | Get results |
| `GET /view?filename=...` | Download image |
| `POST /interrupt` | Stop execution |
| `GET /system_stats` | System info |
| `GET /object_info` | Available nodes |

---

## Error Handling Chain

```
ComfyUI returns error
   │ 400 Bad Request
   │ Body: {"error": {"message": "Node not found", ...}}
   ▼
comfyui_client.py catches it
   │ Formats: "ComfyUI Error (400): {full JSON}"
   │ Raises: HTTPError with detailed message
   ▼
backend/main.py catches it
   │ Updates job status: "failed"
   │ Raises: HTTPException(500, detail="Workflow execution failed: ComfyUI Error...")
   ▼
comfyui_sdk.py catches it
   │ Formats: "Gateway Error (500): Workflow execution failed: ComfyUI Error..."
   │ Raises: HTTPError with full chain
   ▼
User sees complete error chain:
   "Gateway Error (500): Workflow execution failed:
    ComfyUI Error (400): {
      'error': {
        'message': 'Node WanCameraEmbedding not found',
        'details': '...'
      }
    }"
```

---

## Storage Structure

```
comfyautomate/
├── backend/
│   ├── main.py                    # FastAPI gateway
│   ├── load_balancer.py           # Server selection
│   ├── storage.py                 # Image storage
│   ├── requirements.txt           # Backend deps
│   └── generated_images/          # Stored images
│       ├── prompt1_abc123.png
│       ├── prompt1_def456.png
│       └── prompt2_xyz789.png
│
├── comfyui_client.py              # Low-level client
├── comfyui_sdk.py                 # High-level SDK
├── test_load_balancer.py          # Test script
├── workflows/
│   └── video_wan2_2_14B_fun_camera_test.json
└── requirements_sdk.txt           # SDK deps
```

---

## Server Registration Flow

```
sdk.register_server(name, address, description)
   │
   ▼
POST /servers/register
   │
   ├─> Test connection: GET {address}/system_stats
   ├─> If success:
   │   ├─> Add to registered_servers dict
   │   └─> Call load_balancer.register_server(address)
   │
   └─> Return: {"status": "registered", "server": {...}, "system_stats": {...}}
```

---

## WebSocket Event Flow

```
Gateway connects to ComfyUI WebSocket
   │
   │ ws://{server}/ws?clientId={client_id}
   ▼
ComfyUI sends events:
   │
   ├─> {"type": "status", "data": {...}}
   │   └─> Queue status update
   │
   ├─> {"type": "progress", "data": {"value": 5, "max": 10}}
   │   └─> Execution progress
   │
   ├─> {"type": "executing", "data": {"node": "73", "prompt_id": "..."}}
   │   └─> Node started
   │
   ├─> {"type": "executed", "data": {"node": "73", "output": {...}}}
   │   └─> Node completed
   │
   ├─> {"type": "executing", "data": {"node": null, "prompt_id": "..."}}
   │   └─> EXECUTION COMPLETE (node=null signals completion)
   │
   └─> {"type": "execution_error", "data": {...}}
       └─> Execution failed
```

---

## Key Design Decisions

### 1. Load Balancing Strategy
- **Default**: `least_loaded` - Selects server with fewest queued jobs
- **Tie-breaking**: First registered server wins (register important servers first)
- **Health checks**: Updated on every request to get_best_server()

### 2. Image Storage
- **Location**: `backend/generated_images/`
- **Naming**: `{prompt_id}_{uuid}.{ext}` for uniqueness
- **Serving**: Gateway serves via `/images/{filename}`
- **Cleanup**: Manual or via `image_storage.cleanup_old_images(days=7)`

### 3. Job Tracking
- **Storage**: In-memory dict (not persistent)
- **Limitation**: Jobs lost on gateway restart
- **Future**: Could move to Redis/PostgreSQL for persistence

### 4. Error Propagation
- **Strategy**: Chain errors with context at each layer
- **Format**: Include full response bodies from ComfyUI
- **Benefit**: Users see exact reason for failure

### 5. Sync vs Async Execution
- **Sync** (`wait=True`): Gateway waits, returns when complete
- **Async** (`wait=False`): Gateway returns immediately, poll for status
- **Use case**: Sync for quick workflows, async for long-running

### 6. Automatic Logging
- **Approach**: History-based, not real-time WebSocket tracking
- **When**: Logs created after execution completes
- **Format**: JSONL (one JSON object per line)
- **Location**: `gateway/core/logs/prompts/{timestamp}_{prompt_id}.jsonl`
- **Benefits**:
  - Zero configuration required
  - Works for both sync and async modes
  - Complete and accurate (from ComfyUI history)
  - No need for background WebSocket tracking
- **Trade-off**: No real-time progress events, but includes all final results and errors
- **Use case**: Automated debugging by debug agents

---

## Performance Considerations

### Bottlenecks
1. **WebSocket waiting**: Synchronous waiting blocks FastAPI worker
2. **Image downloads**: Sequential downloads can be slow
3. **In-memory jobs**: Limited by RAM

### Optimizations
1. Use `wait_for_completion=False` for parallel execution
2. Poll multiple jobs concurrently
3. Consider async/await for WebSocket handling
4. Add caching for frequently accessed images

### Scalability
- **Current**: Single gateway instance
- **Future**:
  - Multiple gateway instances (need shared job storage)
  - Redis for job tracking
  - S3/object storage for images
  - Message queue (RabbitMQ/Kafka) for job processing

---

## Security Considerations

### Current State
- ⚠️ No authentication
- ⚠️ No rate limiting
- ⚠️ CORS allows all origins
- ⚠️ No input validation on workflows

### Recommendations
- Add API keys for SDK access
- Implement rate limiting per client
- Validate workflow structure
- Sanitize file paths for image serving
- Add HTTPS support
- Restrict CORS to known origins

---

## Testing Strategy

### Unit Tests
- Load balancer server selection
- Image storage and retrieval
- Error message formatting

### Integration Tests
- Full workflow execution
- Server registration and health checks
- Multi-server load balancing

### Current Test
`test_load_balancer.py`:
1. Starts mock ComfyUI server
2. Registers real + mock servers
3. Tests load balancer selection
4. Queues workflow
5. Tests prompt cancellation

---

## Future Enhancements

### Planned
1. **Database integration**: PostgreSQL for job persistence
2. **Async execution**: Proper async/await throughout
3. **Batch operations**: Queue multiple workflows efficiently
4. **Priority queuing**: Assign priorities to jobs
5. **Resource limits**: CPU/GPU/memory-aware scheduling
6. **Metrics/monitoring**: Prometheus + Grafana
7. **Authentication**: JWT tokens
8. **Webhooks**: Notify on completion
9. **Workflow templates**: Pre-configured common workflows
10. **Admin dashboard**: Web UI for monitoring

### Under Consideration
- Multi-region support
- Automatic server discovery
- Workflow validation before queuing
- Cost tracking per job
- A/B testing different servers
