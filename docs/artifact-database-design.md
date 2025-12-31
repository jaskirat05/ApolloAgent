# Artifact Database Design

## Overview

Replace server-to-server file transfers with a local artifact database that:
- Stores all workflow outputs locally
- Tracks metadata (chain, workflow, server, timestamps)
- Enables editing/approval workflows before chaining
- Provides audit trail and versioning

## Current vs Proposed Flow

### Current Flow (Server-to-Server)
```
Step 1: Server A → outputs to Server A/output/
Step 2: Download from Server A → Upload to Server B → Execute on Server B
```

**Problems:**
- Files can disappear if source server restarts
- No human intervention possible
- No audit trail
- Wasteful transfers

### Proposed Flow (Local Artifacts)
```
Step 1: Server A → outputs to Server A/output/ → Download to local storage + DB
[Optional: Human edits/approves artifacts in local storage]
Step 2: Upload from local storage → Server B → Execute on Server B
```

**Benefits:**
- Single source of truth (local storage)
- Human-in-the-loop workflows
- Versioning & audit trail
- Resilient to server restarts
- Can edit outputs before continuing chain

## Entity Relationships

```
chains (1) ─────< workflows (many) ─────< artifacts (many)
                      │
                      └──> latest_artifact_id (1)
```

- A **chain** can have multiple **workflows** (steps)
- A **workflow** can be standalone (chain_id = NULL) or part of a chain
- A **workflow** can generate multiple **artifacts** (outputs)
- A **workflow** has a `latest_artifact_id` pointing to the current/approved artifact
- **Artifacts** can be versioned (parent_artifact_id creates version chain)

## Database Schema

### Table: chains

Represents a chain execution (e.g., "image-edit-to-video-pipeline").

```sql
CREATE TABLE chains (
    id TEXT PRIMARY KEY,  -- UUID
    name TEXT NOT NULL,  -- Chain name from YAML (e.g., "image-edit-to-video-pipeline")
    description TEXT,

    -- Temporal workflow info
    temporal_workflow_id TEXT UNIQUE,
    temporal_run_id TEXT,

    -- Status
    status TEXT NOT NULL,  -- 'initializing', 'executing_level_N', 'completed', 'failed', 'cancelled'
    current_level INTEGER DEFAULT 0,

    -- Timestamps
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,

    -- Results
    error_message TEXT,
    chain_definition JSON,  -- The full chain YAML as JSON

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chains_temporal ON chains(temporal_workflow_id);
CREATE INDEX idx_chains_status ON chains(status);
CREATE INDEX idx_chains_started ON chains(started_at DESC);
```

### Table: workflows

Represents individual workflow executions (steps in a chain OR standalone workflows).

```sql
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,  -- UUID

    -- Chain relationship (NULL for standalone workflows)
    chain_id TEXT,  -- FK to chains, NULL if standalone
    step_id TEXT,  -- Step ID from chain YAML (e.g., "extract_frame1"), NULL if standalone

    -- Workflow info
    workflow_name TEXT NOT NULL,  -- e.g., "imageSave", "qwen_image_edit"
    server_address TEXT NOT NULL,
    prompt_id TEXT NOT NULL,

    -- Temporal workflow info (for standalone workflows or child workflows)
    temporal_workflow_id TEXT,
    temporal_run_id TEXT,

    -- Status
    status TEXT NOT NULL,  -- 'queued', 'executing', 'completed', 'failed', 'skipped'

    -- Latest artifact reference (denormalized for quick access)
    latest_artifact_id TEXT,  -- FK to artifacts, updated when new artifact is approved

    -- Timestamps
    queued_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Execution details
    error_message TEXT,
    workflow_definition JSON,  -- The actual workflow JSON sent to ComfyUI
    parameters JSON,  -- Resolved parameters used (e.g., {"1.video": "ComfyUI_00012_.mp4"})

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (chain_id) REFERENCES chains(id) ON DELETE CASCADE,
    FOREIGN KEY (latest_artifact_id) REFERENCES artifacts(id) ON DELETE SET NULL
);

CREATE INDEX idx_workflows_chain ON workflows(chain_id, step_id);
CREATE INDEX idx_workflows_prompt ON workflows(prompt_id);
CREATE INDEX idx_workflows_temporal ON workflows(temporal_workflow_id);
CREATE INDEX idx_workflows_status ON workflows(status);
```

### Table: artifacts

Tracks each output file (image, video, etc.) from workflow executions.

```sql
CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,  -- UUID
    workflow_id TEXT NOT NULL,  -- FK to workflows

    -- File info
    filename TEXT NOT NULL,  -- Original ComfyUI filename (e.g., "ComfyUI_00001_.png")
    local_filename TEXT NOT NULL UNIQUE,  -- Unique local filename (e.g., "8a3f2b1c.png")
    local_path TEXT NOT NULL UNIQUE,  -- Full path to file
    file_type TEXT NOT NULL,  -- 'image', 'video', etc.
    file_format TEXT,  -- 'png', 'mp4', 'jpg', etc.
    file_size INTEGER,  -- Bytes

    -- ComfyUI metadata
    node_id TEXT,  -- ComfyUI node that generated this (e.g., "9")
    subfolder TEXT DEFAULT '',  -- Subfolder in ComfyUI
    comfy_folder_type TEXT DEFAULT 'output',  -- 'output', 'input', 'temp'

    -- Versioning
    version INTEGER DEFAULT 1,
    is_latest BOOLEAN DEFAULT TRUE,  -- Only one artifact per workflow should have this = TRUE
    parent_artifact_id TEXT,  -- FK to artifacts (for edited versions)

    -- Approval workflow
    approval_status TEXT DEFAULT 'auto_approved',  -- 'pending', 'approved', 'rejected', 'auto_approved', 'edited'
    approved_by TEXT,  -- User email or system
    approved_at TIMESTAMP,
    rejection_reason TEXT,

    -- Metadata
    metadata JSON,  -- Additional metadata (resolution, duration, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_artifact_id) REFERENCES artifacts(id) ON DELETE SET NULL
);

CREATE INDEX idx_artifacts_workflow ON artifacts(workflow_id);
CREATE INDEX idx_artifacts_latest ON artifacts(workflow_id, is_latest);
CREATE INDEX idx_artifacts_approval ON artifacts(approval_status);
CREATE INDEX idx_artifacts_created ON artifacts(created_at DESC);
CREATE UNIQUE INDEX idx_artifacts_one_latest_per_workflow ON artifacts(workflow_id, is_latest) WHERE is_latest = TRUE;
```

### Table: artifact_transfers

Tracks when artifacts are uploaded to target servers (for chaining).

```sql
CREATE TABLE artifact_transfers (
    id TEXT PRIMARY KEY,  -- UUID
    artifact_id TEXT NOT NULL,  -- FK to artifacts (which artifact was transferred)

    -- Transfer info
    source_workflow_id TEXT NOT NULL,  -- Where it came from
    target_workflow_id TEXT,  -- Where it's going (NULL until target starts)
    target_server TEXT NOT NULL,  -- Target ComfyUI server address
    target_subfolder TEXT DEFAULT '',

    -- Status
    status TEXT NOT NULL,  -- 'pending', 'uploading', 'completed', 'failed'
    uploaded_at TIMESTAMP,
    error_message TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE,
    FOREIGN KEY (source_workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
    FOREIGN KEY (target_workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

CREATE INDEX idx_transfers_artifact ON artifact_transfers(artifact_id);
CREATE INDEX idx_transfers_source ON artifact_transfers(source_workflow_id);
CREATE INDEX idx_transfers_target ON artifact_transfers(target_workflow_id);
CREATE INDEX idx_transfers_status ON artifact_transfers(status);
```

## Key Design Decisions

### 1. Workflows.latest_artifact_id (Denormalized)

Instead of always querying `artifacts` with `WHERE workflow_id = ? AND is_latest = TRUE`, we store the latest artifact ID directly on the workflow record.

**Benefits:**
- Fast lookups: `SELECT latest_artifact_id FROM workflows WHERE id = ?`
- Simplifies chain execution: easily get the latest artifact to upload to next step
- Clear intent: "What's the current/approved output of this workflow?"

**Maintenance:**
- When a new artifact is created/approved, update `workflows.latest_artifact_id`
- When an artifact is edited, create new artifact and update `workflows.latest_artifact_id`

### 2. Artifacts.is_latest (Redundant but Useful)

Even though we have `workflows.latest_artifact_id`, we keep `is_latest` flag on artifacts for:
- Querying all latest artifacts across workflows: `SELECT * FROM artifacts WHERE is_latest = TRUE`
- Validation: ensure only one artifact per workflow has `is_latest = TRUE`
- Auditing: see which artifact was "current" at any point in time

### 3. Standalone Workflows (chain_id = NULL)

Workflows can exist independently of chains:
- SDK workflows executed directly
- Manual workflow executions
- Test workflows

This keeps the schema flexible while supporting both use cases.

## Example Queries

### Get all workflows in a chain
```sql
SELECT * FROM workflows
WHERE chain_id = 'chain-abc123'
ORDER BY step_id;
```

### Get latest artifact for a workflow
```sql
-- Option 1: Direct lookup (fast)
SELECT a.* FROM artifacts a
JOIN workflows w ON a.id = w.latest_artifact_id
WHERE w.id = 'workflow-xyz';

-- Option 2: Query with flag
SELECT * FROM artifacts
WHERE workflow_id = 'workflow-xyz' AND is_latest = TRUE;
```

### Get all artifacts for a workflow (including versions)
```sql
SELECT * FROM artifacts
WHERE workflow_id = 'workflow-xyz'
ORDER BY version DESC;
```

### Get dependency artifacts for chain step
```sql
-- For step "edit_frame1" that depends on "extract_frame1"
SELECT a.* FROM artifacts a
JOIN workflows w ON a.id = w.latest_artifact_id
WHERE w.chain_id = 'chain-abc123'
  AND w.step_id = 'extract_frame1';
```

### Track artifact lineage (version history)
```sql
WITH RECURSIVE artifact_history AS (
  -- Start with current artifact
  SELECT * FROM artifacts WHERE id = 'artifact-123'

  UNION ALL

  -- Recursively get parent artifacts
  SELECT a.* FROM artifacts a
  JOIN artifact_history ah ON a.id = ah.parent_artifact_id
)
SELECT * FROM artifact_history ORDER BY version;
```

### Get all chains with failed workflows
```sql
SELECT DISTINCT c.* FROM chains c
JOIN workflows w ON w.chain_id = c.id
WHERE w.status = 'failed';
```

## Implementation Plan

### Phase 1: Database Setup

**Files to create:**
```
gateway/database/
  __init__.py
  models.py          # SQLAlchemy models
  session.py         # Database session/engine setup
  crud.py            # CRUD operations

temporal_gateway/database/
  __init__.py
  models.py          # Same models (shared schema)
  session.py
  crud.py
```

**Dependencies:**
```toml
[tool.poetry.dependencies]
sqlalchemy = "^2.0"
alembic = "^1.13"
aiosqlite = "^0.19"  # For async SQLite
```

**Initialize database:**
```bash
alembic init alembic
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

### Phase 2: Modify Storage Layer

**gateway/core/storage.py:**
```python
class ArtifactStorage:
    async def save_workflow_artifacts(
        workflow_id: str,
        server_address: str,
        history_data: dict
    ) -> list[Artifact]:
        """Download outputs and save to DB"""
        # 1. Download files from ComfyUI
        # 2. Save to local storage
        # 3. Create artifact records in DB
        # 4. Update workflow.latest_artifact_id
        # 5. Return artifact objects
```

**temporal_gateway/activities.py:**
```python
@activity.defn
async def download_and_store_artifacts(
    workflow_id: str,
    server_address: str,
    output_files: list[dict]
) -> list[dict]:
    """Download outputs and save to DB (activity version)"""
```

### Phase 3: Update Chain Execution

**temporal_sdk/chains/workflows.py:**

```python
async def _execute_step(self, node) -> StepResult:
    # 1. Create workflow record in DB
    workflow = await create_workflow(
        chain_id=self.chain_id,
        step_id=node.step_id,
        workflow_name=node.workflow
    )

    # 2. Get dependency artifacts from DB (not in-memory)
    if node.dependencies:
        for dep_step_id in node.dependencies:
            dep_workflow = await get_workflow_by_step(
                chain_id=self.chain_id,
                step_id=dep_step_id
            )
            artifact = await get_latest_artifact(dep_workflow.id)

            # Upload from local storage to target server
            await upload_artifact_to_server(
                artifact_id=artifact.id,
                target_server=target_server
            )

    # 3. Execute workflow
    result = await execute_child_workflow(...)

    # 4. Download and store artifacts to DB
    artifacts = await download_and_store_artifacts(
        workflow_id=workflow.id,
        server_address=target_server,
        output_files=output_files
    )

    # 5. Return result
    return StepResult(...)
```

### Phase 4: Add API Endpoints

**gateway/api/artifacts.py:**
```python
# Chain endpoints
GET    /chains                           # List all chains
GET    /chains/{chain_id}                # Get chain details
GET    /chains/{chain_id}/workflows      # List workflows in chain
DELETE /chains/{chain_id}                # Delete chain and all workflows/artifacts

# Workflow endpoints
GET    /workflows                        # List all workflows
GET    /workflows/{workflow_id}          # Get workflow details
GET    /workflows/{workflow_id}/artifacts # List all artifacts (including versions)
GET    /workflows/{workflow_id}/latest   # Get latest artifact

# Artifact endpoints
GET    /artifacts/{artifact_id}          # Get artifact details
GET    /artifacts/{artifact_id}/download # Download artifact file
POST   /artifacts/{artifact_id}/approve  # Approve artifact
POST   /artifacts/{artifact_id}/reject   # Reject artifact
POST   /artifacts/{artifact_id}/edit     # Upload edited version
GET    /artifacts/{artifact_id}/versions # Get version history
DELETE /artifacts/{artifact_id}          # Delete artifact

# Transfer endpoints
GET    /transfers                        # List all transfers
GET    /transfers/{transfer_id}          # Get transfer details
```

## Usage Examples

### Example 1: Automatic Chain (No Human Intervention)

```python
# Chain starts
chain = create_chain(name="image-edit-to-video-pipeline")

# Step 1: Extract frame
workflow_1 = create_workflow(
    chain_id=chain.id,
    step_id="extract_frame1",
    workflow_name="imageSave"
)
execute_workflow(workflow_1)
artifacts_1 = download_and_store_artifacts(workflow_1.id)
# Automatically sets workflow_1.latest_artifact_id = artifacts_1[0].id

# Step 2: Edit frame (depends on step 1)
workflow_2 = create_workflow(
    chain_id=chain.id,
    step_id="edit_frame1",
    workflow_name="qwen_image_edit"
)

# Get dependency artifact
dep_artifact = get_latest_artifact(workflow_1.id)

# Upload from local storage to target server
upload_artifact_to_server(
    artifact=dep_artifact,
    target_server="http://server-b:8188"
)

# Execute step 2
execute_workflow(workflow_2)
```

### Example 2: Human-in-the-Loop

```python
# Step 1 completes
workflow_1 = get_workflow(id="wf-123")
artifact_1 = get_latest_artifact(workflow_1.id)

# Set to pending approval
update_artifact(artifact_1.id, approval_status="pending")

# Human reviews via UI
print(f"Review: {artifact_1.local_path}")

# Option A: Approve
approve_artifact(artifact_1.id, approved_by="user@example.com")
# workflow_1.latest_artifact_id still points to artifact_1

# Option B: Edit and upload new version
edited_file = edit_locally(artifact_1.local_path)
artifact_2 = create_artifact(
    workflow_id=workflow_1.id,
    local_path=edited_file,
    parent_artifact_id=artifact_1.id,
    version=2,
    approval_status="approved",
    approved_by="user@example.com"
)
# This automatically sets:
# - artifact_1.is_latest = FALSE
# - artifact_2.is_latest = TRUE
# - workflow_1.latest_artifact_id = artifact_2.id

# Chain continues with approved/edited artifact
artifact = get_latest_artifact(workflow_1.id)  # Returns artifact_2
upload_artifact_to_server(artifact, target_server)
```

### Example 3: Query Chain Status

```python
# Get chain with all workflows
chain = get_chain(id="chain-abc")
workflows = get_workflows_by_chain(chain.id)

for workflow in workflows:
    artifact = get_latest_artifact(workflow.id)
    print(f"{workflow.step_id}: {workflow.status} -> {artifact.filename}")

# Output:
# extract_frame1: completed -> frame_001.png
# extract_frame2: completed -> frame_002.png
# edit_frame1: executing -> None
# edit_frame2: queued -> None
```

## Migration Strategy

### Phase 1: Add Database (Non-Breaking)
1. Create database models and migrations
2. Modify storage layer to write to DB (parallel with existing behavior)
3. No changes to chain execution yet
4. Verify data is being saved correctly

### Phase 2: Update Chain Execution (Feature Flag)
1. Add feature flag: `USE_ARTIFACT_DB=true`
2. Modify `transfer_outputs_to_input` to read from DB when flag enabled
3. Test both flows in parallel
4. Gradually migrate chains to use DB

### Phase 3: Full Migration
1. Remove server-to-server transfer code
2. All chains use DB-based artifacts
3. Remove feature flag
4. Add approval/editing UI

### Phase 4: Enhancements
1. Add artifact pruning/cleanup
2. Add S3 storage backend option
3. Add webhook notifications
4. Add artifact search/filtering

## Future Enhancements

1. **S3 Storage**: Store artifacts in S3 instead of local disk
2. **Artifact Pruning**: Auto-delete old artifacts after N days
3. **Thumbnails**: Generate thumbnails for images/videos
4. **Metadata Extraction**: Extract resolution, duration, codec info
5. **Signed URLs**: Generate time-limited download links
6. **Webhooks**: Notify external systems when artifacts ready
7. **Search**: Full-text search on metadata
8. **Tags**: Tag artifacts for organization
9. **Sharing**: Share artifacts with external users
10. **Audit Log**: Track all changes to artifacts
