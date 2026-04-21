"""
SQLite Database Pipeline DAG.

Reads from a configurable SQLite database, validates that a target column
exists, and writes the row count to a result file. Configuration is read from
dag_run.conf (passed at trigger time) with fallback to environment variables,
so failures can be injected without modifying DAG code.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


def _get_conf(key: str, default: str, **context: dict) -> str:
    """Get config value from dag_run.conf, falling back to env var.

    Args:
        key: The configuration key to look up.
        default: Default value if not found in conf or env.
        **context: Airflow task context containing dag_run.

    Returns:
        The resolved configuration value.
    """
    dag_run = context.get("dag_run")
    if dag_run and dag_run.conf and key in dag_run.conf:
        return str(dag_run.conf[key])
    return os.environ.get(key, default)


def read_table(**context: dict) -> list[dict]:
    """Read all rows from the configured SQLite database.

    Reads DB_PATH from dag_run.conf or environment variables, connects
    to the SQLite DB, and fetches all rows from the first table found.

    Returns:
        List of rows as dicts.
    """
    db_path: str = _get_conf("DB_PATH", "/tmp/sample.db", **context)

    # Explicitly check file exists — SQLite silently creates empty files
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"OperationalError: unable to open database file: '{db_path}'"
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get the first table name
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
    table_row = cursor.fetchone()
    if table_row is None:
        conn.close()
        raise ValueError(f"No tables found in database at {db_path}")

    table_name: str = table_row[0]
    cursor.execute(f"SELECT * FROM {table_name}")  # noqa: S608
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def validate(**context: dict) -> int:
    """Validate that the target column exists in the fetched data.

    Reads TARGET_COLUMN from dag_run.conf or environment variables,
    checks that the column exists in the first row, and returns the
    row count.

    Returns:
        Number of rows in the dataset.
    """
    ti = context["ti"]
    rows: list[dict] = ti.xcom_pull(task_ids="read_table")
    if rows is None or len(rows) == 0:
        raise ValueError("No data received from read_table task")

    target_column: str = _get_conf("TARGET_COLUMN", "id", **context)
    # Check column existence using the first row's keys
    if target_column not in rows[0]:
        raise KeyError(
            f"Column '{target_column}' not found. "
            f"Available columns: {list(rows[0].keys())}"
        )
    return len(rows)


def write_result(**context: dict) -> str:
    """Write the validated row count to a result file.

    Appends the row count to /tmp/db_result.txt.

    Returns:
        Path of the result file.
    """
    ti = context["ti"]
    row_count: int = ti.xcom_pull(task_ids="validate")
    if row_count is None:
        raise ValueError("No data received from validate task")

    output_path: str = "/tmp/db_result.txt"
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"Row count: {row_count}\n")
    return output_path


# Default arguments for all tasks in this DAG
default_args = {
    "owner": "airflow",
    "retries": 3,
    "execution_timeout": timedelta(seconds=600),
}

with DAG(
    dag_id="db_dag",
    description="SQLite database read-validate-write pipeline",
    default_args=default_args,
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["self-healing", "database"],
) as dag:
    # BEGIN PRECHECKS
    # Precheck tasks can be added here for validation before main pipeline
    /tmp/nonexistent.db
    # END PRECHECKS

    t_read = PythonOperator(
        task_id="read_table",
        python_callable=read_table,
    )

    t_validate = PythonOperator(
        task_id="validate",
        python_callable=validate,
    )

    t_write = PythonOperator(
        task_id="write_result",
        python_callable=write_result,
    )

    t_read >> t_validate >> t_write
