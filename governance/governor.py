"""
Governance Layer — Milestone 3: Human Review, Rollback, and Safety Guardrails.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

# Import PatchApplier from patcher package
# We assume the script is run from project root or installed as a package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from patcher.patch_applier import PatchApplier

console = Console()

class Governor:

    SAFETY_THRESHOLDS = {
        "max_false_repair_rate":   0.20,   # >20% bad repairs → pause auto-patching
        "min_repair_success_rate": 0.60,   # <60% RSR → pause + escalate
        "max_pending_reviews":     10,     # >10 queued → alert operator
    }

    def __init__(
        self,
        project_root: str = ".",
        plans_path: str = "data/repair_plans.jsonl",
        validation_path: str = "data/validation_results.jsonl",
        audit_log_path: str = "data/audit_log.jsonl",
        governance_log_path: str = "data/governance_log.jsonl",
        review_queue_path: str = "data/review_queue.jsonl",
    ) -> None:
        """
        Load all data paths from .env via python-dotenv.
        Create any missing output directories.
        """
        load_dotenv()
        self.project_root = Path(os.getenv("PROJECT_ROOT", project_root)).resolve()
        self.plans_path = Path(os.getenv("REPAIR_PLANS_PATH", plans_path))
        self.validation_path = Path(os.getenv("VALIDATION_RESULTS_PATH", validation_path))
        self.audit_log_path = Path(os.getenv("AUDIT_LOG_PATH", audit_log_path))
        self.governance_log_path = Path(os.getenv("GOVERNANCE_LOG_PATH", governance_log_path))
        self.review_queue_path = Path(os.getenv("REVIEW_QUEUE_PATH", review_queue_path))

        # Create missing output directories
        self.governance_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.review_queue_path.parent.mkdir(parents=True, exist_ok=True)

    # ── HUMAN REVIEW QUEUE ─────────────────────────────────────────────────

    def build_review_queue(self) -> list[dict]:
        """
        Scan data/repair_plans.jsonl for all plans where
        requires_human_approval=True AND the plan has not yet been reviewed.
        """
        plans = self._load_jsonl(str(self.plans_path))
        decisions = self._load_jsonl(str(self.governance_log_path))
        
        # Track which plans already have a decision
        reviewed_plan_ids = {d["plan_id"] for d in decisions if "plan_id" in d and d.get("action") in ["approved", "rejected"]}
        
        pending_queue = []
        for plan in plans:
            if plan.get("requires_human_approval") and plan["plan_id"] not in reviewed_plan_ids:
                entry = {
                    "queue_id": f"q_{plan['plan_id']}",
                    "plan_id": plan["plan_id"],
                    "episode_id": plan.get("episode_id", plan["plan_id"].replace("plan_", "")),
                    "dag_id": plan.get("dag_id", "unknown"), # Often encoded in plan or episode
                    "failure_class": plan.get("failure_class", "unknown"),
                    "confidence": plan.get("confidence", 0.0),
                    "repair_actions": plan.get("repair_actions", []),
                    "reasoning": plan.get("reasoning", ""),
                    "queued_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending"
                }
                pending_queue.append(entry)
        
        # Overwrite queue file with current pending items (as per implementation rules of "Management")
        # Actually, instructions say "Write each pending plan... to review_queue.jsonl"
        # We'll just overwrite it to keep it as a 'live' queue.
        with open(self.review_queue_path, "w", encoding="utf-8") as f:
            for entry in pending_queue:
                f.write(json.dumps(entry) + "\n")
        
        return pending_queue

    def show_review_queue(self) -> None:
        """
        Print the current review queue as a rich table.
        """
        queue = self._load_jsonl(str(self.review_queue_path))
        if not queue:
            console.print("[yellow]Review queue is empty.[/yellow]")
            return

        table = Table(title="Human Review Queue")
        table.add_column("Queue ID", style="cyan")
        table.add_column("Plan ID", style="magenta")
        table.add_column("DAG ID", style="blue")
        table.add_column("Failure Class", style="yellow")
        table.add_column("Conf.", justify="right")
        table.add_column("Actions", style="green")
        table.add_column("Queued At", style="dim")

        for item in queue:
            conf = item.get("confidence", 0.0)
            row_style = "white"
            if conf < 0.3:
                row_style = "red"
            elif conf < 0.5:
                row_style = "yellow"
            
            actions_summary = ", ".join([f"{a['operator']}({a.get('param', '')})" for a in item.get("repair_actions", [])])
            
            table.add_row(
                item["queue_id"],
                item["plan_id"],
                item["dag_id"],
                item["failure_class"],
                f"{conf:.2f}",
                actions_summary[:30] + ("..." if len(actions_summary) > 30 else ""),
                item["queued_at"][:19].replace("T", " "),
                style=row_style
            )

        console.print(table)
        console.print(f"[bold]Total Pending: {len(queue)}[/bold]")

    def approve(self, plan_id: str, reviewer: str = "human") -> dict:
        """
        Approve a queued plan.
        """
        queue = self._load_jsonl(str(self.review_queue_path))
        target_entry = next((item for item in queue if item["plan_id"] == plan_id or item["queue_id"] == plan_id), None)
        
        if not target_entry:
            raise ValueError(f"Plan ID {plan_id} not found in review queue.")
        if target_entry["status"] != "pending":
            raise ValueError(f"Plan {plan_id} is already in status '{target_entry['status']}'")

        # 1. Trigger Patch Applier
        # We need the full plan from repair_plans.jsonl
        plans = self._load_jsonl(str(self.plans_path))
        full_plan = next((p for p in plans if p["plan_id"] == target_entry["plan_id"]), None)
        if not full_plan:
            raise ValueError(f"Full plan for {target_entry['plan_id']} not found in repair_plans.jsonl")

        # Create a copy and bypass the human approval check for the applier
        applier_plan = full_plan.copy()
        applier_plan["requires_human_approval"] = False 
        
        applier = PatchApplier(project_root=str(self.project_root), audit_log_path=str(self.audit_log_path))
        patch_result = applier.apply(applier_plan)

        # 2. Write governance decision record
        decision = {
            "decision_id": f"gov_{target_entry['plan_id']}",
            "plan_id": target_entry["plan_id"],
            "action": "approved",
            "reviewer": reviewer,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "patch_result": patch_result,
            "threshold_check": self._check_thresholds()
        }
        self._append_jsonl(str(self.governance_log_path), decision)

        # 3. Update queue status
        # We update the file by reading all entries and rewriting
        updated_queue = []
        for item in queue:
            if item["plan_id"] == target_entry["plan_id"]:
                item["status"] = "approved"
            updated_queue.append(item)
        
        with open(self.review_queue_path, "w", encoding="utf-8") as f:
            for item in updated_queue:
                f.write(json.dumps(item) + "\n")

        console.print(f"[green]Plan {target_entry['plan_id']} APPROVED by {reviewer}. Patch applied with commit: {patch_result.get('git_commit_hash', 'N/A')}[/green]")
        return decision

    def reject(self, plan_id: str, reason: str, reviewer: str = "human") -> dict:
        """
        Reject a queued plan.
        """
        queue = self._load_jsonl(str(self.review_queue_path))
        target_entry = next((item for item in queue if item["plan_id"] == plan_id or item["queue_id"] == plan_id), None)
        
        if not target_entry:
            raise ValueError(f"Plan ID {plan_id} not found in review queue.")

        decision = {
            "decision_id": f"gov_{target_entry['plan_id']}",
            "plan_id": target_entry["plan_id"],
            "action": "rejected",
            "reason": reason,
            "reviewer": reviewer,
            "decided_at": datetime.now(timezone.utc).isoformat()
        }
        self._append_jsonl(str(self.governance_log_path), decision)

        # Update queue status
        updated_queue = []
        for item in queue:
            if item["plan_id"] == target_entry["plan_id"]:
                item["status"] = "rejected"
            updated_queue.append(item)
        
        with open(self.review_queue_path, "w", encoding="utf-8") as f:
            for item in updated_queue:
                f.write(json.dumps(item) + "\n")

        console.print(f"[red]Plan {target_entry['plan_id']} REJECTED by {reviewer}. Reason: {reason}[/red]")
        return decision

    # ── AUDIT TRAIL ────────────────────────────────────────────────────────

    def show_audit_trail(
        self,
        limit: int = 20,
        filter_dag: str | None = None,
        filter_status: str | None = None,
    ) -> None:
        """
        Read and merge all logs into a unified timeline.
        """
        audit_logs = self._load_jsonl(str(self.audit_log_path))
        val_results = self._load_jsonl(str(self.validation_path))
        gov_logs = self._load_jsonl(str(self.governance_log_path))

        events = []

        for log in audit_logs:
            action = log.get("status")
            events.append({
                "timestamp": log.get("applied_at", ""),
                "event_type": "patch_applied" if action != "rejected" else "patch_rejected",
                "plan_id": log.get("plan_id", ""),
                "dag_id": log.get("dag_id", "unknown"),
                "status": action,
                "details": f"Commit: {log.get('git_commit_hash', 'N/A')}"
            })

        for res in val_results:
            events.append({
                "timestamp": res.get("validated_at", ""),
                "event_type": "validated",
                "plan_id": res.get("plan_id", ""),
                "dag_id": res.get("dag_id", ""),
                "status": res.get("status", ""),
                "details": f"Inv Passed: {len(res.get('invariants_passed', []))}, Failed: {len(res.get('invariants_failed', []))}"
            })

        for gov in gov_logs:
            action = gov.get("action")
            if action in ["approved", "rejected"]:
                details = f"Reviewer: {gov.get('reviewer', 'N/A')}"
                if action == "rejected":
                    details += f" | Reason: {gov.get('reason', 'N/A')}"
                
                events.append({
                    "timestamp": gov.get("decided_at", ""),
                    "event_type": f"gov_{action}",
                    "plan_id": gov.get("plan_id", ""),
                    "dag_id": "N/A",
                    "status": action,
                    "details": details
                })

        # Sort by timestamp
        events.sort(key=lambda x: x["timestamp"], reverse=True)

        table = Table(title="Unified Audit Trail")
        table.add_column("Timestamp", style="dim")
        table.add_column("Event Type", style="cyan")
        table.add_column("Plan ID", style="magenta")
        table.add_column("DAG ID", style="blue")
        table.add_column("Status")
        table.add_column("Details", style="italic")

        filtered_count = 0
        for e in events:
            if filter_dag and filter_dag != e["dag_id"]: continue
            if filter_status and filter_status != e["status"]: continue
            
            status_color = "white"
            s = e["status"].lower()
            if s in ["applied", "success", "approved"]: status_color = "green"
            elif s in ["rejected", "failed"]: status_color = "red"
            elif s in ["pending", "timeout"]: status_color = "yellow"

            table.add_row(
                e["timestamp"][:19].replace("T", " "),
                e["event_type"],
                e["plan_id"],
                e["dag_id"],
                f"[{status_color}]{e['status']}[/{status_color}]",
                e["details"]
            )
            filtered_count += 1
            if filtered_count >= limit: break

        console.print(table)

    def export_audit_report(self, output_path: str = "data/audit_report.md") -> None:
        """
        Write a Markdown audit report.
        """
        audit_logs = self._load_jsonl(str(self.audit_log_path))
        val_results = self._load_jsonl(str(self.validation_path))
        gov_logs = self._load_jsonl(str(self.governance_log_path))

        total_plans = len({l["plan_id"] for l in audit_logs})
        auto_applied = len([l for l in audit_logs if l.get("status") == "applied" and not any(g.get("plan_id") == l["plan_id"] for g in gov_logs)])
        human_reviewed = len([g for g in gov_logs if g.get("action") in ["approved", "rejected"]])
        approvals = len([g for g in gov_logs if g.get("action") == "approved"])
        rejections = len([g for g in gov_logs if g.get("action") == "rejected"])
        val_success = len([v for v in val_results if v.get("status") == "success"])
        total_val = len(val_results)
        val_rate = (val_success / total_val * 100) if total_val > 0 else 0
        
        rollbacks = [g for g in gov_logs if g.get("action") == "rolled_back"]
        breaches = [g for g in gov_logs if g.get("action") == "threshold_breach"]

        report = f"""# Self-Healing AI Audit Report
Generated at: {datetime.now(timezone.utc).isoformat()}

## Summary Metrics
- **Total Plans Processed**: {total_plans}
- **Auto-Applied Plans**: {auto_applied}
- **Human-Reviewed Plans**: {human_reviewed}
  - Approvals: {approvals}
  - Rejections: {rejections}
- **Validation Success Rate**: {val_rate:.1f}% ({val_success}/{total_val})

## Rollbacks Performed
{chr(10).join([f"- Plan {r['plan_id']} (Commit: {r['reverted_commit'][:7]}) at {r['rolled_back_at']}" for r in rollbacks]) if rollbacks else "No rollbacks performed."}

## Safety Threshold Breaches
{chr(10).join([f"- Breach: {b.get('metrics', {}).get('breaches')} at {b.get('timestamp')}" for b in breaches]) if breaches else "No safety breaches detected."}
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        console.print(f"[green]Audit report exported to {output_path}[/green]")

    # ── GIT ROLLBACK ───────────────────────────────────────────────────────

    def rollback(self, plan_id: str, dry_run: bool = False) -> dict:
        """
        Revert the Git commit associated with a plan_id.
        """
        audit_logs = self._load_jsonl(str(self.audit_log_path))
        target_log = next((l for l in audit_logs if l["plan_id"] == plan_id), None)
        
        if not target_log:
            # Maybe look in gov_logs for approval results
            gov_logs = self._load_jsonl(str(self.governance_log_path))
            target_gov = next((g for g in gov_logs if g["plan_id"] == plan_id and "patch_result" in g), None)
            if target_gov:
                commit_hash = target_gov["patch_result"].get("git_commit_hash")
            else:
                raise ValueError(f"Plan ID {plan_id} not found in audit logs.")
        else:
            commit_hash = target_log.get("git_commit_hash")

        if not commit_hash:
            raise ValueError(f"No git commit hash found for plan {plan_id}.")

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would revert commit {commit_hash} for plan {plan_id}[/yellow]")
            new_hash = "DRY_RUN_HASH"
        else:
            new_hash = self._git_revert(commit_hash)

        record = {
            "decision_id": f"rollback_{plan_id}",
            "plan_id": plan_id,
            "action": "rolled_back",
            "reverted_commit": commit_hash,
            "new_commit": new_hash,
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run
        }
        
        if not dry_run:
            self._append_jsonl(str(self.governance_log_path), record)
            console.print(f"[bold green]Commit {commit_hash[:7]} rolled back! New commit: {new_hash[:7]}[/bold green]")
        
        return record

    def list_rollbackable(self) -> None:
        """
        Print a rich table of all applied patches that can be rolled back.
        """
        audit_logs = self._load_jsonl(str(self.audit_log_path))
        gov_logs = self._load_jsonl(str(self.governance_log_path))
        
        rolled_back_ids = {g["plan_id"] for g in gov_logs if g.get("action") == "rolled_back"}
        
        table = Table(title="Rollbackable Patches")
        table.add_column("Plan ID", style="magenta")
        table.add_column("DAG ID", style="blue")
        table.add_column("Failure Class", style="yellow")
        table.add_column("Applied At", style="dim")
        table.add_column("Commit Hash", style="cyan")
        table.add_column("Status")

        for l in audit_logs:
            pid = l["plan_id"]
            if pid in rolled_back_ids: continue
            if not l.get("git_commit_hash"): continue
            
            table.add_row(
                pid,
                l.get("dag_id", "unknown"),
                l.get("failure_class", "unknown"),
                l.get("applied_at", "")[:16].replace("T", " "),
                l.get("git_commit_hash", "")[:7],
                l.get("status", "")
            )
        
        console.print(table)

    # ── SAFETY THRESHOLDS ──────────────────────────────────────────────────

    def _check_thresholds(self) -> dict:
        """
        Compute current metrics and compare against SAFETY_THRESHOLDS.
        """
        val_results = self._load_jsonl(str(self.validation_path))
        queue = self._load_jsonl(str(self.review_queue_path))
        
        total_val = len(val_results)
        success_count = len([v for v in val_results if v.get("status") == "success"])
        inv_failed_count = len([v for v in val_results if v.get("status") == "invariant_failed"])
        pending_reviews = len([q for q in queue if q.get("status") == "pending"])
        
        rsr = (success_count / total_val) if total_val > 0 else 1.0
        frr = (inv_failed_count / total_val) if total_val > 0 else 0.0
        
        breaches = []
        if frr > self.SAFETY_THRESHOLDS["max_false_repair_rate"]:
            breaches.append("max_false_repair_rate")
        if rsr < self.SAFETY_THRESHOLDS["min_repair_success_rate"]:
            breaches.append("min_repair_success_rate")
        if pending_reviews > self.SAFETY_THRESHOLDS["max_pending_reviews"]:
            breaches.append("max_pending_reviews")
            
        auto_patch_paused = len(breaches) > 0
        
        result = {
            "repair_success_rate": rsr,
            "false_repair_rate": frr,
            "pending_reviews": pending_reviews,
            "breaches": breaches,
            "auto_patch_paused": auto_patch_paused
        }
        
        if auto_patch_paused:
            self._pause_auto_patching(f"Thresholds breached: {', '.join(breaches)}")
            # Log the breach
            self._append_jsonl(str(self.governance_log_path), {
                "action": "threshold_breach",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": result
            })

        return result

    def _pause_auto_patching(self, reason: str) -> None:
        """
        Signal to the Patch Applier to stop applying patches.
        """
        console.print(Panel(f"[bold red]AUTO-PATCHING PAUSED[/bold red]\nReason: {reason}", title="Safety Guardrail", border_style="red"))
        # Persistent state could be a file or env var change. We'll log it for now.
        self._append_jsonl(str(self.governance_log_path), {
            "action": "auto_patch_paused",
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def resume(self) -> None:
        """
        Resume auto-patching from CLI.
        """
        self._append_jsonl(str(self.governance_log_path), {
            "action": "auto_patch_resumed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        console.print("[bold green]Auto-patching resumed.[/bold green]")

    # ── INTERNAL HELPERS ───────────────────────────────────────────────────

    def _load_jsonl(self, path: str) -> list[dict]:
        if not os.path.exists(path): return []
        data = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except: pass
        return data

    def _append_jsonl(self, path: str, record: dict) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()

    def _git_revert(self, commit_hash: str) -> str:
        if not (self.project_root / ".git").exists():
            raise RuntimeError("Project is not a Git repository.")
        
        # Git revert -n --no-edit ensures no editor opens
        res = subprocess.run(["git", "revert", commit_hash, "--no-edit"], cwd=self.project_root, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Git revert failed:\n{res.stderr}")
        
        # Get the new hash
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.project_root, capture_output=True, text=True)
        return res.stdout.strip()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Governor: AI Governance Layer for Workflow Self-Healing")
    parser.add_argument("--queue", action="store_true", help="Show pending human review queue")
    parser.add_argument("--build-queue", action="store_true", help="Rebuild the review queue from plans")
    parser.add_argument("--approve", type=str, nargs='?', const="", help="Approve a plan by ID")
    parser.add_argument("--reject", type=str, nargs='?', const="", help="Reject a plan by ID")
    parser.add_argument("--reason", type=str, help="Reason for rejection")
    parser.add_argument("--reviewer", type=str, default="human", help="Reviewer name")
    parser.add_argument("--audit", action="store_true", help="Show full audit trail")
    parser.add_argument("--limit", type=int, default=20, help="Audit trail entries limit")
    parser.add_argument("--dag", type=str, help="Filter audit by DAG ID")
    parser.add_argument("--rollback", type=str, nargs='?', const="", help="Rollback a patch by Plan ID")
    parser.add_argument("--dry-run", action="store_true", help="Dry run for rollback")
    parser.add_argument("--list-rollbackable", action="store_true", help="List all rollbackable patches")
    parser.add_argument("--check-thresholds", action="store_true", help="Manually check safety thresholds")
    parser.add_argument("--export-report", action="store_true", help="Export Markdown audit report")
    parser.add_argument("--resume", action="store_true", help="Resume auto-patching")

    args = parser.parse_args()
    gov = Governor()

    if args.build_queue:
        q = gov.build_review_queue()
        console.print(f"[bold green]Queue built with {len(q)} entries.[/bold green]")
    
    if args.queue:
        gov.show_review_queue()
    
    elif args.approve is not None or "approve" in sys.argv:
        plan_id = args.approve
        if not plan_id:
            gov.show_review_queue()
            plan_id = Prompt.ask("Enter Plan ID or Queue ID to [bold green]APPROVE[/bold green]")
        if plan_id:
            gov.approve(plan_id, args.reviewer)
    
    elif args.reject is not None or "reject" in sys.argv:
        plan_id = args.reject
        if not plan_id:
            gov.show_review_queue()
            plan_id = Prompt.ask("Enter Plan ID or Queue ID to [bold red]REJECT[/bold bold red]")
        
        if plan_id:
            reason = args.reason
            if not reason:
                reason = Prompt.ask("Enter rejection reason")
            gov.reject(plan_id, reason, args.reviewer)
    
    elif args.audit:
        gov.show_audit_trail(limit=args.limit, filter_dag=args.dag)
    
    elif args.rollback:
        gov.rollback(args.rollback, dry_run=args.dry_run)
    
    elif args.list_rollbackable:
        gov.list_rollbackable()
    
    elif args.check_thresholds:
        res = gov._check_thresholds()
        import pprint
        console.print(Panel(pprint.pformat(res), title="Threshold Check Results"))
    
    elif args.export_report:
        gov.export_audit_report()
    
    elif args.resume:
        gov.resume()
    
    else:
        parser.print_help()
