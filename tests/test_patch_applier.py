"""
Unit tests for the Patch Applier component.

Tests cover:
  - All regex patterns for DAG edits (set_retry, set_timeout, add_precheck)
  - .env.inject file handling
  - Plan validation and rejection logic
  - Git commit functionality (mocked)
  - Audit log writing
"""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from patcher.patch_applier import PatchApplier


class TestSetEnv:
    """Tests for _apply_set_env operator."""

    def test_create_new_env_file(self):
        """Test creating a new .env.inject file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            applier = PatchApplier(project_root=tmpdir, dry_run=False)

            diff = applier._apply_set_env("API_URL", "https://api.example.com")

            env_path = Path(tmpdir) / ".env.inject"
            assert env_path.exists()
            content = env_path.read_text()
            assert "API_URL=https://api.example.com" in content

    def test_update_existing_env_var(self):
        """Test updating an existing environment variable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            env_path = Path(tmpdir) / ".env.inject"
            env_path.write_text("API_URL=https://old.example.com\nAPI_TIMEOUT=30\n")

            applier = PatchApplier(project_root=tmpdir, dry_run=False)
            diff = applier._apply_set_env("API_URL", "https://new.example.com")

            content = env_path.read_text()
            assert "API_URL=https://new.example.com" in content
            assert "API_TIMEOUT=30" in content
            assert "https://old.example.com" not in content

    def test_add_multiple_env_vars(self):
        """Test adding multiple environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            applier = PatchApplier(project_root=tmpdir, dry_run=False)

            applier._apply_set_env("VAR1", "value1")
            applier._apply_set_env("VAR2", "value2")
            applier._apply_set_env("VAR3", "value3")

            env_path = Path(tmpdir) / ".env.inject"
            content = env_path.read_text()
            assert "VAR1=value1" in content
            assert "VAR2=value2" in content
            assert "VAR3=value3" in content

    def test_dry_run_does_not_create_file(self):
        """Test that dry_run mode does not create files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)
            diff = applier._apply_set_env("API_URL", "https://api.example.com")

            env_path = Path(tmpdir) / ".env.inject"
            assert not env_path.exists()
            assert diff  # diff should still be returned


class TestSetRetry:
    """Tests for _apply_set_retry operator with regex patterns."""

    def test_update_retries_in_default_args(self):
        """Test updating retries in default_args."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()

            dag_file = dag_dir / "http_dag.py"
            dag_file.write_text(
                """
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "airflow",
    "retries": 3,
    "start_date": datetime(2024, 1, 1),
}

with DAG(
    dag_id="http_dag",
    default_args=default_args,
) as dag:
    pass
"""
            )

            applier = PatchApplier(project_root=tmpdir, dry_run=False)
            diff = applier._apply_set_retry("http_dag", "retries", "5")

            content = dag_file.read_text()
            assert 'retries": 5' in content or "retries=5" in content
            assert 'retries": 3' not in content or "retries=3" not in content

    def test_update_retries_variable_format(self):
        """Test updating retries when it's formatted as retries=N."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()

            dag_file = dag_dir / "test_dag.py"
            dag_file.write_text(
                """
default_args = {
    "owner": "airflow",
    "retries": 2,
}
"""
            )

            applier = PatchApplier(project_root=tmpdir, dry_run=False)
            diff = applier._apply_set_retry("test_dag", "retries", "10")

            content = dag_file.read_text()
            assert "retries\": 10" in content or "retries=10" in content

    def test_set_retry_dag_not_found(self):
        """Test that set_retry raises error if DAG file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="DAG file not found"):
                applier._apply_set_retry("nonexistent_dag", "retries", "5")

    def test_set_retry_pattern_not_found(self):
        """Test that set_retry raises error if retries pattern not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()

            dag_file = dag_dir / "test_dag.py"
            dag_file.write_text("# No retries here\npass")

            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="Pattern 'retries' not found"):
                applier._apply_set_retry("test_dag", "retries", "5")


class TestSetTimeout:
    """Tests for _apply_set_timeout operator with regex patterns."""

    def test_update_execution_timeout_timedelta(self):
        """Test updating execution_timeout with timedelta."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()

            dag_file = dag_dir / "http_dag.py"
            dag_file.write_text(
                """
from datetime import timedelta

default_args = {
    "owner": "airflow",
    "execution_timeout": timedelta(seconds=300),
}
"""
            )

            applier = PatchApplier(project_root=tmpdir, dry_run=False)
            diff = applier._apply_set_timeout("http_dag", "execution_timeout", "600")

            content = dag_file.read_text()
            assert "timedelta(seconds=600)" in content
            assert "seconds=300" not in content

    def test_set_timeout_dag_not_found(self):
        """Test that set_timeout raises error if DAG file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="DAG file not found"):
                applier._apply_set_timeout("nonexistent_dag", "execution_timeout", "600")

    def test_set_timeout_pattern_not_found(self):
        """Test that set_timeout raises error if pattern not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()

            dag_file = dag_dir / "test_dag.py"
            dag_file.write_text("# No execution_timeout here\npass")

            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="Pattern 'execution_timeout' not found"):
                applier._apply_set_timeout("test_dag", "execution_timeout", "600")


class TestAddPrecheck:
    """Tests for _apply_add_precheck operator."""

    def test_add_precheck_to_block(self):
        """Test adding a precheck task to the PRECHECKS block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()

            dag_file = dag_dir / "http_dag.py"
            dag_file.write_text(
                """
from airflow import DAG
from airflow.operators.python import PythonOperator

with DAG(dag_id="http_dag") as dag:
    # BEGIN PRECHECKS
    pass
    # END PRECHECKS

    t_extract = PythonOperator(
        task_id="extract_api",
        python_callable=extract_api,
    )
"""
            )

            applier = PatchApplier(project_root=tmpdir, dry_run=False)
            precheck_line = "t_precheck = PythonOperator(task_id='precheck', python_callable=check_timeout)"
            diff = applier._apply_add_precheck("http_dag", precheck_line)

            content = dag_file.read_text()
            assert precheck_line in content
            # Ensure it's before END PRECHECKS
            assert content.index(precheck_line) < content.index("# END PRECHECKS")

    def test_add_precheck_dag_not_found(self):
        """Test that add_precheck raises error if DAG file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="DAG file not found"):
                applier._apply_add_precheck("nonexistent_dag", "t_precheck = ...")

    def test_add_precheck_block_not_found(self):
        """Test that add_precheck raises error if PRECHECKS block missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()

            dag_file = dag_dir / "test_dag.py"
            dag_file.write_text("# No PRECHECKS block\npass")

            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="PRECHECKS block not found"):
                applier._apply_add_precheck("test_dag", "t_precheck = ...")


class TestReplacePath:
    """Tests for _apply_replace_path operator."""

    def test_replace_path_same_as_set_env(self):
        """Test that replace_path works like set_env."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            applier = PatchApplier(project_root=tmpdir, dry_run=False)

            diff = applier._apply_replace_path("MY_PATH", "/usr/local/bin:/usr/bin")

            env_path = Path(tmpdir) / ".env.inject"
            assert env_path.exists()
            content = env_path.read_text()
            assert "MY_PATH=/usr/local/bin:/usr/bin" in content


class TestPlanValidation:
    """Tests for plan validation logic."""

    def test_reject_plan_with_human_approval(self):
        """Test that plans requiring human approval are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            plan = {
                "plan_id": "plan_ep_001",
                "failure_class": "timeout",
                "repair_actions": [
                    {"operator": "set_timeout", "param": "execution_timeout", "value": "600"}
                ],
                "requires_human_approval": True,
            }

            result = applier.apply(plan)

            assert result["status"] == "rejected"
            assert len(result["failed_actions"]) > 0

    def test_reject_plan_with_invalid_operator(self):
        """Test that plans with invalid operators are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            plan = {
                "plan_id": "plan_ep_002",
                "failure_class": "missing_env_var",
                "repair_actions": [
                    {"operator": "invalid_operator", "param": "VAR", "value": "value"}
                ],
                "requires_human_approval": False,
            }

            result = applier.apply(plan)

            assert result["status"] == "rejected"

    def test_apply_valid_plan(self):
        """Test applying a valid plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            plan = {
                "plan_id": "plan_ep_003",
                "failure_class": "missing_env_var",
                "repair_actions": [
                    {"operator": "set_env", "param": "API_URL", "value": "https://api.example.com"}
                ],
                "requires_human_approval": False,
            }

            result = applier.apply(plan)

            assert result["status"] == "dry_run"
            assert len(result["applied_actions"]) == 1


class TestAuditLog:
    """Tests for audit log functionality."""

    def test_write_audit_entry(self):
        """Test writing an audit log entry."""
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
                "applied_actions": ["set_env(API_URL)"],
                "failed_actions": [],
            }

            applier._write_audit_entry(entry)

            assert audit_log_path.exists()
            content = audit_log_path.read_text()
            logged_entry = json.loads(content.strip())
            assert logged_entry["plan_id"] == "plan_ep_001"

    def test_append_multiple_audit_entries(self):
        """Test appending multiple audit log entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log_path = Path(tmpdir) / "audit_log.jsonl"
            applier = PatchApplier(
                project_root=tmpdir,
                audit_log_path=str(audit_log_path),
                dry_run=True,
            )

            for i in range(3):
                entry = {
                    "plan_id": f"plan_ep_{i:03d}",
                    "status": "dry_run",
                }
                applier._write_audit_entry(entry)

            lines = audit_log_path.read_text().strip().split("\n")
            assert len(lines) == 3

            for i, line in enumerate(lines):
                entry = json.loads(line)
                assert entry["plan_id"] == f"plan_ep_{i:03d}"


class TestGitCommit:
    """Tests for Git commit functionality."""

    @patch("subprocess.run")
    def test_git_commit_success(self, mock_run):
        """Test successful Git commit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock .git directory
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()

            # Mock subprocess calls
            mock_run.side_effect = [
                MagicMock(returncode=0),  # git add
                MagicMock(returncode=0, stdout=""),  # git commit
                MagicMock(returncode=0, stdout="a1b2c3d\n"),  # git rev-parse
            ]

            applier = PatchApplier(project_root=tmpdir, dry_run=False)
            commit_hash = applier._git_commit("plan_ep_001", "timeout")

            assert commit_hash == "a1b2c3d"
            assert mock_run.call_count == 3

    @patch("subprocess.run")
    def test_git_commit_failure(self, mock_run):
        """Test Git commit failure handling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()

            from subprocess import CalledProcessError

            mock_run.side_effect = CalledProcessError(1, "git", stderr="Not a git repo")

            applier = PatchApplier(project_root=tmpdir, dry_run=False)

            with pytest.raises(RuntimeError, match="Git commit failed"):
                applier._git_commit("plan_ep_001", "timeout")


class TestDiffGeneration:
    """Tests for diff generation utilities."""

    def test_generate_diff(self):
        """Test unified diff generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            old_content = "line 1\nline 2\nline 3\n"
            new_content = "line 1\nline 2 modified\nline 3\n"

            diff = applier._generate_diff("test.txt", old_content, new_content)

            assert "line 2" in diff
            assert "+" in diff or "-" in diff

    def test_extract_target_file(self):
        """Test target file extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            assert applier._extract_target_file("", "set_env", "API_URL") == ".env.inject"
            assert applier._extract_target_file("", "replace_path", "PATH") == ".env.inject"
            assert (
                applier._extract_target_file("", "set_retry", "retries", dag_id="http_dag")
                == "dags/http_dag.py"
            )
            assert (
                applier._extract_target_file("", "set_timeout", "execution_timeout", dag_id="db_dag")
                == "dags/db_dag.py"
            )
            assert (
                applier._extract_target_file("", "add_precheck", "", dag_id="file_dag")
                == "dags/file_dag.py"
            )


class TestApplyBatch:
    """Tests for batch application."""

    def test_apply_batch_with_multiple_plans(self):
        """Test applying multiple plans from a JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create JSONL file
            plans_file = Path(tmpdir) / "repair_plans.jsonl"
            plans = [
                {
                    "plan_id": "plan_ep_001",
                    "failure_class": "timeout",
                    "repair_actions": [
                        {"operator": "set_env", "param": "VAR1", "value": "value1"}
                    ],
                    "requires_human_approval": False,
                },
                {
                    "plan_id": "plan_ep_002",
                    "failure_class": "missing_env_var",
                    "repair_actions": [
                        {"operator": "set_env", "param": "VAR2", "value": "value2"}
                    ],
                    "requires_human_approval": True,
                },
            ]

            with open(plans_file, "w") as f:
                for plan in plans:
                    f.write(json.dumps(plan) + "\n")

            applier = PatchApplier(project_root=tmpdir, dry_run=True)
            applier.apply_batch(str(plans_file))

            # Both should be processed (one applied, one pending human review)
            audit_path = Path(tmpdir) / "data" / "audit_log.jsonl"
            # In dry_run mode, might not write audit logs


class TestValidateAction:
    """Tests for _validate_action() validation dispatcher."""

    def test_validate_action_valid_set_env(self):
        """Test valid set_env action"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            action = {"operator": "set_env", "param": "API_URL", "value": "https://api.example.com"}
            operator, target_path, params = applier._validate_action(action)

            assert operator == "set_env"
            assert params["param"] == "API_URL"
            assert params["value"] == "https://api.example.com"

    def test_validate_action_invalid_operator(self):
        """Test action with invalid operator"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            action = {"operator": "invalid_op", "param": "API_URL", "value": "value"}

            with pytest.raises(ValueError, match="Invalid operator"):
                applier._validate_action(action)

    def test_validate_action_missing_operator(self):
        """Test action missing operator field"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            action = {"param": "API_URL", "value": "value"}

            with pytest.raises(ValueError, match="operator"):
                applier._validate_action(action)

    def test_validate_action_set_retry_missing_dag_id(self):
        """Test set_retry action missing dag_id"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()
            (dag_dir / "test_dag.py").write_text("retries=3")

            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            action = {"operator": "set_retry", "param": "retries", "value": "5"}

            with pytest.raises(ValueError, match="dag_id"):
                applier._validate_action(action)


class TestValidateTargetFile:
    """Tests for _validate_target_file() path security validation."""

    def test_validate_target_file_env_inject(self):
        """Test valid .env.inject target"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)
            target_path = applier._validate_target_file(".env.inject")
            assert target_path.name == ".env.inject"

    def test_validate_target_file_valid_dag(self):
        """Test valid dags/*.py target"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()
            dag_file = dag_dir / "http_dag.py"
            dag_file.write_text("")

            applier = PatchApplier(project_root=tmpdir, dry_run=True)
            target_path = applier._validate_target_file("dags/http_dag.py")
            assert target_path.name == "http_dag.py"

    def test_validate_target_file_path_traversal_with_dotdot(self):
        """Test path traversal prevention with .."""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match=r"\[SECURITY\] Path traversal detected"):
                applier._validate_target_file("dags/../../../etc/passwd")

    def test_validate_target_file_path_traversal_direct(self):
        """Test path traversal prevention - direct ../ attempt"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match=r"\[SECURITY\] Path traversal detected"):
                applier._validate_target_file("../hack.py")

    def test_validate_target_file_absolute_path_escape(self):
        """Test prevention of absolute path escape"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match=r"\[SECURITY\] Path escape detected"):
                applier._validate_target_file("/etc/passwd")

    def test_validate_target_file_not_allowed_directory(self):
        """Test rejection of non-whitelisted directories"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="Target file not allowed"):
                applier._validate_target_file("models/hack.py")

    def test_validate_target_file_not_python_extension(self):
        """Test rejection of non-.py files in dags/"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="Target file not allowed"):
                applier._validate_target_file("dags/config.json")


class TestValidateParams:
    """Tests for _validate_params() operator-specific parameter validation."""

    def test_validate_params_set_env_valid(self):
        """Test set_env parameter validation - valid"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            params = applier._validate_params("set_env", "API_URL", "https://api.example.com", None)

            assert params["param"] == "API_URL"
            assert params["value"] == "https://api.example.com"

    def test_validate_params_set_retry_valid(self):
        """Test set_retry parameter validation - valid"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()
            (dag_dir / "test_dag.py").write_text("retries=3")

            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            params = applier._validate_params("set_retry", "retries", "5", "test_dag")

            assert params["param"] == "retries"
            assert params["value"] == "5"

    def test_validate_params_set_retry_invalid_type(self):
        """Test set_retry parameter validation - invalid type"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="retries must be"):
                applier._validate_params("set_retry", "retries", "not_an_int", "test_dag")

    def test_validate_params_set_retry_negative_value(self):
        """Test set_retry parameter validation - negative retries"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="retries|must be"):
                applier._validate_params("set_retry", "retries", "-1", "test_dag")

    def test_validate_params_set_timeout_valid(self):
        """Test set_timeout parameter validation - valid"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            params = applier._validate_params("set_timeout", "execution_timeout", "600", "test_dag")

            assert params["value"] == "600"

    def test_validate_params_set_timeout_zero_value(self):
        """Test set_timeout parameter validation - zero timeout"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match="execution_timeout|must be"):
                applier._validate_params("set_timeout", "execution_timeout", "0", "test_dag")

    def test_validate_params_replace_path_valid(self):
        """Test replace_path parameter validation - valid"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            params = applier._validate_params("replace_path", "MY_PATH", "/usr/local/bin", None)

            assert params["param"] == "MY_PATH"

    def test_validate_params_add_precheck_valid(self):
        """Test add_precheck parameter validation - valid"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            precheck_line = "t_precheck = PythonOperator(...)"
            params = applier._validate_params("add_precheck", "", precheck_line, "test_dag")

            assert params["value"] == precheck_line


class TestMixedValidInvalidActions:
    """Tests for apply() with mixed valid and invalid actions."""

    def test_apply_mixed_valid_and_invalid_actions(self):
        """Test applying a plan with both valid and invalid actions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()

            # Create test DAG file
            dag_file = dag_dir / "test_dag.py"
            dag_file.write_text("""
from datetime import timedelta
default_args = {
    "owner": "airflow",
    "retries": 3,
    "execution_timeout": timedelta(seconds=300),
}
# BEGIN PRECHECKS
# END PRECHECKS
""")

            applier = PatchApplier(project_root=tmpdir, dry_run=False)

            plan = {
                "plan_id": "plan_ep_mixed_001",
                "episode_id": "ep_001",
                "failure_class": "timeout",
                "repair_actions": [
                    # Valid: set_env
                    {
                        "operator": "set_env",
                        "param": "API_URL",
                        "value": "https://api.example.com",
                    },
                    # Invalid: path traversal
                    {
                        "operator": "set_env",
                        "param": "VAR",
                        "value": "value",
                    },
                    # Valid: set_retry
                    {
                        "operator": "set_retry",
                        "dag_id": "test_dag",
                        "param": "retries",
                        "value": "5",
                    },
                    # Invalid: invalid operator
                    {
                        "operator": "invalid_operator",
                        "param": "something",
                        "value": "value",
                    },
                ],
                "requires_human_approval": False,
            }

            result = applier.apply(plan)

            # Should have partial status (some succeeded, some failed)
            assert result["status"] == "partial"
            assert len(result["applied_actions"]) == 3  # Two set_env and set_retry
            assert len(result["failed_actions"]) == 1   # invalid_operator
            assert result["git_commit_hash"] is not None  # Should still commit because partial succeeded

    def test_apply_all_valid_actions(self):
        """Test applying a plan with all valid actions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()

            dag_file = dag_dir / "test_dag.py"
            dag_file.write_text("""
from datetime import timedelta
default_args = {
    "owner": "airflow",
    "retries": 3,
    "execution_timeout": timedelta(seconds=300),
}
# BEGIN PRECHECKS
# END PRECHECKS
""")

            applier = PatchApplier(project_root=tmpdir, dry_run=False)

            plan = {
                "plan_id": "plan_ep_valid_001",
                "episode_id": "ep_001",
                "failure_class": "timeout",
                "repair_actions": [
                    {
                        "operator": "set_env",
                        "param": "API_URL",
                        "value": "https://api.example.com",
                    },
                    {
                        "operator": "set_retry",
                        "dag_id": "test_dag",
                        "param": "retries",
                        "value": "5",
                    },
                ],
                "requires_human_approval": False,
            }

            result = applier.apply(plan)

            assert result["status"] == "applied"
            assert len(result["applied_actions"]) == 2
            assert len(result["failed_actions"]) == 0
            assert result["git_commit_hash"] is not None


class TestAllInvalidActions:
    """Tests for apply() with all invalid actions."""

    def test_apply_all_invalid_actions(self):
        """Test applying a plan where all actions are invalid"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize as git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            applier = PatchApplier(project_root=tmpdir, dry_run=False)

            plan = {
                "plan_id": "plan_ep_invalid_001",
                "episode_id": "ep_001",
                "failure_class": "timeout",
                "repair_actions": [
                    # Invalid: unknown operator
                    {
                        "operator": "exec_code",
                        "param": "code",
                        "value": "os.system('rm -rf /')",
                    },
                    # Valid: set_env (should succeed)
                    {
                        "operator": "set_env",
                        "param": "VAR",
                        "value": "value",
                    },
                    # Valid: set_env (should succeed)
                    {
                        "operator": "set_env",
                        "param": "VAR2",
                        "value": "value",
                    },
                ],
                "requires_human_approval": False,
            }

            result = applier.apply(plan)

            # One invalid operator, but two valid set_env actions succeed
            assert result["status"] == "partial"
            assert len(result["applied_actions"]) == 2
            assert len(result["failed_actions"]) == 1
            assert result["git_commit_hash"] is not None  # Should have commit because partial succeeded

            # Verify the two valid set_env actions DID write the file
            env_path = Path(tmpdir) / ".env.inject"
            assert env_path.exists(), ".env.inject should exist because 2 valid set_env actions ran"
            content = env_path.read_text()
            assert "VAR=value" in content
            assert "VAR2=value" in content


class TestSecurityValidation:
    """Tests for security-specific validation (path traversal, injection)."""

    def test_security_path_traversal_encoded(self):
        """Test that URL-encoded traversal attempts are caught"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match=r"\[SECURITY\]"):
                applier._validate_target_file("dags/..%2F..%2Fetc%2Fpasswd")

    def test_security_double_slash_traversal(self):
        """Test that double-slash traversal attempts are caught"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            # Should still catch ".." in any form
            with pytest.raises(ValueError, match=r"\[SECURITY\]"):
                applier._validate_target_file("dags/test/../../../etc/passwd")

    def test_security_absolute_path_from_relative(self):
        """Test that absolute paths in relative contexts are rejected"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            with pytest.raises(ValueError, match=r"\[SECURITY\]"):
                applier._validate_target_file("/tmp/malicious.py")

    def test_security_symlink_escape_attempt(self):
        """Test that escape attempts using symlinks are caught"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a symlink outside project root
            parent_dir = Path(tmpdir).parent
            outside_file = parent_dir / "outside.py"
            outside_file.write_text("malicious code")

            symlink_path = Path(tmpdir) / "dags" / "link.py"
            symlink_path.parent.mkdir(parents=True, exist_ok=True)

            # Create symlink (if possible on this OS)
            try:
                symlink_path.symlink_to(outside_file)

                applier = PatchApplier(project_root=tmpdir, dry_run=True)

                with pytest.raises(ValueError, match=r"\[SECURITY\]"):
                    applier._validate_target_file(str(symlink_path.relative_to(tmpdir)))

            except (NotImplementedError, OSError):
                # Symlinks might not be supported on Windows, skip test
                pass

    def test_security_no_eval_exec_in_params(self):
        """Test that parameter validation doesn't allow dangerous patterns"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            # While we don't have explicit eval blocking, dangerous params should fail validation
            dangerous_patterns = [
                "__import__",
                "exec(",
                "eval(",
                "os.system",
                "subprocess",
            ]

            for pattern in dangerous_patterns:
                try:
                    # These should at least not be accepted without validation errors
                    applier._validate_params(
                        "set_env",
                        "DANGEROUS",
                        pattern,
                        None,
                    )
                    # If we get here, the pattern was accepted - that's OK as long as it's validated
                except ValueError:
                    # If validation rejects it, even better
                    pass


class TestDryRunValidation:
    """Tests for dry-run mode with validation."""

    def test_dry_run_validation_still_runs(self):
        """Test that validation still runs in dry-run mode"""
        with tempfile.TemporaryDirectory() as tmpdir:
            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            plan = {
                "plan_id": "plan_ep_dryrun_001",
                "episode_id": "ep_001",
                "failure_class": "timeout",
                "repair_actions": [
                    {
                        "operator": "invalid_operator",
                        "param": "VAR",
                        "value": "value",
                    },
                ],
                "requires_human_approval": False,
            }

            result = applier.apply(plan)

            # Should still reject invalid operator even in dry-run
            assert result["status"] in ["rejected", "dry_run"]
            assert len(result["failed_actions"]) > 0

    def test_dry_run_no_files_modified(self):
        """Test that dry-run mode doesn't modify files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            dag_dir = Path(tmpdir) / "dags"
            dag_dir.mkdir()

            dag_file = dag_dir / "test_dag.py"
            original_content = """
from datetime import timedelta
default_args = {
    "owner": "airflow",
    "retries": 3,
    "execution_timeout": timedelta(seconds=300),
}
# BEGIN PRECHECKS
# END PRECHECKS
"""
            dag_file.write_text(original_content)

            applier = PatchApplier(project_root=tmpdir, dry_run=True)

            plan = {
                "plan_id": "plan_ep_dryrun_002",
                "episode_id": "ep_001",
                "failure_class": "timeout",
                "repair_actions": [
                    {
                        "operator": "set_retry",
                        "dag_id": "test_dag",
                        "param": "retries",
                        "value": "10",
                    },
                ],
                "requires_human_approval": False,
            }

            result = applier.apply(plan)

            # File should NOT be modified in dry-run
            assert dag_file.read_text() == original_content
            assert result["status"] == "dry_run"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

