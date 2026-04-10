#!/usr/bin/env python
"""
Simple smoke test to verify PatchApplier implementation.
"""

import json
import tempfile
from pathlib import Path
import sys

# Add to path
sys.path.insert(0, r"c:\Users\h p\rou-work\SelfHealing-AutomationWorkflow")

from patcher.patch_applier import PatchApplier


def test_set_env():
    """Test set_env operator."""
    print("Testing set_env operator...")
    with tempfile.TemporaryDirectory() as tmpdir:
        applier = PatchApplier(project_root=tmpdir, dry_run=False)
        diff = applier._apply_set_env("API_URL", "https://api.example.com")
        
        env_path = Path(tmpdir) / ".env.inject"
        assert env_path.exists(), "Failed: .env.inject was not created"
        content = env_path.read_text()
        assert "API_URL=https://api.example.com" in content, "Failed: API_URL not found in .env.inject"
        assert diff, "Failed: diff should not be empty"
    print("✓ set_env operator works correctly")


def test_set_retry():
    """Test set_retry operator."""
    print("Testing set_retry operator...")
    with tempfile.TemporaryDirectory() as tmpdir:
        dag_dir = Path(tmpdir) / "dags"
        dag_dir.mkdir()
        
        dag_file = dag_dir / "http_dag.py"
        dag_file.write_text("""
default_args = {
    "owner": "airflow",
    "retries": 3,
}
""")
        
        applier = PatchApplier(project_root=tmpdir, dry_run=False)
        diff = applier._apply_set_retry("http_dag", "retries", "5")
        
        content = dag_file.read_text()
        assert "retries\": 5" in content or "retries=5" in content, "Failed: retries value not updated"
        assert diff, "Failed: diff should not be empty"
    print("✓ set_retry operator works correctly")


def test_set_timeout():
    """Test set_timeout operator."""
    print("Testing set_timeout operator...")
    with tempfile.TemporaryDirectory() as tmpdir:
        dag_dir = Path(tmpdir) / "dags"
        dag_dir.mkdir()
        
        dag_file = dag_dir / "http_dag.py"
        dag_file.write_text("""
from datetime import timedelta

default_args = {
    "owner": "airflow",
    "execution_timeout": timedelta(seconds=300),
}
""")
        
        applier = PatchApplier(project_root=tmpdir, dry_run=False)
        diff = applier._apply_set_timeout("http_dag", "execution_timeout", "600")
        
        content = dag_file.read_text()
        assert "timedelta(seconds=600)" in content, "Failed: execution_timeout value not updated"
        assert diff, "Failed: diff should not be empty"
    print("✓ set_timeout operator works correctly")


def test_add_precheck():
    """Test add_precheck operator."""
    print("Testing add_precheck operator...")
    with tempfile.TemporaryDirectory() as tmpdir:
        dag_dir = Path(tmpdir) / "dags"
        dag_dir.mkdir()
        
        dag_file = dag_dir / "http_dag.py"
        dag_file.write_text("""
with DAG(dag_id="http_dag") as dag:
    # BEGIN PRECHECKS
    pass
    # END PRECHECKS
""")
        
        applier = PatchApplier(project_root=tmpdir, dry_run=False)
        precheck_line = "t_precheck = PythonOperator(...)"
        diff = applier._apply_add_precheck("http_dag", precheck_line)
        
        content = dag_file.read_text()
        assert precheck_line in content, "Failed: precheck not added"
        assert content.index(precheck_line) < content.index("# END PRECHECKS"), "Failed: precheck not before END marker"
        assert diff, "Failed: diff should not be empty"
    print("✓ add_precheck operator works correctly")


def test_plan_rejection():
    """Test plan rejection logic."""
    print("Testing plan rejection (requires_human_approval)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        applier = PatchApplier(project_root=tmpdir, dry_run=True)
        
        plan = {
            "plan_id": "plan_ep_001",
            "failure_class": "timeout",
            "repair_actions": [
                {"operator": "set_env", "param": "VAR", "value": "value"}
            ],
            "requires_human_approval": True,
        }
        
        result = applier.apply(plan)
        assert result["status"] == "rejected", "Failed: plan should be rejected"
    print("✓ Plan rejection works correctly")


def test_audit_log():
    """Test audit log writing."""
    print("Testing audit log writing...")
    with tempfile.TemporaryDirectory() as tmpdir:
        audit_log_path = Path(tmpdir) / "audit_log.jsonl"
        applier = PatchApplier(
            project_root=tmpdir,
            audit_log_path=str(audit_log_path),
            dry_run=True,
        )
        
        entry = {
            "plan_id": "plan_ep_001",
            "status": "dry_run",
            "applied_actions": [],
        }
        
        applier._write_audit_entry(entry)
        
        assert audit_log_path.exists(), "Failed: audit log was not created"
        content = audit_log_path.read_text()
        logged_entry = json.loads(content.strip())
        assert logged_entry["plan_id"] == "plan_ep_001", "Failed: audit entry not logged correctly"
    print("✓ Audit log writing works correctly")


if __name__ == "__main__":
    try:
        test_set_env()
        test_set_retry()
        test_set_timeout()
        test_add_precheck()
        test_plan_rejection()
        test_audit_log()
        
        print("\n" + "="*60)
        print("✓ All smoke tests passed!")
        print("="*60)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
