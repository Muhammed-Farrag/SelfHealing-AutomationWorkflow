"""
Episode Generator for the Self-Healing Workflow AI.

Generates 60 failure episodes (5 failure types × 12 seeds) by:
1. Injecting failures via the FailureInjector
2. Triggering target DAGs via the Airflow REST API
3. Polling until terminal state
4. Collecting task logs
5. Writing JSONL records to data/episodes_raw.jsonl

Usage:
    python -m episode_generator.generate_episodes
    python -m episode_generator.generate_episodes --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path for imports
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from failure_injection.injector import FailureInjector  # noqa: E402

# ─── Configuration constants ────────────────────────────────────────────────
AIRFLOW_BASE_URL: str = os.environ.get("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER: str = os.environ.get("AIRFLOW_USER", "airflow")
AIRFLOW_PASSWORD: str = os.environ.get("AIRFLOW_PASSWORD", "airflow")
NUM_SEEDS: int = 12
MAX_WAIT_SECONDS: int = 120
POLL_INTERVAL: int = 5
MAX_LOG_EXCERPT: int = 500
API_RETRY_ATTEMPTS: int = 3
API_RETRY_DELAY: int = 2

OUTPUT_DIR: Path = PROJECT_ROOT / "data"
OUTPUT_FILE: Path = OUTPUT_DIR / "episodes_raw.jsonl"


def airflow_api(
    method: str,
    endpoint: str,
    json_data: dict[str, Any] | None = None,
    retries: int = API_RETRY_ATTEMPTS,
) -> requests.Response:
    """Make an authenticated request to the Airflow REST API.

    Retries up to `retries` times on transient failures.

    Args:
        method: HTTP method (GET, POST, etc.).
        endpoint: API endpoint path (e.g., /api/v1/dags).
        json_data: Optional JSON body for POST requests.
        retries: Number of retry attempts.

    Returns:
        The HTTP response object.

    Raises:
        requests.RequestException: If all retries are exhausted.
    """
    url: str = f"{AIRFLOW_BASE_URL}{endpoint}"
    auth = HTTPBasicAuth(AIRFLOW_USER, AIRFLOW_PASSWORD)
    headers: dict[str, str] = {"Content-Type": "application/json"}

    last_exception: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.request(
                method=method,
                url=url,
                json=json_data,
                auth=auth,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_exception = exc
            if attempt < retries:
                print(f"  ⚠ API request failed (attempt {attempt}/{retries}): {exc}")
                time.sleep(API_RETRY_DELAY)
            else:
                raise last_exception  # type: ignore[misc]

    raise last_exception  # type: ignore[misc]


def unpause_dag(dag_id: str) -> None:
    """Unpause a DAG so it can be triggered.

    Args:
        dag_id: The DAG ID to unpause.
    """
    airflow_api("PATCH", f"/api/v1/dags/{dag_id}", json_data={"is_paused": False})
    print(f"  ✓ Unpaused DAG '{dag_id}'")


def trigger_dag(dag_id: str, conf: dict[str, Any] | None = None) -> str:
    """Trigger a DAG run via the Airflow REST API.

    Args:
        dag_id: The DAG ID to trigger.
        conf: Optional configuration dict to pass to the DAG run.

    Returns:
        The run_id of the triggered DAG run.
    """
    payload: dict[str, Any] = {"conf": conf or {}}
    response = airflow_api("POST", f"/api/v1/dags/{dag_id}/dagRuns", json_data=payload)
    data: dict[str, Any] = response.json()
    run_id: str = data["dag_run_id"]
    return run_id


def set_dag_env_vars(env_overrides: dict[str, str]) -> None:
    """Set environment variables for the current process.

    These will be inherited by DAG tasks if running locally, or should
    be passed through to the Airflow worker environment.

    Args:
        env_overrides: Dict of environment variable name → value.
    """
    for key, value in env_overrides.items():
        os.environ[key] = value


def poll_dag_run(
    dag_id: str,
    run_id: str,
    max_wait: int = MAX_WAIT_SECONDS,
    poll_interval: int = POLL_INTERVAL,
) -> dict[str, Any]:
    """Poll a DAG run until it reaches a terminal state.

    Args:
        dag_id: The DAG ID.
        run_id: The run_id to poll.
        max_wait: Maximum seconds to wait.
        poll_interval: Seconds between polls.

    Returns:
        The final DAG run state dict.
    """
    elapsed: int = 0
    while elapsed < max_wait:
        response = airflow_api("GET", f"/api/v1/dags/{dag_id}/dagRuns/{run_id}")
        data: dict[str, Any] = response.json()
        state: str = data.get("state", "unknown")

        if state in ("success", "failed"):
            return data

        time.sleep(poll_interval)
        elapsed += poll_interval

    return {"state": "timeout", "dag_id": dag_id, "run_id": run_id}


def get_task_instances(dag_id: str, run_id: str) -> list[dict[str, Any]]:
    """Get all task instances for a DAG run.

    Args:
        dag_id: The DAG ID.
        run_id: The run_id.

    Returns:
        List of task instance dicts.
    """
    response = airflow_api(
        "GET", f"/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances"
    )
    data: dict[str, Any] = response.json()
    return data.get("task_instances", [])


def get_task_log(
    dag_id: str, run_id: str, task_id: str, try_number: int = 1
) -> str:
    """Fetch the log for a specific task instance.

    First tries the Airflow REST API. If that returns an unreadable log
    (e.g., 'Could not read served logs'), falls back to reading the log
    file directly from the mounted ./logs/ directory.

    Args:
        dag_id: The DAG ID.
        run_id: The run_id.
        task_id: The task ID.
        try_number: The attempt number (default 1).

    Returns:
        The task log text, truncated to MAX_LOG_EXCERPT chars.
    """
    log_text: str = ""

    # Try API first
    try:
        response = airflow_api(
            "GET",
            f"/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{try_number}",
        )
        log_text = response.text
    except requests.RequestException:
        pass

    # If API log is empty or unreadable, try filesystem fallback
    if not log_text or "Could not read served logs" in log_text:
        log_dir: Path = PROJECT_ROOT / "logs" / f"dag_id={dag_id}" / f"run_id={run_id}" / f"task_id={task_id}"
        if log_dir.exists():
            # Find the latest attempt log file
            log_files = sorted(log_dir.glob("attempt=*.log"), reverse=True)
            if log_files:
                try:
                    log_text = log_files[0].read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

    if not log_text:
        return "(log unavailable)"

    # Capture the tail of the log where errors typically appear
    return log_text[-MAX_LOG_EXCERPT:]


def find_error_signature(log_excerpt: str, signature_tokens: list[str]) -> str:
    """Find the first matching signature token in a log excerpt.

    Args:
        log_excerpt: The log text to search.
        signature_tokens: List of tokens to look for.

    Returns:
        The first matched token, or 'unknown' if none match.
    """
    for token in signature_tokens:
        if token.lower() in log_excerpt.lower():
            return token
    return "unknown"


def generate_episode(
    episode_num: int,
    seed: int,
    failure_type: str,
    injector: FailureInjector,
    dry_run: bool = False,
) -> dict[str, Any] | None:
    """Generate a single failure episode.

    Args:
        episode_num: Sequential episode number (1-based).
        seed: Random seed identifier.
        failure_type: The failure type to inject.
        injector: FailureInjector instance.
        dry_run: If True, don't actually trigger DAGs.

    Returns:
        The episode record dict, or None on dry-run.
    """
    config = FailureInjector.FAILURE_CONFIGS[failure_type]
    target_dag: str = config["target_dag"]
    failing_task: str = config["failing_task"]
    signature_tokens: list[str] = config["signature_tokens"]

    episode_id: str = f"ep_{episode_num:03d}"
    triggered_at: str = datetime.now(timezone.utc).isoformat()

    print(f"\n{'='*60}")
    print(f"Episode {episode_id} | seed={seed} | {failure_type} -> {target_dag}")
    print(f"{'='*60}")

    # Inject the failure
    injection_state: dict[str, Any] = injector.inject(failure_type, target_dag)
    env_overrides: dict[str, str] = injection_state["env_overrides"]

    if dry_run:
        print(f"  [DRY RUN] Would inject: {env_overrides}")
        print(f"  [DRY RUN] Would trigger DAG '{target_dag}'")
        print(f"  [DRY RUN] Expected failing task: '{failing_task}'")
        signature_index = min(seed % len(signature_tokens), len(signature_tokens) - 1)
        mock_signature = signature_tokens[signature_index]
        return {
            "episode_id": episode_id,
            "seed": seed,
            "dag_id": target_dag,
            "task_id": failing_task,
            "run_id": f"dry_run_{episode_id}",
            "try_number": 1,
            "failure_type": failure_type,
            "error_signature": mock_signature,
            "failure_class": "",
            "log_excerpt": f"[2026-04-08] ERROR - {mock_signature} occurred during execution.",
            "injected_env": env_overrides,
            "triggered_at": triggered_at,
            "terminal_state": "failed",
            "mttr_start": triggered_at,
        }

    # Unpause and trigger the DAG, passing overrides as dag_run.conf
    try:
        unpause_dag(target_dag)
    except requests.RequestException:
        print(f"  ⚠ DAG '{target_dag}' may already be unpaused, continuing...")

    run_id: str = trigger_dag(target_dag, conf=env_overrides)
    print(f"  ✓ Triggered run: {run_id}")

    # Poll until terminal state
    run_state: dict[str, Any] = poll_dag_run(target_dag, run_id)
    terminal_state: str = run_state.get("state", "unknown")
    print(f"  ✓ Terminal state: {terminal_state}")

    # Get task instances to find the actual failed task and try_number
    actual_failing_task: str = failing_task
    try_number: int = 1
    try:
        task_instances: list[dict[str, Any]] = get_task_instances(target_dag, run_id)
        # First, look for the task that actually failed (state=failed)
        for ti in task_instances:
            if ti.get("state") == "failed":
                actual_failing_task = ti.get("task_id", failing_task)
                tn = ti.get("try_number", 1)
                try_number = max(1, tn)  # Airflow logs API is 1-based
                break
    except requests.RequestException:
        pass

    # Collect the log
    log_excerpt: str = get_task_log(target_dag, run_id, actual_failing_task, try_number)
    error_signature: str = find_error_signature(log_excerpt, signature_tokens)

    # Build the episode record
    episode: dict[str, Any] = {
        "episode_id": episode_id,
        "seed": seed,
        "dag_id": target_dag,
        "task_id": actual_failing_task,
        "run_id": run_id,
        "try_number": try_number,
        "failure_type": failure_type,
        "error_signature": error_signature,
        "failure_class": "",  # To be filled by the classifier
        "log_excerpt": log_excerpt,
        "injected_env": env_overrides,
        "triggered_at": triggered_at,
        "terminal_state": terminal_state,
        "mttr_start": triggered_at,
    }

    # Reset injection after capturing the episode
    injector.reset()

    return episode


def write_episode(episode: dict[str, Any], output_path: Path) -> None:
    """Append a single episode record to a JSONL file.

    Args:
        episode: The episode dict to write.
        output_path: Path to the output JSONL file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(episode, ensure_ascii=False) + "\n")
        f.flush()


def main() -> None:
    """Main entry point for episode generation.

    Generates 60 episodes (5 failure types × 12 seeds) and writes them
    to data/episodes_raw.jsonl.
    """
    parser = argparse.ArgumentParser(
        description="Generate failure episodes for the Self-Healing AI system"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be injected without triggering actual DAG runs",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(OUTPUT_FILE),
        help=f"Output JSONL file path (default: {OUTPUT_FILE})",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    injector = FailureInjector()
    failure_types: list[str] = FailureInjector.list_types()

    print("#" * 70)
    print("      SELF-HEALING WORKFLOW AI — EPISODE GENERATOR (M1)")
    print("#" * 70 + "\n")
    print(f"#  Failure types : {len(failure_types):>3d}                                  #")
    print(f"#  Seeds per type: {NUM_SEEDS:>3d}                                  #")
    print(f"#  Total episodes: {len(failure_types) * NUM_SEEDS:>3d}                                  #")
    print(f"#  Output        : {str(output_path):<40s} #")
    print(f"#  Dry run       : {str(args.dry_run):<40s} #")
    print("#" * 70)

    episode_num: int = 0
    generated_count: int = 0

    for failure_type in failure_types:
        for seed in range(1, NUM_SEEDS + 1):
            episode_num += 1
            episode = generate_episode(
                episode_num=episode_num,
                seed=seed,
                failure_type=failure_type,
                injector=injector,
                dry_run=args.dry_run,
            )

            if episode is not None:
                write_episode(episode, output_path)
                generated_count += 1
                print(f"  ✓ Written episode {episode['episode_id']}")

    print(f"\n{'='*60}")
    if args.dry_run:
        print(f"[DRY RUN] Would generate {episode_num} episodes")
    else:
        print(f"✓ {generated_count} episodes generated → {output_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
