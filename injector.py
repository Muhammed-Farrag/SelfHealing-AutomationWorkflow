"""
Failure Injection Library for the Self-Healing Workflow AI.

Provides a FailureInjector class that can inject 5 different failure types
into Airflow DAGs by manipulating environment variable overrides. This allows
the system to create controlled failure episodes for training the classifier.

Usage:
    python -m failure_injection.injector inject timeout http_dag
    python -m failure_injection.injector list-types
    python -m failure_injection.injector reset
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar


# Default environment values (used when resetting)
DEFAULT_ENV: dict[str, str] = {
    "API_URL": "https://httpbin.org/json",
    "API_TIMEOUT": "30",
    "API_RETRIES": "3",
    "DB_PATH": "/tmp/sample.db",
    "TARGET_COLUMN": "id",
    "INPUT_FILE_PATH": "/tmp/input.txt",
    "OUTPUT_FILE_PATH": "/tmp/file_output.txt",
}

# Project root directory
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


class FailureInjector:
    """Injects controlled failures into Airflow DAGs via environment overrides.

    Each failure type maps to a specific DAG and set of environment variable
    overrides that will cause the DAG to fail in a predictable way.

    Attributes:
        FAILURE_CONFIGS: Mapping of failure_type → configuration dict.
    """

    FAILURE_CONFIGS: ClassVar[dict[str, dict[str, Any]]] = {
        "timeout": {
            "target_dag": "http_dag",
            "env_overrides": {
                "API_URL": "https://httpbin.org/delay/10",
                "API_TIMEOUT": "1",
                "API_RETRIES": "1",
            },
            "expected_error": "requests.exceptions.ReadTimeout",
            "signature_tokens": ["ReadTimeout", "timeout", "HTTPSConnectionPool"],
            "failing_task": "extract_api",
        },
        "missing_file": {
            "target_dag": "file_dag",
            "env_overrides": {"INPUT_FILE_PATH": "/nonexistent/path/data.csv"},
            "expected_error": "FileNotFoundError",
            "signature_tokens": ["FileNotFoundError", "No such file", "nonexistent"],
            "failing_task": "read_file",
        },
        "http_error": {
            "target_dag": "http_dag",
            "env_overrides": {"API_URL": "https://httpbin.org/status/404"},
            "expected_error": "HTTPError 404",
            "signature_tokens": ["HTTPError", "404", "Client Error"],
            "failing_task": "extract_api",
        },
        "missing_column": {
            "target_dag": "db_dag",
            "env_overrides": {"TARGET_COLUMN": "nonexistent_column"},
            "expected_error": "KeyError",
            "signature_tokens": ["KeyError", "nonexistent_column", "column"],
            "failing_task": "validate",
        },
        "missing_db": {
            "target_dag": "db_dag",
            "env_overrides": {"DB_PATH": "/tmp/nonexistent.db"},
            "expected_error": "OperationalError",
            "signature_tokens": ["OperationalError", "unable to open", "database"],
            "failing_task": "read_table",
        },
    }

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the FailureInjector.

        Args:
            project_root: Root directory of the project. Defaults to the
                          parent of the failure_injection package.
        """
        self.project_root: Path = project_root or PROJECT_ROOT
        self.inject_env_path: Path = self.project_root / ".env.inject"
        self.state_path: Path = self.project_root / "injection_state.json"

    def inject(self, failure_type: str, target_dag: str) -> dict[str, Any]:
        """Inject a failure by writing environment overrides.

        Creates a .env.inject file with the overridden environment variables
        and writes an injection_state.json file recording the injection.

        Args:
            failure_type: One of the 5 supported failure types.
            target_dag: The DAG ID to target (validated against config).

        Returns:
            The injection config dict with metadata.

        Raises:
            ValueError: If failure_type is not supported or target_dag
                        doesn't match the failure type's expected DAG.
        """
        if failure_type not in self.FAILURE_CONFIGS:
            raise ValueError(
                f"Unknown failure type: '{failure_type}'. "
                f"Supported types: {self.list_types()}"
            )

        config: dict[str, Any] = self.FAILURE_CONFIGS[failure_type]
        expected_dag: str = config["target_dag"]

        if target_dag != expected_dag:
            raise ValueError(
                f"Failure type '{failure_type}' targets DAG '{expected_dag}', "
                f"but '{target_dag}' was specified."
            )

        env_overrides: dict[str, str] = config["env_overrides"]

        # Write .env.inject file
        with open(self.inject_env_path, "w", encoding="utf-8") as f:
            for key, value in env_overrides.items():
                f.write(f"{key}={value}\n")

        # Build injection state
        injection_state: dict[str, Any] = {
            "failure_type": failure_type,
            "target_dag": target_dag,
            "injected_at": datetime.now(timezone.utc).isoformat(),
            "env_overrides": env_overrides,
            "signature_tokens": config["signature_tokens"],
            "expected_error": config["expected_error"],
            "failing_task": config["failing_task"],
        }

        # Write injection_state.json
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(injection_state, f, indent=2)

        return injection_state

    def reset(self) -> None:
        """Clear all injections and restore default environment values.

        Removes the .env.inject file and injection_state.json, and writes
        the default environment values back.
        """
        # Remove injection files
        if self.inject_env_path.exists():
            self.inject_env_path.unlink()

        if self.state_path.exists():
            self.state_path.unlink()

        # Write defaults to .env.inject (clean state)
        with open(self.inject_env_path, "w", encoding="utf-8") as f:
            for key, value in DEFAULT_ENV.items():
                f.write(f"{key}={value}\n")

    def get_state(self) -> dict[str, Any] | None:
        """Read the current injection state, if any.

        Returns:
            The injection state dict, or None if no injection is active.
        """
        if not self.state_path.exists():
            return None
        with open(self.state_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_failing_task(self, failure_type: str) -> str:
        """Get the task_id that is expected to fail for a given failure type.

        Args:
            failure_type: One of the 5 supported failure types.

        Returns:
            The task_id string.

        Raises:
            ValueError: If failure_type is not supported.
        """
        if failure_type not in self.FAILURE_CONFIGS:
            raise ValueError(f"Unknown failure type: '{failure_type}'")
        return self.FAILURE_CONFIGS[failure_type]["failing_task"]

    @classmethod
    def list_types(cls) -> list[str]:
        """Return the list of supported failure types.

        Returns:
            List of 5 failure type name strings.
        """
        return list(cls.FAILURE_CONFIGS.keys())


def main() -> None:
    """CLI entry point for the failure injector.

    Usage:
        python -m failure_injection.injector inject <failure_type> <target_dag>
        python -m failure_injection.injector list-types
        python -m failure_injection.injector reset
    """
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m failure_injection.injector inject <type> <dag>")
        print("  python -m failure_injection.injector list-types")
        print("  python -m failure_injection.injector reset")
        sys.exit(1)

    command: str = sys.argv[1]
    injector = FailureInjector()

    if command == "list-types":
        types: list[str] = FailureInjector.list_types()
        print("Supported failure types:")
        for ft in types:
            config = FailureInjector.FAILURE_CONFIGS[ft]
            print(f"  • {ft:20s} → DAG: {config['target_dag']}")
        sys.exit(0)

    elif command == "inject":
        if len(sys.argv) < 4:
            print("Usage: python -m failure_injection.injector inject <type> <dag>")
            sys.exit(1)
        failure_type: str = sys.argv[2]
        target_dag: str = sys.argv[3]
        try:
            state: dict[str, Any] = injector.inject(failure_type, target_dag)
            print(f"✓ Injected '{failure_type}' into '{target_dag}'")
            print(json.dumps(state, indent=2))
        except ValueError as e:
            print(f"✗ Error: {e}")
            sys.exit(1)

    elif command == "reset":
        injector.reset()
        print("✓ All injections cleared, defaults restored.")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
