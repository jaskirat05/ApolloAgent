# Getting Started with Temporal Gateway

This guide will get you running the Temporal-based ComfyUI gateway in 5 minutes.

## Prerequisites

- ✅ Temporal CLI installed (you already have this)
- ✅ Temporal Python SDK installed (you already have this)
- Python 3.10+
- Access to ComfyUI server

## Step-by-Step Setup

### Terminal 1: Start Temporal Server

```bash
temporal server start-dev
```

**What this does**:
- Starts Temporal Server on `localhost:7233`
- Starts Temporal UI on `http://localhost:8233`
- Uses SQLite for storage (good for dev)

**You should see**:
```
Temporal server is running.
Temporal UI is at: http://localhost:8233
```

**Leave this running**. Open `http://localhost:8233` in your browser to see the UI!

---

### Terminal 2: Start Temporal Worker

```bash
cd /home/jaskirat/Documents/comfyautomate
python temporal_gateway/worker.py
```

**What this does**:
- Connects to Temporal Server
- Registers workflows and activities
- Waits for work to execute

**You should see**:
```
============================================================
Temporal Worker Started
============================================================
Connected to: localhost:7233
Task Queue: comfyui-gpu-farm
Workflows: ['ComfyUIWorkflow']
Activities: 5 registered
============================================================

Worker is running. Press Ctrl+C to stop.
Waiting for workflows to execute...
```

**Leave this running**.

---

### Terminal 3: Start Temporal Gateway

```bash
cd /home/jaskirat/Documents/comfyautomate
python temporal_gateway/main.py
```

**What this does**:
- Starts FastAPI server on `http://localhost:8001`
- Provides HTTP API for workflow execution
- Connects to Temporal Server

**You should see**:
```
============================================================
Temporal Gateway Started
============================================================
Connected to Temporal: localhost:7233
Gateway API: http://localhost:8001
Temporal UI: http://localhost:8233
============================================================
INFO:     Uvicorn running on http://0.0.0.0:8001
```

**Leave this running**.

---

### Terminal 4: Test It!

```bash
cd /home/jaskirat/Documents/comfyautomate
python tests/test_temporal_comparison.py
```

This will:
1. Register a ComfyUI server
2. Execute a workflow via Temporal
3. Show real-time progress
4. Display results

**You should see**:
```
Workflow started: workflow-abc123
Temporal UI: http://localhost:8233/namespaces/default/workflows/workflow-abc123

[selecting_server] Server: procure-x.testmcp.org
[queueing] Workflow queued
[executing] Node: 3, Progress: 25.0%
[executing] Node: 7, Progress: 50.0%
...
✓ TEMPORAL GATEWAY SUCCESS
```

---

## What's Happening Behind the Scenes

```
[Test Script]
     ↓
  SDK.execute_workflow()
     ↓
[FastAPI Gateway :8001]
  temporal_client.start_workflow()
     ↓
[Temporal Server :7233]
  "New workflow! Who can handle it?"
     ↓
[Worker]
  "I can! Let me execute it..."
  - select_server activity
  - queue_workflow activity
  - track_execution activity (sends heartbeats)
  - download_images activity
  - create_log activity
     ↓
[ComfyUI Server]
  Actually renders the workflow
     ↓
[Worker]
  Returns result to Temporal
     ↓
[Temporal Server]
  Marks workflow complete
     ↓
[SDK]
  Gets final result with images
```

---

## Explore Temporal UI

Open `http://localhost:8233` in your browser.

You'll see:
1. **Workflows** tab - All your workflows
2. Click on a workflow to see:
   - Full execution history
   - Current status
   - Activity results
   - Heartbeat data
   - Input/output
   - Timeline

Try this:
1. Start a workflow
2. Immediately go to Temporal UI
3. Find your workflow in the list
4. Click on it
5. Watch it execute in real-time!

---

## Try Breaking Things!

### Test 1: Crash Recovery

1. Start a workflow (use a long-running one)
2. While it's running, **kill the worker** (Ctrl+C in Terminal 2)
3. Watch what happens:
   - Temporal detects worker died
   - Workflow shows as "running" but no heartbeats
4. **Restart the worker**: `python temporal_gateway/worker.py`
5. Magic: Workflow resumes exactly where it left off!

### Test 2: Query Running Workflow

```python
from temporalio.client import Client

client = await Client.connect("localhost:7233")
handle = client.get_workflow_handle("workflow-abc123")

# Get current status
status = await handle.query("get_status")
print(status)  # Shows current node, progress, etc.
```

### Test 3: Cancel a Workflow

```python
# Via SDK
sdk.cancel_workflow("workflow-abc123")

# Or via Temporal client
await handle.signal("cancel")
```

---

## Common Issues

### "Connection refused" on port 7233
**Fix**: Make sure Temporal Server is running (`temporal server start-dev`)

### Worker says "No activities"
**Fix**: Check imports in `worker.py` - make sure all activities are imported

### Gateway can't start workflows
**Fix**: Make sure worker is running and connected

### Workflow stuck
**Fix**:
1. Check Temporal UI for errors
2. Check worker logs
3. Look at activity heartbeats

---

## Production Checklist

For GPU farm production:

- [ ] Use PostgreSQL instead of SQLite
- [ ] Run Temporal Server in docker-compose
- [ ] Run multiple workers for redundancy
- [ ] Set up monitoring/alerting
- [ ] Configure retry policies per your needs
- [ ] Set appropriate timeouts for activities
- [ ] Use Temporal Cloud (optional, paid)

---

## Next Steps

1. ✅ Test basic workflow execution
2. ✅ Explore Temporal UI
3. ✅ Try crash recovery
4. Try with your own workflows
5. Integrate with AI debugging agent
6. Deploy to production

## Need Help?

- Temporal UI: http://localhost:8233
- Temporal Docs: https://docs.temporal.io/
- Code: `/home/jaskirat/Documents/comfyautomate/temporal_gateway/`

Enjoy your durable GPU farm! 🚀
