"""
Test all database CRUD operations

Run with: python test_database.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from temporal_gateway.database import (
    init_db,
    get_session,
    # Chain operations
    create_chain,
    get_chain,
    get_chain_by_temporal_id,
    update_chain_status,
    list_chains,
    # Workflow operations
    create_workflow,
    get_workflow,
    get_workflow_by_prompt,
    get_workflow_by_step,
    get_workflows_by_chain,
    update_workflow_status,
    update_workflow_latest_artifact,
    list_workflows,
    # Artifact operations
    create_artifact,
    get_artifact,
    get_latest_artifact,
    get_artifacts_by_workflow,
    get_artifact_versions,
    update_artifact_latest_flag,
    approve_artifact,
    reject_artifact,
    list_artifacts,
    # Transfer operations
    create_transfer,
    get_transfer,
    update_transfer_status,
    list_transfers,
)


def print_header(title):
    """Print a test section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_success(message):
    """Print success message"""
    print(f"✓ {message}")


def print_info(message):
    """Print info message"""
    print(f"  → {message}")


def test_database_setup():
    """Test 1: Database initialization"""
    print_header("Test 1: Database Setup")

    # Initialize database
    init_db()
    print_success("Database initialized")

    # Check database file exists
    db_path = Path(__file__).parent / "temporal_gateway" / "data" / "artifacts.db"
    if db_path.exists():
        print_success(f"Database file created at: {db_path}")
        print_info(f"File size: {db_path.stat().st_size} bytes")
    else:
        print(f"✗ Database file not found at: {db_path}")
        return False

    return True


def test_chain_operations():
    """Test 2: Chain CRUD operations"""
    print_header("Test 2: Chain Operations")

    with get_session() as session:
        # Create chain
        chain = create_chain(
            session=session,
            name="test-chain-1",
            temporal_workflow_id="wf-test-123",
            temporal_run_id="run-test-123",
            description="Test chain for database testing",
            chain_definition={"name": "test", "steps": []},
            status="initializing"
        )
        print_success(f"Created chain: {chain.id}")
        print_info(f"Name: {chain.name}")
        print_info(f"Status: {chain.status}")
        print_info(f"Temporal ID: {chain.temporal_workflow_id}")

        # Get chain by ID
        retrieved = get_chain(session, chain.id)
        assert retrieved.id == chain.id
        print_success(f"Retrieved chain by ID: {retrieved.name}")

        # Get chain by temporal ID
        by_temporal = get_chain_by_temporal_id(session, "wf-test-123")
        assert by_temporal.id == chain.id
        print_success(f"Retrieved chain by temporal ID")

        # Update chain status
        updated = update_chain_status(
            session=session,
            chain_id=chain.id,
            status="executing_level_1",
            current_level=1
        )
        print_success(f"Updated chain status to: {updated.status}")

        # List chains
        chains = list_chains(session, limit=10)
        print_success(f"Listed {len(chains)} chain(s)")

        return chain.id


def test_workflow_operations(chain_id):
    """Test 3: Workflow CRUD operations"""
    print_header("Test 3: Workflow Operations")

    with get_session() as session:
        # Create workflow
        workflow = create_workflow(
            session=session,
            workflow_name="test_workflow",
            server_address="http://localhost:8188",
            prompt_id="prompt-123",
            chain_id=chain_id,
            step_id="step1",
            temporal_workflow_id="wf-child-123",
            workflow_definition={"prompt": "test"},
            parameters={"param1": "value1"},
            status="queued"
        )
        print_success(f"Created workflow: {workflow.id}")
        print_info(f"Name: {workflow.workflow_name}")
        print_info(f"Chain ID: {workflow.chain_id}")
        print_info(f"Step ID: {workflow.step_id}")
        print_info(f"Status: {workflow.status}")

        # Get workflow by ID
        retrieved = get_workflow(session, workflow.id)
        assert retrieved.id == workflow.id
        print_success(f"Retrieved workflow by ID")

        # Get workflow by prompt ID
        by_prompt = get_workflow_by_prompt(session, "prompt-123")
        assert by_prompt.id == workflow.id
        print_success(f"Retrieved workflow by prompt ID")

        # Get workflow by step
        by_step = get_workflow_by_step(session, chain_id, "step1")
        assert by_step.id == workflow.id
        print_success(f"Retrieved workflow by chain + step")

        # Get workflows by chain
        chain_workflows = get_workflows_by_chain(session, chain_id)
        print_success(f"Found {len(chain_workflows)} workflow(s) in chain")

        # Update workflow status
        updated = update_workflow_status(
            session=session,
            workflow_id=workflow.id,
            status="executing"
        )
        print_success(f"Updated workflow status to: {updated.status}")

        # List workflows
        workflows = list_workflows(session, limit=10)
        print_success(f"Listed {len(workflows)} workflow(s)")

        return workflow.id


def test_artifact_operations(workflow_id):
    """Test 4: Artifact CRUD operations"""
    print_header("Test 4: Artifact Operations")

    with get_session() as session:
        # Create artifact
        artifact1 = create_artifact(
            session=session,
            workflow_id=workflow_id,
            filename="output_00001.png",
            local_filename="abc123.png",
            local_path="/tmp/artifacts/abc123.png",
            file_type="image",
            file_format="png",
            file_size=1024000,
            node_id="9",
            subfolder="",
            comfy_folder_type="output",
            version=1,
            is_latest=True,
            approval_status="auto_approved"
        )
        print_success(f"Created artifact: {artifact1.id}")
        print_info(f"Filename: {artifact1.filename}")
        print_info(f"Local path: {artifact1.local_path}")
        print_info(f"File type: {artifact1.file_type}")
        print_info(f"Size: {artifact1.file_size} bytes")
        print_info(f"Version: {artifact1.version}")
        print_info(f"Is latest: {artifact1.is_latest}")

        # Get artifact by ID
        retrieved = get_artifact(session, artifact1.id)
        assert retrieved.id == artifact1.id
        print_success(f"Retrieved artifact by ID")

        # Get latest artifact
        latest = get_latest_artifact(session, workflow_id)
        assert latest.id == artifact1.id
        print_success(f"Retrieved latest artifact for workflow")

        # Create second version (edited)
        artifact2 = create_artifact(
            session=session,
            workflow_id=workflow_id,
            filename="output_00001_edited.png",
            local_filename="def456.png",
            local_path="/tmp/artifacts/def456.png",
            file_type="image",
            file_format="png",
            file_size=1050000,
            node_id="9",
            parent_artifact_id=artifact1.id,
            version=2,
            is_latest=True,
            approval_status="pending"
        )
        print_success(f"Created artifact version 2: {artifact2.id}")
        print_info(f"Parent artifact: {artifact2.parent_artifact_id}")

        # Verify artifact1 is no longer latest
        artifact1_check = get_artifact(session, artifact1.id)
        assert artifact1_check.is_latest == False
        print_success(f"Artifact v1 is_latest flag updated to False")

        # Get all artifacts for workflow
        all_artifacts = get_artifacts_by_workflow(session, workflow_id, include_old_versions=True)
        print_success(f"Retrieved {len(all_artifacts)} total artifact(s)")

        # Get only latest artifacts
        latest_only = get_artifacts_by_workflow(session, workflow_id, include_old_versions=False)
        print_success(f"Retrieved {len(latest_only)} latest artifact(s)")

        # Get artifact versions
        versions = get_artifact_versions(session, artifact2.id)
        print_success(f"Retrieved {len(versions)} version(s) in history")
        for v in versions:
            print_info(f"  v{v.version}: {v.filename}")

        # Approve artifact
        approved = approve_artifact(session, artifact2.id, "test_user")
        assert approved.approval_status == "approved"
        print_success(f"Approved artifact: {approved.approval_status}")

        # List artifacts
        artifacts = list_artifacts(session, limit=10, is_latest=True)
        print_success(f"Listed {len(artifacts)} latest artifact(s)")

        return artifact1.id, artifact2.id


def test_transfer_operations(workflow_id, artifact_id):
    """Test 5: Transfer CRUD operations"""
    print_header("Test 5: Transfer Operations")

    with get_session() as session:
        # Create transfer
        transfer = create_transfer(
            session=session,
            artifact_id=artifact_id,
            source_workflow_id=workflow_id,
            target_server="http://server-b:8188",
            target_subfolder="",
            status="pending"
        )
        print_success(f"Created transfer: {transfer.id}")
        print_info(f"Artifact ID: {transfer.artifact_id}")
        print_info(f"Source workflow: {transfer.source_workflow_id}")
        print_info(f"Target server: {transfer.target_server}")
        print_info(f"Status: {transfer.status}")

        # Get transfer by ID
        retrieved = get_transfer(session, transfer.id)
        assert retrieved.id == transfer.id
        print_success(f"Retrieved transfer by ID")

        # Update transfer status
        updated = update_transfer_status(
            session=session,
            transfer_id=transfer.id,
            status="completed"
        )
        assert updated.status == "completed"
        assert updated.uploaded_at is not None
        print_success(f"Updated transfer status to: {updated.status}")
        print_info(f"Uploaded at: {updated.uploaded_at}")

        # List transfers
        transfers = list_transfers(session, limit=10)
        print_success(f"Listed {len(transfers)} transfer(s)")

        # List transfers by artifact
        by_artifact = list_transfers(session, artifact_id=artifact_id)
        print_success(f"Found {len(by_artifact)} transfer(s) for artifact")

        return transfer.id


def test_workflow_latest_artifact_update(workflow_id, artifact_id):
    """Test 6: Workflow latest artifact reference"""
    print_header("Test 6: Workflow Latest Artifact Reference")

    with get_session() as session:
        # Update workflow's latest artifact
        workflow = update_workflow_latest_artifact(
            session=session,
            workflow_id=workflow_id,
            artifact_id=artifact_id
        )
        assert workflow.latest_artifact_id == artifact_id
        print_success(f"Updated workflow.latest_artifact_id")
        print_info(f"Latest artifact: {workflow.latest_artifact_id}")

        # Verify we can retrieve the latest artifact via workflow
        workflow_check = get_workflow(session, workflow_id)
        assert workflow_check.latest_artifact_id == artifact_id
        print_success(f"Verified latest artifact reference persisted")


def test_query_relationships():
    """Test 7: Query relationships between tables"""
    print_header("Test 7: Query Relationships")

    with get_session() as session:
        # Query chains with workflows
        chains = list_chains(session)
        for chain in chains:
            print_info(f"Chain: {chain.name} ({chain.status})")
            workflows = get_workflows_by_chain(session, chain.id)
            for wf in workflows:
                print_info(f"  → Workflow: {wf.workflow_name} ({wf.status})")
                artifacts = get_artifacts_by_workflow(session, wf.id, include_old_versions=True)
                for art in artifacts:
                    print_info(f"      → Artifact: {art.filename} (v{art.version}, latest={art.is_latest})")

        print_success(f"Successfully queried relationships")


def test_error_handling():
    """Test 8: Error handling"""
    print_header("Test 8: Error Handling")

    with get_session() as session:
        # Try to get non-existent chain
        chain = get_chain(session, "non-existent-id")
        assert chain is None
        print_success("Handled non-existent chain gracefully")

        # Try to get non-existent workflow
        workflow = get_workflow(session, "non-existent-id")
        assert workflow is None
        print_success("Handled non-existent workflow gracefully")

        # Try to get non-existent artifact
        artifact = get_artifact(session, "non-existent-id")
        assert artifact is None
        print_success("Handled non-existent artifact gracefully")


def run_all_tests():
    """Run all database tests"""
    print("\n" + "="*60)
    print("  DATABASE OPERATIONS TEST SUITE")
    print("="*60)

    try:
        # Test 1: Setup
        if not test_database_setup():
            print("\n✗ Database setup failed. Aborting tests.")
            return

        # Test 2: Chain operations
        chain_id = test_chain_operations()

        # Test 3: Workflow operations
        workflow_id = test_workflow_operations(chain_id)

        # Test 4: Artifact operations
        artifact1_id, artifact2_id = test_artifact_operations(workflow_id)

        # Test 5: Transfer operations
        transfer_id = test_transfer_operations(workflow_id, artifact2_id)

        # Test 6: Workflow latest artifact
        test_workflow_latest_artifact_update(workflow_id, artifact2_id)

        # Test 7: Query relationships
        test_query_relationships()

        # Test 8: Error handling
        test_error_handling()

        # Summary
        print_header("TEST SUMMARY")
        print_success("All database tests passed!")
        print_info("Database is ready for production use")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
