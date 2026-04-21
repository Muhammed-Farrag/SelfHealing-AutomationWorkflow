"""
Patch Applier — Milestone 2: Safe, Audited Configuration Patching.

Applies repair plans to Airflow configurations with full audit trail and rollback
capability via Git commits. Enforces strict safety rules:
  - Only modifies .env.inject and dags/*.py files
  - Rejects plans requiring human approval
  - Uses regex-only for DAG edits (no eval/exec/AST)
  - Creates Git commits for every change
  - Produces detailed audit logs
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


class PatchApplier:
    """
    Safe, audited patch applier for Airflow configuration and DAG files.

    Reads repair plans from JSONL, validates operators, applies patches
    with regex-only modifications, creates Git commits, and maintains audit logs.
    
    SECURITY: All patch actions are strictly validated before application.
    - Operators must be in the allowlist
    - Target files are validated with path traversal checks
    - Parameters are type-checked per operator
    """

    ALLOWED_OPERATORS = {"set_env", "set_retry", "set_timeout", "replace_path", "add_precheck"}
    ALLOWED_TARGET_FILES = {".env.inject", "dags/http_dag.py", "dags/db_dag.py", "dags/file_dag.py"}
    
    # Operator parameter schemas
    OPERATOR_PARAMS = {
        "set_env": {"param": str, "value": str},
        "set_retry": {"param": str, "value": str},
        "set_timeout": {"param": str, "value": str},
        "replace_path": {"param": str, "value": str},
        "add_precheck": {"dag_id": str, "value": str},
    }

    def __init__(
        self,
        project_root: str = ".",
        audit_log_path: str = "data/audit_log.jsonl",
        dry_run: bool = False,
    ) -> None:
        """
        Initialize the Patch Applier.

        Parameters
        ----------
        project_root : str
            Root directory of the project (must be a Git repository).
        audit_log_path : str
            Path where audit log entries will be appended (JSONL format).
        dry_run : bool
            If True, print changes without modifying files or committing.
        """
        self.project_root = Path(project_root).resolve()
        self.audit_log_path = Path(audit_log_path)
        self.dry_run = dry_run

        # Ensure project root is a Git repository
        if not (self.project_root / ".git").exists():
            if not self.dry_run:
                raise RuntimeError(f"Project root {self.project_root} is not a Git repository")
            console.print("[yellow]Warning:[/yellow] Not a Git repo (dry-run mode), proceeding anyway")

        # Create audit log parent directory if it doesn't exist
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # VALIDATION LAYER (CRITICAL SECURITY)
    # =========================================================================

    def _validate_action(self, action: dict[str, Any]) -> tuple[str, Optional[Path], dict[str, Any]]:
        """
        Validate a single repair action for correctness and safety.
        
        Performs comprehensive validation:
        1. Operator must be in ALLOWED_OPERATORS
        2. Target file must be safe (no path traversal, inside project_root)
        3. Parameters must match operator schema
        4. File must exist (if applicable)
        
        Parameters
        ----------
        action : dict
            The repair action from a repair plan:
            {
                "operator": str,
                "param": str,
                "value": str,
                "dag_id": str (optional)
            }
        
        Returns
        -------
        tuple[str, Optional[Path], dict]
            (operator, safe_target_path, validated_params)
        
        Raises
        ------
        ValueError
            If operator, target file, or parameters are invalid
        """
        # 1. Validate operator
        operator = action.get("operator")
        if not operator:
            raise ValueError("Missing required field: 'operator'")
        if operator not in self.ALLOWED_OPERATORS:
            raise ValueError(f"Invalid operator: {operator} (allowed: {self.ALLOWED_OPERATORS})")
        
        # 2. Extract and validate parameters
        param = action.get("param", "")
        value = action.get("value", "")
        dag_id = action.get("dag_id", "")
        
        if not param and operator != "add_precheck":
            raise ValueError(f"Missing required field 'param' for operator '{operator}'")
        if not value:
            raise ValueError(f"Missing required field 'value' for operator '{operator}'")
        
        # 3. Validate parameters based on operator type
        validated_params = self._validate_params(operator, param, value, dag_id)
        
        # 4. Validate target file (this returns the safe path)
        target_file = self._get_target_file(operator, dag_id or param.split(".")[0], param)
        safe_target_path = self._validate_target_file(target_file)
        
        # 5. Verify file exists (for DAGs)
        if safe_target_path.name.endswith(".py") and not safe_target_path.exists():
            raise ValueError(f"DAG file not found: {target_file}")
        
        return operator, safe_target_path, validated_params

    def _validate_target_file(self, target_file: str) -> Path:
        """
        Validate that target_file is safe and within allowed locations.
        
        CRITICAL SECURITY CHECKS:
        - No path traversal attempts (..)
        - No absolute paths outside project_root
        - Must be .env.inject or dags/*.py
        - Must resolve within project_root
        
        Parameters
        ----------
        target_file : str
            The target file path (relative or absolute)
        
        Returns
        -------
        Path
            The resolved, safe path within project_root
        
        Raises
        ------
        ValueError
            If the path contains traversal attempts or is outside allowed locations
        """
        # Check for obvious path traversal attempts
        if ".." in target_file:
            raise ValueError(f"[SECURITY] Path traversal detected: {target_file}")
        
        # Try to resolve the path
        if target_file.startswith("/"):
            # Absolute path - must be inside project_root
            target_path = Path(target_file).resolve()
        else:
            # Relative path
            target_path = (self.project_root / target_file).resolve()
        
        # Verify the path is inside project_root
        try:
            target_path.relative_to(self.project_root)
        except ValueError:
            raise ValueError(
                f"[SECURITY] Path escape detected: {target_file} resolves to {target_path} "
                f"which is outside project root {self.project_root}"
            )
        
        # Verify target is in allowed locations
        if target_file == ".env.inject":
            return target_path
        
        if target_file.startswith("dags/") and target_file.endswith(".py"):
            return target_path
        
        raise ValueError(
            f"Target file not allowed: {target_file}. "
            f"Must be '.env.inject' or 'dags/*.py' in the project root."
        )

    def _validate_params(
        self, operator: str, param: str, value: str, dag_id: str
    ) -> dict[str, Any]:
        """
        Validate operation-specific parameters.
        
        Parameters
        ----------
        operator : str
            The operator type
        param : str
            The parameter name or key
        value : str
            The parameter value
        dag_id : str
            The DAG ID (for DAG-specific operators)
        
        Returns
        -------
        dict
            Validated parameters for the operator
        
        Raises
        ------
        ValueError
            If parameters are invalid or have wrong types
        """
        if operator == "set_env":
            if not isinstance(param, str) or not param.strip():
                raise ValueError(f"set_env: param must be a non-empty string, got {type(param)}")
            if not isinstance(value, str):
                raise ValueError(f"set_env: value must be a string, got {type(value)}")
            return {"param": param, "value": value}
        
        elif operator == "set_retry":
            if not isinstance(param, str) or param != "retries":
                raise ValueError(f"set_retry: param must be 'retries', got {param}")
            try:
                retry_count = int(value)
                if retry_count < 0:
                    raise ValueError("retries must be >= 0")
            except (ValueError, TypeError):
                raise ValueError(f"retries must be a non-negative integer, got {value}")
            if not dag_id:
                raise ValueError("set_retry: required field 'dag_id' is missing")
            return {"dag_id": dag_id, "param": param, "value": str(retry_count)}
        
        elif operator == "set_timeout":
            if not isinstance(param, str) or param != "execution_timeout":
                raise ValueError(f"set_timeout: param must be 'execution_timeout', got {param}")
            try:
                timeout_sec = int(value)
                if timeout_sec <= 0:
                    raise ValueError("timeout must be > 0")
            except (ValueError, TypeError):
                raise ValueError(f"set_timeout: value must be a positive integer, got {value}")
            if not dag_id:
                raise ValueError("set_timeout: required field 'dag_id' is missing")
            return {"dag_id": dag_id, "param": param, "value": str(timeout_sec)}
        
        elif operator == "replace_path":
            if not isinstance(param, str) or not param.strip():
                raise ValueError(f"replace_path: param must be a non-empty string, got {param}")
            if not isinstance(value, str):
                raise ValueError(f"replace_path: value must be a string, got {value}")
            return {"param": param, "value": value}
        
        elif operator == "add_precheck":
            if not isinstance(dag_id, str) or not dag_id.strip():
                raise ValueError(f"add_precheck: dag_id must be a non-empty string")
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"add_precheck: value (code) must be a non-empty string")
            return {"dag_id": dag_id, "value": value}
        
        else:
            raise ValueError(f"Unknown operator: {operator}")

    def _get_target_file(self, operator: str, dag_id: str, param: str) -> str:
        """
        Determine the target file for an operator.
        
        Parameters
        ----------
        operator : str
            The operator type
        dag_id : str
            The DAG ID (for DAG-specific operators)
        param : str
            The parameter name
        
        Returns
        -------
        str
            The target file path (relative to project_root)
        """
        if operator in {"set_env", "replace_path"}:
            return ".env.inject"
        elif operator in {"set_retry", "set_timeout", "add_precheck"}:
            return f"dags/{dag_id}.py"
        else:
            raise ValueError(f"Unknown operator: {operator}")

    def apply(self, repair_plan: dict[str, Any]) -> dict[str, Any]:
        """
        Apply all repair actions from a single RepairPlan.

        Validates the plan, rejects if requires_human_approval=True, applies
        each action, creates a Git commit, and writes an audit log entry.

        Parameters
        ----------
        repair_plan : dict
            The repair plan dict from data/repair_plans.jsonl with keys:
              - plan_id (str)
              - failure_class (str)
              - repair_actions (list[dict])
              - requires_human_approval (bool)

        Returns
        -------
        dict
            Result dict with keys:
              - plan_id (str)
              - status ("applied" | "rejected" | "partial" | "dry_run")
              - applied_actions (list[str])
              - failed_actions (list[str])
              - git_commit_hash (str | None)
              - audit_log_entry (dict)
        """
        plan_id = repair_plan.get("plan_id", "unknown")
        failure_class = repair_plan.get("failure_class", "unknown")
        episode_id = repair_plan.get("episode_id", plan_id.replace("plan_", ""))
        repair_actions = repair_plan.get("repair_actions", [])
        requires_human_approval = repair_plan.get("requires_human_approval", False)

        applied_actions: list[str] = []
        failed_actions: list[str] = []
        diffs: dict[str, str] = {}
        git_commit_hash: Optional[str] = None
        status = "applied"

        # Step 1: Check for human approval requirement
        if requires_human_approval:
            console.print(
                f"[yellow]Rejecting plan {plan_id}:[/yellow] requires_human_approval=True"
            )
            audit_entry = {
                "plan_id": plan_id,
                "episode_id": episode_id,
                "failure_class": failure_class,
                "status": "rejected",
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "applied_actions": [],
                "failed_actions": [],
                "git_commit_hash": None,
                "dry_run": self.dry_run,
                "diffs": {},
                "rejection_reason": "requires_human_approval=True",
            }
            self._write_audit_entry(audit_entry)
            return {
                "plan_id": plan_id,
                "status": "rejected",
                "applied_actions": [],
                "failed_actions": ["All actions rejected"],
                "git_commit_hash": None,
                "audit_log_entry": audit_entry,
            }

        # Step 2: Apply each repair action with validation
        for action in repair_actions:
            action_desc = f"{action.get('operator')}({action.get('param')})"
            try:
                # VALIDATION: Validate action before applying
                operator, safe_target_path, params = self._validate_action(action)
                
                # Apply the action
                if operator == "set_env":
                    diff_str = self._apply_set_env(params["param"], params["value"])
                elif operator == "set_retry":
                    diff_str = self._apply_set_retry(params["dag_id"], params["param"], params["value"])
                elif operator == "set_timeout":
                    diff_str = self._apply_set_timeout(params["dag_id"], params["param"], params["value"])
                elif operator == "replace_path":
                    diff_str = self._apply_replace_path(params["param"], params["value"])
                elif operator == "add_precheck":
                    diff_str = self._apply_add_precheck(params["dag_id"], params["value"])
                else:
                    raise ValueError(f"Unknown operator: {operator}")

                applied_actions.append(action_desc)
                if diff_str:
                    diffs[str(safe_target_path)] = diff_str

                console.print(f"[green]✓[/green] Applied {action_desc}")

            except Exception as exc:
                failed_actions.append(f"{action_desc}: {str(exc)}")
                console.print(f"[red]✗[/red] Failed {action_desc}: {str(exc)}")
                status = "partial" if applied_actions else "rejected"

        # Step 3: Determine final status
        if not applied_actions:
            status = "rejected"
        elif failed_actions:
            status = "partial"
        else:
            status = "applied"

        # Step 4: Git commit if we have applied actions (unless dry-run)
        if applied_actions and not self.dry_run:
            try:
                git_commit_hash = self._git_commit(plan_id, failure_class)
                console.print(f"[green]Git commit:[/green] {git_commit_hash}")
            except RuntimeError as exc:
                console.print(f"[red]Git commit failed:[/red] {str(exc)}")
                status = "partial"
                failed_actions.append(f"git_commit: {str(exc)}")
        
        # Override status to "dry_run" if in dry-run mode AND plan fully succeeded
        if self.dry_run and status == "applied":
            status = "dry_run"

        # Step 5: Write audit log entry
        audit_entry = {
            "plan_id": plan_id,
            "episode_id": episode_id,
            "failure_class": failure_class,
            "status": status,
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "applied_actions": applied_actions,
            "failed_actions": failed_actions,
            "git_commit_hash": git_commit_hash if applied_actions and not self.dry_run else None,
            "dry_run": self.dry_run,
            "diffs": diffs,
        }
        self._write_audit_entry(audit_entry)

        return {
            "plan_id": plan_id,
            "status": status,
            "applied_actions": applied_actions,
            "failed_actions": failed_actions,
            "git_commit_hash": git_commit_hash,
            "audit_log_entry": audit_entry,
        }

    def apply_batch(self, plans_jsonl: str) -> None:
        """
        Apply all repair plans from a JSONL file.

        Skips plans with requires_human_approval=True. Prints a summary
        of applied, rejected, and pending_human_review counts.

        Parameters
        ----------
        plans_jsonl : str
            Path to the repair_plans.jsonl file.
        """
        plans_path = Path(plans_jsonl)
        if not plans_path.exists():
            console.print(f"[red]Error:[/red] {plans_jsonl} not found")
            return

        applied = 0
        rejected = 0
        pending_human_review = 0
        partial = 0

        console.print(f"\n[bold cyan]Processing {plans_path}...[/bold cyan]")

        with open(plans_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                if not line.strip():
                    continue

                try:
                    plan = json.loads(line)
                    result = self.apply(plan)

                    if result["status"] == "rejected":
                        if plan.get("requires_human_approval"):
                            pending_human_review += 1
                        else:
                            rejected += 1
                    elif result["status"] == "applied":
                        applied += 1
                    elif result["status"] == "partial":
                        partial += 1

                except json.JSONDecodeError as exc:
                    console.print(f"[yellow]Warning:[/yellow] Line {line_num} is not valid JSON: {str(exc)}")
                except Exception as exc:
                    console.print(f"[red]Error processing plan at line {line_num}:[/red] {str(exc)}")

        # Print summary
        console.print("\n[bold cyan]Summary:[/bold cyan]")
        table = Table(title="Batch Application Results")
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="magenta")
        table.add_row("Applied", str(applied), style="green")
        table.add_row("Partial", str(partial), style="yellow")
        table.add_row("Rejected", str(rejected), style="red")
        table.add_row("Pending Human Review", str(pending_human_review), style="yellow")
        console.print(table)

    # =========================================================================
    # Operator Implementations
    # =========================================================================

    def _apply_set_env(self, param: str, value: str) -> str:
        """
        Write or update param=value in .env.inject.

        Creates the file if it doesn't exist. Returns a unified diff string
        showing the before/after state.

        Parameters
        ----------
        param : str
            Environment variable name (e.g., "API_URL").
        value : str
            Environment variable value.

        Returns
        -------
        str
            Unified diff showing the change.

        Raises
        ------
        ValueError
            If the operation would violate safety rules.
        """
        env_inject_path = self.project_root / ".env.inject"

        # Read existing content or start fresh
        if env_inject_path.exists():
            with open(env_inject_path, "r", encoding="utf-8") as f:
                old_content = f.read()
        else:
            old_content = ""

        # Parse existing env vars
        env_dict: dict[str, str] = {}
        if old_content:
            for line in old_content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env_dict[k.strip()] = v.strip()

        # Update or add the new value
        env_dict[param] = value

        # Rebuild content
        new_lines = [f"{k}={v}" for k, v in sorted(env_dict.items())]
        new_content = "\n".join(new_lines) + "\n"

        # Generate diff
        diff_str = self._generate_diff(".env.inject", old_content, new_content)

        # Write file (unless dry_run)
        if not self.dry_run:
            env_inject_path.write_text(new_content, encoding="utf-8")
            console.print(f"[dim]Wrote {param}={value} to .env.inject[/dim]")

        return diff_str

    def _apply_set_retry(self, dag_id: str, param: str, value: str) -> str:
        """
        Update retries=<value> in dags/<dag_id>.py default_args.

        Uses regex replacement to find and update the retries line.
        Only modifies the first occurrence within default_args.

        Parameters
        ----------
        dag_id : str
            The DAG ID (e.g., "http_dag", "db_dag", "file_dag").
        param : str
            Parameter name (should be "retries").
        value : str
            New retry count as a string (e.g., "5").

        Returns
        -------
        str
            Unified diff showing the change.

        Raises
        ------
        ValueError
            If the DAG file doesn't exist or pattern not found.
        """
        dag_path = self.project_root / f"dags/{dag_id}.py"

        if not dag_path.exists():
            raise ValueError(f"DAG file not found: {dag_path}")

        with open(dag_path, "r", encoding="utf-8") as f:
            old_content = f.read()

        # Pattern: match "retries": <number> (Python dict format with quoted key)
        pattern = r'(["\']?retries["\']?\s*[:=]\s*)(\d+|[A-Za-z_]\w*)'
        if not re.search(pattern, old_content):
            raise ValueError(
                f"Pattern 'retries' not found in {dag_path}. "
                "Ensure default_args is defined with a retries entry."
            )

        new_content = re.sub(pattern, rf"\g<1>{value}", old_content, count=1)

        # Generate diff
        diff_str = self._generate_diff(f"dags/{dag_id}.py", old_content, new_content)

        # Write file (unless dry_run)
        if not self.dry_run:
            dag_path.write_text(new_content, encoding="utf-8")
            console.print(f"[dim]Updated retries={value} in {dag_id}.py[/dim]")

        return diff_str

    def _apply_set_timeout(self, dag_id: str, param: str, value: str) -> str:
        """
        Update execution_timeout=timedelta(...) in dags/<dag_id>.py.

        Uses regex replacement to find and update the execution_timeout line.
        Expects value to be in the format expected by timedelta (e.g., "300" for seconds,
        or "timedelta(seconds=300)").

        Parameters
        ----------
        dag_id : str
            The DAG ID (e.g., "http_dag", "db_dag", "file_dag").
        param : str
            Parameter name (should be "execution_timeout").
        value : str
            New timeout value as a string (e.g., "300" for seconds or
            "timedelta(seconds=300)").

        Returns
        -------
        str
            Unified diff showing the change.

        Raises
        ------
        ValueError
            If the DAG file doesn't exist or pattern not found.
        """
        dag_path = self.project_root / f"dags/{dag_id}.py"

        if not dag_path.exists():
            raise ValueError(f"DAG file not found: {dag_path}")

        with open(dag_path, "r", encoding="utf-8") as f:
            old_content = f.read()

        # Pattern: match "execution_timeout": timedelta(...) (Python dict format)
        pattern = r'(["\']?execution_timeout["\']?\s*[:=]\s*)(timedelta\([^)]+\))'
        if not re.search(pattern, old_content):
            raise ValueError(
                f"Pattern 'execution_timeout' not found in {dag_path}. "
                "Ensure default_args is defined with an execution_timeout entry."
            )

        # Format value as timedelta if not already formatted
        if not value.startswith("timedelta"):
            value = f"timedelta(seconds={value})"

        new_content = re.sub(pattern, rf"\g<1>{value}", old_content, count=1)

        # Generate diff
        diff_str = self._generate_diff(f"dags/{dag_id}.py", old_content, new_content)

        # Write file (unless dry_run)
        if not self.dry_run:
            dag_path.write_text(new_content, encoding="utf-8")
            console.print(f"[dim]Updated execution_timeout={value} in {dag_id}.py[/dim]")

        return diff_str

    def _apply_replace_path(self, param: str, value: str) -> str:
        """
        Replace or update a PATH-like environment variable in .env.inject.

        Similar to _apply_set_env but specifically for PATH variables.
        Returns a unified diff.

        Parameters
        ----------
        param : str
            PATH variable name (e.g., "PYTHONPATH", "PATH").
        value : str
            New PATH value.

        Returns
        -------
        str
            Unified diff showing the change.
        """
        return self._apply_set_env(param, value)

    def _apply_add_precheck(self, dag_id: str, value: str) -> str:
        """
        Append a precheck line to the # PRECHECKS block in dags/<dag_id>.py.

        The DAG file must contain markers:
          # BEGIN PRECHECKS
          ...
          # END PRECHECKS

        The value (task call) will be appended before the # END PRECHECKS line.

        Parameters
        ----------
        dag_id : str
            The DAG ID (e.g., "http_dag", "db_dag", "file_dag").
        value : str
            The precheck task line to add (e.g.,
            "t_precheck_timeout = PythonOperator(...)").

        Returns
        -------
        str
            Unified diff showing the change.

        Raises
        ------
        ValueError
            If the DAG file doesn't exist or PRECHECKS block not found.
        """
        dag_path = self.project_root / f"dags/{dag_id}.py"

        if not dag_path.exists():
            raise ValueError(f"DAG file not found: {dag_path}")

        with open(dag_path, "r", encoding="utf-8") as f:
            old_content = f.read()

        # Check for PRECHECKS block
        if "# BEGIN PRECHECKS" not in old_content or "# END PRECHECKS" not in old_content:
            raise ValueError(
                f"PRECHECKS block not found in {dag_path}. "
                "Ensure # BEGIN PRECHECKS and # END PRECHECKS markers exist."
            )

        # Append the precheck line before # END PRECHECKS
        new_content = old_content.replace(
            "# END PRECHECKS",
            f"{value}\n    # END PRECHECKS",
        )

        # Generate diff
        diff_str = self._generate_diff(f"dags/{dag_id}.py", old_content, new_content)

        # Write file (unless dry_run)
        if not self.dry_run:
            dag_path.write_text(new_content, encoding="utf-8")
            console.print(f"[dim]Added precheck to {dag_id}.py[/dim]")

        return diff_str

    # =========================================================================
    # Git & Audit
    # =========================================================================

    def _git_commit(self, plan_id: str, failure_class: str) -> str:
        """
        Create a Git commit for all modified files.

        Stages all modified files (git add -u) and commits with the message:
        "auto-repair: {plan_id} ({failure_class})"

        Parameters
        ----------
        plan_id : str
            The repair plan ID.
        failure_class : str
            The failure class being repaired.

        Returns
        -------
        str
            Short Git commit hash (7 chars).

        Raises
        ------
        RuntimeError
            If Git operations fail.
        """
        try:
            # Stage all modified and new files
            subprocess.run(
                ["git", "-C", str(self.project_root), "add", "."],
                check=True,
                capture_output=True,
                text=True,
            )

            # Create commit
            commit_msg = f"auto-repair: {plan_id} ({failure_class})"
            result = subprocess.run(
                ["git", "-C", str(self.project_root), "commit", "-m", commit_msg],
                check=True,
                capture_output=True,
                text=True,
            )

            # Get short hash
            hash_result = subprocess.run(
                ["git", "-C", str(self.project_root), "rev-parse", "--short", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            commit_hash = hash_result.stdout.strip()
            return commit_hash

        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Git commit failed: {exc.stderr or exc.stdout}"
            ) from exc

    def _write_audit_entry(self, entry: dict[str, Any]) -> None:
        """
        Append one JSON record to the audit log file.

        Flushes immediately to ensure the log is persisted.

        Parameters
        ----------
        entry : dict
            The audit log entry to write (will be converted to JSON).
        """
        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            json.dump(entry, f)
            f.write("\n")
            f.flush()

        console.print(f"[dim]Audit entry logged[/dim]")

    # =========================================================================
    # Utilities
    # =========================================================================

    def _generate_diff(self, filename: str, old_content: str, new_content: str) -> str:
        """
        Generate a unified diff string.

        Parameters
        ----------
        filename : str
            The filename (for display purposes).
        old_content : str
            The original file content.
        new_content : str
            The new file content.

        Returns
        -------
        str
            A unified diff string.
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = list(
            unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{filename}",
                tofile=f"b/{filename}",
                lineterm="",
            )
        )

        return "".join(diff_lines)

    def _extract_target_file(
        self,
        diff_str: str,
        operator: str,
        param: str,
        dag_id: Optional[str] = None,
    ) -> str:
        """
        Extract the target filename from a diff string or infer from operator.

        Parameters
        ----------
        diff_str : str
            The diff string (may be empty or contain file info).
        operator : str
            The operator name (set_env, set_retry, etc.).
        param : str
            The parameter name.
        dag_id : str, optional
            The DAG ID if applicable.

        Returns
        -------
        str
            The target filename.
        """
        if operator in {"set_env", "replace_path"}:
            return ".env.inject"
        elif operator == "set_retry":
            return f"dags/{dag_id}.py"
        elif operator == "set_timeout":
            return f"dags/{dag_id}.py"
        elif operator == "add_precheck":
            return f"dags/{dag_id}.py"
        else:
            return "unknown"


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Safe, audited patch applier for Airflow configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run a single plan
  python -m patcher.patch_applier --plan data/repair_plans.jsonl \\
      --plan-id plan_ep_001 --dry-run

  # Apply all plans
  python -m patcher.patch_applier --apply-all data/repair_plans.jsonl

  # Show audit log
  python -m patcher.patch_applier --audit
        """,
    )

    parser.add_argument(
        "--plan",
        type=str,
        help="Path to repair_plans.jsonl file",
        default="data/repair_plans.jsonl",
    )
    parser.add_argument(
        "--plan-id",
        type=str,
        help="Specific plan ID to test (requires --plan)",
    )
    parser.add_argument(
        "--apply-all",
        type=str,
        help="Apply all plans from the specified JSONL file",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Display audit log",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate changes without modifying files",
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=".",
        help="Project root directory (must be a Git repo)",
    )
    parser.add_argument(
        "--audit-log",
        type=str,
        default="data/audit_log.jsonl",
        help="Path to audit log file",
    )

    return parser.parse_args()


def _show_audit_log(audit_log_path: str) -> None:
    """Display the audit log in a formatted table."""
    audit_path = Path(audit_log_path)
    if not audit_path.exists():
        console.print(f"[yellow]Audit log not found:[/yellow] {audit_log_path}")
        return

    console.print(f"\n[bold cyan]Audit Log: {audit_log_path}[/bold cyan]\n")

    table = Table(title="Patch Application Audit Trail")
    table.add_column("Plan ID", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Applied Actions", style="green")
    table.add_column("Failed Actions", style="red")
    table.add_column("Commit Hash", style="magenta")

    with open(audit_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
                plan_id = entry.get("plan_id", "unknown")
                status = entry.get("status", "unknown")
                applied = len(entry.get("applied_actions", []))
                failed = len(entry.get("failed_actions", []))
                commit = entry.get("git_commit_hash", "—")

                status_color = {
                    "applied": "green",
                    "rejected": "red",
                    "partial": "yellow",
                    "dry_run": "blue",
                }.get(status, "white")

                table.add_row(
                    plan_id,
                    f"[{status_color}]{status}[/{status_color}]",
                    str(applied),
                    str(failed),
                    commit[:7] if commit and commit != "—" else "—",                )

            except json.JSONDecodeError:
                pass

    console.print(table)


if __name__ == "__main__":
    args = _parse_args()

    applier = PatchApplier(
        project_root=args.project_root,
        audit_log_path=args.audit_log,
        dry_run=args.dry_run,
    )

    if args.audit:
        _show_audit_log(args.audit_log)
        sys.exit(0)

    if args.apply_all:
        applier.apply_batch(args.apply_all)
        sys.exit(0)

    if args.plan_id:
        # Find and apply a specific plan
        plans_path = Path(args.plan)
        if not plans_path.exists():
            console.print(f"[red]Error:[/red] {args.plan} not found")
            sys.exit(1)

        found = False
        with open(plans_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    plan = json.loads(line)
                    if plan.get("plan_id") == args.plan_id:
                        console.print(
                            f"\n[bold cyan]Applying plan {args.plan_id}[/bold cyan] "
                            f"(dry-run={args.dry_run})\n"
                        )
                        result = applier.apply(plan)

                        console.print(f"\n[bold cyan]Result:[/bold cyan]")
                        console.print(f"  Status: {result['status']}")
                        console.print(f"  Applied: {len(result['applied_actions'])}")
                        console.print(f"  Failed: {len(result['failed_actions'])}")
                        if result["git_commit_hash"]:
                            console.print(f"  Commit: {result['git_commit_hash']}")

                        found = True
                        break

                except json.JSONDecodeError:
                    pass

        if not found:
            console.print(f"[red]Plan not found:[/red] {args.plan_id}")
            sys.exit(1)
    else:
        console.print(
            "[yellow]Usage:[/yellow] specify --plan-id, --apply-all, or --audit"
        )
        sys.exit(1)
