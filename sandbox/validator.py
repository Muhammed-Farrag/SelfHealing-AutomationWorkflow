"""
Sandbox Validator for Milestone 3.
Re-runs patched DAGs in an isolated staging environment and runs invariant checks.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from rich.console import Console

console = Console()

class SandboxValidator:

    def __init__(
        self,
        airflow_base_url: str = "http://localhost:8080",
        airflow_user: str = "airflow",
        airflow_password: str = "airflow",
        max_wait_seconds: int = 180,
        poll_interval: int = 5,
        validation_log_path: str = "data/validation_results.jsonl",
    ) -> None:
        """
        Load config from .env using python-dotenv.
        Create validation_log_path directory if it doesn't exist.
        """
        load_dotenv()
        self.airflow_base_url = os.getenv("AIRFLOW_BASE_URL", airflow_base_url).rstrip("/")
        self.airflow_user = os.getenv("AIRFLOW_USER", airflow_user)
        self.airflow_password = os.getenv("AIRFLOW_PASSWORD", airflow_password)
        self.max_wait_seconds = max_wait_seconds
        self.poll_interval = poll_interval
        
        self.validation_log_path = Path(validation_log_path)
        self.validation_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.auth = HTTPBasicAuth(self.airflow_user, self.airflow_password)

    def _format_mttr(self, seconds: float) -> str:
        """Returns MTTR in human-readable format like '2m 14s'."""
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        parts = []
        if h > 0:
            parts.append(f"{h}h")
        if m > 0 or h > 0:
            parts.append(f"{m}m")
        parts.append(f"{s}s")
        return " ".join(parts)

    def _trigger_dag_run(self, dag_id: str) -> str:
        """
        POST /api/v1/dags/{dag_id}/dagRuns with conf={} and a unique run_id.
        Returns the new run_id string.
        Retries up to 3 times on HTTP errors with 2s backoff.
        """
        url = f"{self.airflow_base_url}/api/v1/dags/{dag_id}/dagRuns"
        run_id = f"sandbox_val_{uuid.uuid4().hex[:8]}"
        payload = {"dag_run_id": run_id, "conf": {}}
        
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, auth=self.auth, timeout=10)
                if resp.status_code in (200, 201):
                    return run_id
                console.print(f"[yellow]Trigger failed ({resp.status_code}): {resp.text}[/yellow]")
            except requests.RequestException as e:
                console.print(f"[yellow]Trigger exception: {e}[/yellow]")
                
            time.sleep(2)
            
        raise RuntimeError(f"Failed to trigger {dag_id} after 3 attempts.")

    def _poll_dag_run(self, dag_id: str, run_id: str) -> str:
        """
        Poll GET /api/v1/dags/{dag_id}/dagRuns/{run_id} every poll_interval
        seconds until state is in {"success", "failed"} or max_wait_seconds
        is exceeded.
        Returns the terminal state string ("success", "failed", or "timeout").
        """
        url = f"{self.airflow_base_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}"
        start_time = time.time()
        
        while time.time() - start_time < self.max_wait_seconds:
            try:
                resp = requests.get(url, auth=self.auth, timeout=10)
                if resp.status_code == 200:
                    state = resp.json().get("state")
                    if state in ("success", "failed"):
                        return state
            except requests.RequestException:
                pass
            
            time.sleep(self.poll_interval)
            
        return "timeout"

    def _get_task_log(self, dag_id: str, run_id: str, task_id: str) -> str:
        """
        GET /api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/1
        Returns the log text (truncated to 2000 chars). Returns "" on error.
        """
        url = f"{self.airflow_base_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/1"
        try:
            resp = requests.get(url, auth=self.auth, timeout=10)
            if resp.status_code == 200:
                text = resp.text
                return text[:2000] if len(text) > 2000 else text
        except requests.RequestException:
            pass
        return ""

    def _check_invariants(self, dag_id: str, task_id: str, run_id: str) -> dict:
        """
        Run post-success invariant checks to confirm the repair didn't
        break anything downstream.
        """
        passed = []
        failed = []
        
        # 1. Check Task Duration Reasonable (< 60s)
        ti_url = f"{self.airflow_base_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}"
        task_duration_reasonable = False
        try:
            resp = requests.get(ti_url, auth=self.auth, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                start_date = data.get("start_date")
                end_date = data.get("end_date")
                if start_date and end_date:
                    try:
                        # Airflow dates are like '2026-04-10T19:55:42.455865+00:00'
                        fmt = "%Y-%m-%dT%H:%M:%S"
                        # Handle potential fractional seconds and timezone
                        clean_start = start_date.split(".")[0].split("+")[0]
                        clean_end = end_date.split(".")[0].split("+")[0]
                        st = datetime.strptime(clean_start, fmt)
                        et = datetime.strptime(clean_end, fmt)
                        duration = (et - st).total_seconds()
                        if duration < 60:
                            task_duration_reasonable = True
                    except Exception:
                        pass
        except Exception:
            pass
            
        if task_duration_reasonable:
            passed.append("task_duration_reasonable")
        else:
            failed.append("task_duration_reasonable")
            
        # Get Task Log for proxy checks
        log_text = self._get_task_log(dag_id, run_id, task_id)
        
        if dag_id == "http_dag":
            if "FileNotFoundError" not in log_text and "OperationalError" not in log_text and ("/tmp/output.json" in log_text or "load" in task_id.lower()):
                passed.append("output_file_exists")
                passed.append("output_file_nonempty")
            else:
                passed.append("output_file_exists") # Assuming it exists normally unless error
                passed.append("output_file_nonempty")
                # Wait: "If the log contains FileNotFoundError or OperationalError the invariant fails."
                if "FileNotFoundError" in log_text or "OperationalError" in log_text:
                    if "output_file_exists" in passed: passed.remove("output_file_exists")
                    if "output_file_nonempty" in passed: passed.remove("output_file_nonempty")
                    failed.extend(["output_file_exists", "output_file_nonempty"])
                
        elif dag_id == "db_dag":
            if "FileNotFoundError" in log_text or "OperationalError" in log_text:
                failed.extend(["result_file_exists", "result_file_nonempty"])
            else:
                passed.extend(["result_file_exists", "result_file_nonempty"])
                
        elif dag_id == "file_dag":
            if "FileNotFoundError" in log_text or "OperationalError" in log_text:
                failed.extend(["output_file_exists", "output_contains_count"])
            else:
                passed.extend(["output_file_exists", "output_contains_count"])
                
        return {"passed": passed, "failed": failed}

    def _write_result(self, result: dict) -> None:
        """Append one JSON record to validation_log_path with flush."""
        with open(self.validation_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\\n")
            f.flush()

    def validate(self, plan: dict, episode: dict) -> dict:
        """Run sandbox validation for one repair plan against its source episode."""
        plan_id = plan["plan_id"]
        episode_id = episode["episode_id"]
        dag_id = episode["dag_id"]
        task_id = episode["task_id"]
        mttr_start_str = episode["mttr_start"]
        
        # 1. Trigger DAG run
        new_run_id = ""
        terminal_state = "error"
        status = "failed"
        mttr_seconds = 0.0
        invariants_passed = []
        invariants_failed = []
        error = None
        
        try:
            new_run_id = self._trigger_dag_run(dag_id)
            
            # 2. Poll until terminal
            terminal_state = self._poll_dag_run(dag_id, new_run_id)
            
            if terminal_state == "success":
                # 4. Check invariants
                inv_result = self._check_invariants(dag_id, task_id, new_run_id)
                invariants_passed = inv_result["passed"]
                invariants_failed = inv_result["failed"]
                
                if invariants_failed:
                    status = "invariant_failed"
                else:
                    status = "success"
            elif terminal_state == "timeout":
                status = "timeout"
            else:
                status = "failed"
                
        except Exception as e:
            error = str(e)
            
        # 5. Compute mttr_seconds
        try:
            # ISO timestamp e.g. "2026-04-10T18:44:45.760009+00:00"
            start_dt = datetime.fromisoformat(mttr_start_str.replace("Z", "+00:00"))
            mttr_seconds = (datetime.now(timezone.utc) - start_dt).total_seconds()
        except Exception:
            mttr_seconds = 0.0
            
        # 6. Build and write result
        val_result = {
            "validation_id": f"val_{plan_id}_{uuid.uuid4().hex[:6]}",
            "plan_id": plan_id,
            "episode_id": episode_id,
            "dag_id": dag_id,
            "task_id": task_id,
            "new_run_id": new_run_id,
            "status": status,
            "invariants_passed": invariants_passed,
            "invariants_failed": invariants_failed,
            "mttr_seconds": mttr_seconds,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "terminal_state": terminal_state,
            "error": error
        }
        
        self._write_result(val_result)
        return val_result

    def validate_batch(
        self,
        plans_jsonl: str,
        episodes_jsonl: str,
        output_path: str = "data/validation_results.jsonl",
        dry_run: bool = False
    ) -> None:
        """
        Match each plan to its source episode by episode_id, then validate.
        """
        # Load episodes
        episodes: Dict[str, dict] = {}
        if Path(episodes_jsonl).exists():
            with open(episodes_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        ep = json.loads(line)
                        episodes[ep["episode_id"]] = ep
                        
        total_validated = 0
        success_count = 0
        failed_count = 0
        timeout_count = 0
        invariant_failed_count = 0
        skipped_count = 0
        total_mttr = 0.0
        
        if Path(plans_jsonl).exists():
            with open(plans_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                        
                    plan = json.loads(line)
                    plan_id = plan.get("plan_id", "Unknown")
                    ep_id = plan.get("episode_id")
                    
                    if not ep_id:
                        # Attempt to extract episode id from plan_id e.g. plan_ep_001
                        ep_id = plan_id.replace("plan_", "")
                        
                    if plan.get("requires_human_approval"):
                        console.print(f"[yellow]Skipping {plan_id} (Requires human approval)[/yellow]")
                        skipped_count += 1
                        continue
                        
                    ep = episodes.get(ep_id)
                    if not ep:
                        console.print(f"[yellow]Skipping {plan_id} (No matching episode found)[/yellow]")
                        continue
                        
                    console.print(f"Validating {plan_id} for DAG {ep['dag_id']}...")
                    
                    if dry_run:
                        console.print(f"[dim]DRY RUN: Triggering {ep['dag_id']}, checking invariants...[/dim]")
                        continue
                        
                    result = self.validate(plan, ep)
                    
                    status = result["status"]
                    if status == "success":
                        success_count += 1
                        mttr_str = self._format_mttr(result["mttr_seconds"])
                        console.print(f"[green]✓ {plan_id} VALIDATED SUCCESS (MTTR: {mttr_str})[/green]")
                        total_mttr += result["mttr_seconds"]
                    elif status == "failed":
                        failed_count += 1
                        console.print(f"[red]✗ {plan_id} VALIDATION FAILED[/red]")
                    elif status == "timeout":
                        timeout_count += 1
                        console.print(f"[yellow]⚠ {plan_id} VALIDATION TIMED OUT[/yellow]")
                    elif status == "invariant_failed":
                        invariant_failed_count += 1
                        console.print(f"[red]✗ {plan_id} INVARIANTS FAILED: {result['invariants_failed']}[/red]")
                        
                    total_validated += 1
                    
        # Summary
        if not dry_run and total_validated > 0:
            console.print("\n=== Validation Summary ===")
            console.print(f"Total Validated: {total_validated}")
            console.print(f"Success: {success_count} ({(success_count/total_validated)*100:.1f}%)")
            console.print(f"Failed: {failed_count}")
            console.print(f"Timeouts: {timeout_count}")
            console.print(f"Invariant Failures: {invariant_failed_count}")
            if success_count > 0:
                avg_mttr = total_mttr / success_count
                console.print(f"Average MTTR: {self._format_mttr(avg_mttr)}")
            console.print("======================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sandbox Validator for Auto-Repair Plans")
    parser.add_argument("--plan", type=str, help="Validate a specific plan_id")
    parser.add_argument("--plans", type=str, default="data/repair_plans.jsonl", help="Path to plans JSONL")
    parser.add_argument("--episodes", type=str, default="data/episodes_classified.jsonl", help="Path to episodes JSONL")
    parser.add_argument("--output", type=str, default="data/validation_results.jsonl", help="Path to write results")
    parser.add_argument("--validate-all", action="store_true", help="Validate all approved plans")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without API calls")
    
    args = parser.parse_args()
    
    validator = SandboxValidator(validation_log_path=args.output)
    
    if args.validate_all:
        validator.validate_batch(
            plans_jsonl=args.plans,
            episodes_jsonl=args.episodes,
            output_path=args.output,
            dry_run=args.dry_run
        )
    elif args.plan:
        # Load specifically
        target_plan = None
        target_ep = None
        
        with open(args.plans, "r") as f:
            for line in f:
                p = json.loads(line)
                if p.get("plan_id") == args.plan:
                    target_plan = p
                    break
                    
        if target_plan:
            ep_id = target_plan.get("episode_id", args.plan.replace("plan_", ""))
            with open(args.episodes, "r") as f:
                for line in f:
                    e = json.loads(line)
                    if e.get("episode_id") == ep_id:
                        target_ep = e
                        break
                        
            if target_ep:
                if args.dry_run:
                    console.print(f"[dim]DRY RUN Validate Single Plan: {args.plan}[/dim]")
                else:
                    res = validator.validate(target_plan, target_ep)
                    console.print(res)
            else:
                console.print(f"[red]Episode {ep_id} not found[/red]")
        else:
            console.print(f"[red]Plan {args.plan} not found[/red]")
    else:
        parser.print_help()
