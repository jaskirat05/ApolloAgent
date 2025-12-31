# Artifact Database Implementation - Complete

## Overview

Successfully implemented database-backed artifact tracking system that replaces server-to-server file transfers with local storage and database persistence. This enables human-in-the-loop workflows, versioning, and audit trails.

## Implementation Summary

### 1. Database Schema ✅

**Location:** `temporal_gateway/database/models.py`

Created 4 main tables:
- **chains**: Track chain executions
- **workflows**: Track individual workflow executions (standalone or chain steps)
- **artifacts**: Track output files with versioning support
- **artifact_transfers**: Track file uploads to target servers

**Key Features:**
- `workflows.latest_artifact_id` - Denormalized pointer for fast lookups
- `artifacts.is_latest` - Boolean flag for current version
- `artifacts.parent_artifact_id` - For versioning/editing
- Cascade deletes for data integrity

### 2. CRUD Operations ✅

**Location:** `temporal_gateway/database/crud/`

Organized into separate files:
- `chain.py` - Chain operations
- `workflow.py` - Workflow operations
- `artifact.py` - Artifact operations
- `transfer.py` - Transfer operations

### 3. Database Session Management ✅

**Location:** `temporal_gateway/database/session.py`

- SQLite database by default (`temporal_gateway/data/artifacts.db`)
- Context manager support: `with get_session() as session:`
- Automatic table creation via `init_db()`

### 4. Activities Reorganization ✅

**Location:** `temporal_gateway/activities/`

Split monolithic `activities.py` into separate files:
- `select_server.py` - Server selection
- `download_artifacts.py` - Download WITHOUT DB (ephemeral)
- `download_artifacts_db.py` - Download WITH DB (required)
- `execution_log.py` - Execution logging
- `server_outputs.py` - Extract server output files
- `chain_templates.py` - Template resolution
- `chain_conditions.py` - Condition evaluation
- `workflow_parameters.py` - Parameter application
- `transfer_artifacts.py` - Transfer from local storage (NEW) + legacy server-to-server
- `execute_workflow.py` - Workflow execution
- `database_operations.py` - Database CRUD activities

### 5. New Activities for Database Integration ✅

#### `download_and_store_artifacts` (Required DB)
```python
async def download_and_store_artifacts(
    workflow_id: str,              # REQUIRED
    server_address: str,
    output_files: list[Dict]
) -> list[Dict]:
```
- Always persists to database
- Fails workflow if DB save fails
- Use for chains and trackable workflows

#### `download_and_store_images` (Optional DB)
```python
async def download_and_store_images(
    server_address: str,
    output_files: list[Dict],
    workflow_id: Optional[str] = None  # Optional
) -> list[Dict]:
```
- Works without database
- Use for ephemeral/temporary downloads

#### `transfer_artifacts_from_storage` (NEW)
```python
async def transfer_artifacts_from_storage(
    source_workflow_id: str,
    target_server: str,
    artifact_ids: List[str],        # Can use ["latest"]
    target_workflow_id: Optional[str] = None
) -> list[str]:
```
- Reads artifacts from database
- Loads files from local storage
- Uploads to target server
- Tracks transfers in database

#### Database Operation Activities
```python
create_chain_record()
create_workflow_record()
update_chain_status_activity()
update_workflow_status_activity()
get_workflow_artifacts()
```

### 6. Chain Executor Updates ✅

**Location:** `temporal_sdk/chains/workflows.py`

**New Flow:**
1. **Chain Start:** Create chain record in DB
2. **Each Level:** Update chain status in DB
3. **Each Step:**
   - Create workflow record in DB (before execution)
   - Get dependency artifacts from DB (not in-memory)
   - Transfer artifacts from local storage to target server
   - Execute child workflow with `workflow_db_id`
   - Update workflow status in DB
4. **Chain Complete:** Update final chain status

**Key Changes:**
- Added `_chain_id` to track database chain ID
- Added `_workflow_ids` to map step_id → workflow_id
- Replaced `transfer_outputs_to_input` with `transfer_artifacts_from_storage`
- Pass `workflow_db_id` to child workflows

### 7. ComfyUI Workflow Updates ✅

**Location:** `temporal_gateway/workflows.py`

**Changes:**
- Added `workflow_db_id` to `WorkflowExecutionRequest`
- Conditional artifact persistence:
  ```python
  if request.workflow_db_id:
      # Use download_and_store_artifacts (with DB)
  else:
      # Use download_and_store_images (without DB)
  ```

### 8. Worker Registration ✅

**Location:** `temporal_gateway/worker.py`

- Initialize database on startup: `init_db()`
- Registered all new activities with Temporal worker

## Complete Data Flow

### Chain Execution Flow

```
1. ChainExecutorWorkflow starts
   └─> create_chain_record() → chain_id

2. For each level:
   └─> update_chain_status_activity(level_num)

3. For each step:
   a. create_workflow_record() → workflow_db_id
   b. For each dependency:
      - get_workflow_artifacts(dep_workflow_id)
      - transfer_artifacts_from_storage(dep_workflow_id, target_server, artifact_ids)
   c. execute_child_workflow(workflow_db_id=workflow_db_id)
      - ComfyUIWorkflow receives workflow_db_id
      - execute_and_track_workflow()
      - download_and_store_artifacts(workflow_db_id, server, files)
         ├─> Downloads files from ComfyUI
         ├─> Saves to local storage
         ├─> Creates artifact records in DB
         └─> Updates workflow.latest_artifact_id
   d. update_workflow_status_activity("completed")

4. Chain completes:
   └─> update_chain_status_activity("completed")
```

### Artifact Transfer Flow (OLD vs NEW)

**OLD (Server-to-Server):**
```
Source Server/output/file.png
   ↓ download
Local Memory
   ↓ upload
Target Server/input/file.png
```

**NEW (Database-Backed):**
```
Source Server/output/file.png
   ↓ download_and_store_artifacts()
Local Storage (/path/to/artifacts/abc123.png)
   ↓ create_artifact() in DB
Database (workflow_id, artifact_id, local_path)
   ↓ [Human can edit here!]
   ↓ transfer_artifacts_from_storage()
Local Storage (/path/to/artifacts/abc123.png)
   ↓ upload
Target Server/input/file.png
```

## Human-in-the-Loop Workflow (Future)

With the database in place, we can now implement:

```python
# Step 1 completes
workflow_1 = get_workflow(id="wf-123")
artifact_1 = get_latest_artifact(workflow_1.id)

# Pause chain execution
# Human reviews artifact
print(f"Review: {artifact_1.local_path}")

# Human edits locally
edited_file = edit_image(artifact_1.local_path)

# Create new version
artifact_2 = create_artifact(
    workflow_id=workflow_1.id,
    local_path=edited_file,
    parent_artifact_id=artifact_1.id,
    version=2,
    approval_status="approved"
)
# Automatically sets:
# - artifact_1.is_latest = FALSE
# - artifact_2.is_latest = TRUE
# - workflow_1.latest_artifact_id = artifact_2.id

# Resume chain - uses edited version
chain.resume()
```

## Testing Checklist

- [ ] Database initializes on worker startup
- [ ] Chain record created when chain starts
- [ ] Workflow records created for each step
- [ ] Artifacts saved to database during execution
- [ ] Artifacts transferred from local storage (not server-to-server)
- [ ] Transfer records created and updated
- [ ] Chain status updated throughout execution
- [ ] Workflow status updated (queued → executing → completed/failed)
- [ ] Standalone workflows work without database (backward compatibility)
- [ ] Legacy transfer_outputs_to_input still works for old chains

## Files Modified/Created

### New Files
- `temporal_gateway/database/models.py`
- `temporal_gateway/database/session.py`
- `temporal_gateway/database/crud/chain.py`
- `temporal_gateway/database/crud/workflow.py`
- `temporal_gateway/database/crud/artifact.py`
- `temporal_gateway/database/crud/transfer.py`
- `temporal_gateway/database/crud/__init__.py`
- `temporal_gateway/database/__init__.py`
- `temporal_gateway/activities/select_server.py`
- `temporal_gateway/activities/download_artifacts.py`
- `temporal_gateway/activities/download_artifacts_db.py`
- `temporal_gateway/activities/execution_log.py`
- `temporal_gateway/activities/server_outputs.py`
- `temporal_gateway/activities/chain_templates.py`
- `temporal_gateway/activities/chain_conditions.py`
- `temporal_gateway/activities/workflow_parameters.py`
- `temporal_gateway/activities/transfer_artifacts.py`
- `temporal_gateway/activities/execute_workflow.py`
- `temporal_gateway/activities/database_operations.py`
- `temporal_gateway/activities/__init__.py`

### Modified Files
- `temporal_gateway/worker.py` - Added init_db(), registered new activities
- `temporal_gateway/workflows.py` - Added workflow_db_id support
- `temporal_sdk/chains/workflows.py` - Complete database integration
- `temporal_sdk/chains/models.py` - Added workflow_db_id to StepResult
- `pyproject.toml` - Added sqlalchemy, alembic, aiosqlite

### Backup Files
- `temporal_gateway/activities_old.py.backup` - Original monolithic activities file

## Next Steps

1. **Create Artifact Management API** - Endpoints for querying/managing artifacts
2. **Test Database Operations** - End-to-end testing of chain execution
3. **Add Alembic Migrations** - Proper database schema versioning
4. **Add Approval Workflows** - UI/API for approving/rejecting artifacts
5. **Add S3 Storage Backend** - Option to store artifacts in S3
6. **Add Artifact Pruning** - Auto-delete old artifacts after N days

## Dependencies Added

```toml
sqlalchemy = ">=2.0.0"
alembic = ">=1.13.0"
aiosqlite = ">=0.19.0"
```

Installed successfully via `uv sync`.
