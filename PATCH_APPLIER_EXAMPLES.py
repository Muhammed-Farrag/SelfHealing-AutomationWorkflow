#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
=============================================================================
COMPLETE END-TO-END EXAMPLE: M2 Pipeline (Patch Applier)
=============================================================================

This example demonstrates the complete flow from a failure episode through
the Patch Applier component (Member 5), including all 5 operators.

Flow:
  Failure Episode -> Parsed Logs -> Repair Plan -> Patch Applier
                                                    ├─ apply() processed
                                                    ├─ audit_log.jsonl
                                                    ├─ Git commits
                                                    └─ .env.inject + dags/*.py

=============================================================================
"""

# Example repair plans that would come from the LLM Repair Planner (Member 4)

REPAIR_PLANS_EXAMPLE = """
{
  "plan_id": "plan_ep_001",
  "episode_id": "ep_001",
  "failure_class": "timeout",
  "confidence": 0.95,
  "reasoning": "HTTP request timeout. Increase execution_timeout from 300s to 600s.",
  "repair_actions": [
    {
      "operator": "set_timeout",
      "dag_id": "http_dag",
      "param": "execution_timeout",
      "value": "600",
      "justification": "Timeout detected at 300s; increase to 600s"
    }
  ],
  "fallback_action": "escalate_to_human",
  "requires_human_approval": false
}

{
  "plan_id": "plan_ep_002",
  "episode_id": "ep_002",
  "failure_class": "missing_env_var",
  "confidence": 0.92,
  "reasoning": "Missing API_KEY environment variable. Set from secrets.",
  "repair_actions": [
    {
      "operator": "set_env",
      "param": "API_KEY",
      "value": "sk-prod-12345abcde",
      "justification": "API authentication required"
    },
    {
      "operator": "set_env",
      "param": "API_TIMEOUT",
      "value": "45",
      "justification": "Sync with application timeout"
    }
  ],
  "fallback_action": "escalate_to_human",
  "requires_human_approval": false
}

{
  "plan_id": "plan_ep_003",
  "episode_id": "ep_003",
  "failure_class": "retry_exceeded",
  "confidence": 0.88,
  "reasoning": "Task failed after 3 retries. Increase retry count to 5.",
  "repair_actions": [
    {
      "operator": "set_retry",
      "dag_id": "db_dag",
      "param": "retries",
      "value": "5",
      "justification": "Transient DB connection issues; allow more retries"
    }
  ],
  "fallback_action": "escalate_to_human",
  "requires_human_approval": false
}

{
  "plan_id": "plan_ep_004",
  "episode_id": "ep_004",
  "failure_class": "path_not_found",
  "confidence": 0.85,
  "reasoning": "Input file path not found. Update INPUT_FILE_PATH.",
  "repair_actions": [
    {
      "operator": "replace_path",
      "param": "INPUT_FILE_PATH",
      "value": "/data/prod/input_files/latest.txt",
      "justification": "Correct path to production data directory"
    },
    {
      "operator": "replace_path",
      "param": "PYTHONPATH",
      "value": "/opt/airflow/dags:/opt/airflow/plugins:/usr/local/lib/python3.10/site-packages",
      "justification": "Include custom modules in Python path"
    }
  ],
  "fallback_action": "escalate_to_human",
  "requires_human_approval": false
}

{
  "plan_id": "plan_ep_005",
  "episode_id": "ep_005",
  "failure_class": "dependency_failure",
  "confidence": 0.80,
  "reasoning": "Add precheck task to validate API availability before main pipeline.",
  "repair_actions": [
    {
      "operator": "add_precheck",
      "dag_id": "http_dag",
      "value": "t_precheck_api = PythonOperator(task_id='precheck_api', python_callable=_check_api_availability)",
      "justification": "Fail fast if API is unavailable"
    }
  ],
  "fallback_action": "escalate_to_human",
  "requires_human_approval": false
}

{
  "plan_id": "plan_ep_006",
  "episode_id": "ep_006",
  "failure_class": "timeout",
  "confidence": 0.70,
  "reasoning": "Complex fix requiring human review - multiple DAGs affected.",
  "repair_actions": [
    {
      "operator": "set_timeout",
      "dag_id": "http_dag",
      "param": "execution_timeout",
      "value": "900",
      "justification": "Long-running queries need 15 min timeout"
    },
    {
      "operator": "set_retry",
      "dag_id": "http_dag",
      "param": "retries",
      "value": "2",
      "justification": "Reduce retries to avoid cascading failures"
    }
  ],
  "fallback_action": "escalate_to_human",
  "requires_human_approval": true
}
"""

# Expected AUDIT LOG OUTPUT

AUDIT_LOG_EXAMPLE = """
{
  "plan_id": "plan_ep_001",
  "episode_id": "ep_001",
  "failure_class": "timeout",
  "status": "applied",
  "applied_at": "2024-04-10T12:34:56.789012",
  "applied_actions": ["set_timeout(execution_timeout=600)"],
  "failed_actions": [],
  "git_commit_hash": "a1b2c3d",
  "dry_run": false,
  "diffs": {
    "dags/http_dag.py": "--- a/dags/http_dag.py\\n+++ b/dags/http_dag.py\\n@@ -1,5 +1,5 @@\\n default_args = {\\n     'execution_timeout': timedelta(seconds=300),\\n-    'execution_timeout': timedelta(seconds=300),\\n+    'execution_timeout': timedelta(seconds=600),\\n }"
  }
}

{
  "plan_id": "plan_ep_002",
  "episode_id": "ep_002",
  "failure_class": "missing_env_var",
  "status": "applied",
  "applied_at": "2024-04-10T12:35:01.234567",
  "applied_actions": ["set_env(API_KEY=sk-prod-12345abcde)", "set_env(API_TIMEOUT=45)"],
  "failed_actions": [],
  "git_commit_hash": "b2c3d4e",
  "dry_run": false,
  "diffs": {
    ".env.inject": "--- a/.env.inject\\n+++ b/.env.inject\\n@@ -0,0 +1,2 @@\\n+API_KEY=sk-prod-12345abcde\\n+API_TIMEOUT=45\\n"
  }
}

{
  "plan_id": "plan_ep_006",
  "episode_id": "ep_006",
  "failure_class": "timeout",
  "status": "rejected",
  "applied_at": "2024-04-10T12:35:10.567890",
  "applied_actions": [],
  "failed_actions": ["All actions rejected"],
  "git_commit_hash": null,
  "dry_run": false,
  "diffs": {},
  "rejection_reason": "requires_human_approval=True"
}
"""

# COMMAND-LINE USAGE EXAMPLES

USAGE_EXAMPLES = """
=== DRY-RUN TESTS ===

# Test a single repair plan without modifying files
python -m patcher.patch_applier --plan-id plan_ep_001 --dry-run
python -m patcher.patch_applier --plan-id plan_ep_002 --dry-run

# Output shows what would be applied (status: "dry_run"):
#   ✓ Applied set_timeout(execution_timeout)
#   [dry_run mode – no files modified]


=== APPLY PATCHES ===

# Apply a single approved repair plan
python -m patcher.patch_applier --plan-id plan_ep_001

# Output shows results:
#   ✓ Applied set_timeout(execution_timeout)
#   ✓ Git commit: a1b2c3d
#   Audit entry logged


# Apply all plans from JSONL file
python -m patcher.patch_applier --apply-all data/repair_plans.jsonl

# Output shows summary:
#   Applied:              4
#   Partial:              0
#   Rejected:             1
#   Pending Human Review: 1


=== VIEW RESULTS ===

# Display audit log in table format
python -m patcher.patch_applier --audit

# Output:
#   ┏━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┓
#   ┃ Plan ID   ┃ Status ┃ Applied┃ Failed ┃ Commit   ┃
#   ┡━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━┩
#   │ plan_..001│applied │   1    │   0    │ a1b2c3d  │
#   │ plan_..002│applied │   2    │   0    │ b2c3d4e  │
#   │ plan_..006│rejected│   0    │   1    │ —        │
#   └───────────┴────────┴────────┴────────┴──────────┘


# View Git commits created by patcher
git log --oneline | grep "auto-repair"

# Output:
#   a1b2c3d auto-repair: plan_ep_001 (timeout)
#   b2c3d4e auto-repair: plan_ep_002 (missing_env_var)
#   c3d4e5f auto-repair: plan_ep_003 (retry_exceeded)
#   d4e5f6g auto-repair: plan_ep_004 (path_not_found)
#   e5f6g7h auto-repair: plan_ep_005 (dependency_failure)


# Inspect a specific patch
git show a1b2c3d

# Output shows unified diff of exact changes:
#   commit a1b2c3d
#   Author: system <airflow@example.com>
#   Date:   Thu Apr 10 12:34:56 2024
#   
#       auto-repair: plan_ep_001 (timeout)
#   
#   diff --git a/dags/http_dag.py b/dags/http_dag.py
#   @@ -1,5 +1,5 @@
#    default_args = {
#        "owner": "airflow",
#   -    "execution_timeout": timedelta(seconds=300),
#   +    "execution_timeout": timedelta(seconds=600),
#    }


=== VIEW MODIFIED FILES ===

# Check current .env.inject settings
cat .env.inject

# Output:
#   API_KEY=sk-prod-12345abcde
#   API_TIMEOUT=45
#   INPUT_FILE_PATH=/data/prod/input_files/latest.txt
#   PYTHONPATH=/opt/airflow/dags:/opt/airflow/plugins:/usr/local/lib/python3.10/site-packages


# Check updated DAG file
grep -A 2 "execution_timeout" dags/http_dag.py

# Output:
#   "execution_timeout": timedelta(seconds=600),


=== ROLLBACK ===

# If a patch was bad, rollback via Git
git revert a1b2c3d

# Or reset to specific commit
git reset --hard <commit-before-patches>
"""

# EXPECTED FILE CHANGES

FILE_CHANGES = """
=== AFTER APPLYING ALL EXAMPLE PLANS ===

.env.inject
───────────
API_KEY=sk-prod-12345abcde
API_TIMEOUT=45
INPUT_FILE_PATH=/data/prod/input_files/latest.txt
PYTHONPATH=/opt/airflow/dags:/opt/airflow/plugins:/usr/local/lib/python3.10/site-packages


dags/http_dag.py
────────────────
default_args = {
    "owner": "airflow",
    "retries": 3,                              # Unchanged (no set_retry plan)
    "execution_timeout": timedelta(seconds=600),  # CHANGED from 300s
}

with DAG(...) as dag:
    # BEGIN PRECHECKS
    t_precheck_api = PythonOperator(...)           # ADDED by add_precheck
    # END PRECHECKS
    
    t_extract = PythonOperator(...)


dags/db_dag.py
──────────────
default_args = {
    "owner": "airflow",
    "retries": 5,                              # CHANGED from 3
    "execution_timeout": timedelta(seconds=600),  # Unchanged
}


dags/file_dag.py
────────────────
# No changes (no plans for file_dag)


audit_log.jsonl
───────────────
{plan_ep_001: applied, changes: http_dag.py timeout}
{plan_ep_002: applied, changes: .env.inject API_KEY, API_TIMEOUT}
{plan_ep_003: applied, changes: db_dag.py retries}
{plan_ep_004: applied, changes: .env.inject INPUT_FILE_PATH, PYTHONPATH}
{plan_ep_005: applied, changes: http_dag.py precheck}
{plan_ep_006: rejected, reason: requires_human_approval=true}
"""

if __name__ == "__main__":
    print(__doc__)
    print("\n" + "="*80)
    print("EXAMPLE REPAIR PLANS (input to Patch Applier)")
    print("="*80)
    print(REPAIR_PLANS_EXAMPLE)
    
    print("\n" + "="*80)
    print("EXPECTED AUDIT LOG (output from Patch Applier)")
    print("="*80)
    print(AUDIT_LOG_EXAMPLE)
    
    print("\n" + "="*80)
    print("COMMAND-LINE USAGE")
    print("="*80)
    print(USAGE_EXAMPLES)
    
    print("\n" + "="*80)
    print("FILE CHANGES AFTER APPLYING PLANS")
    print("="*80)
    print(FILE_CHANGES)
