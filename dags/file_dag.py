"""
File Processing Pipeline DAG.

Reads from a configurable input file, counts the number of lines, and writes
the count to a configurable output file. Configuration is read from
dag_run.conf (passed at trigger time) with fallback to environment variables,
so failures can be injected without modifying DAG code.
"""

from __future__ import annotations

import os
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


def read_file(**context: dict) -> str:
    """Read the contents of the configured input file.

    Reads INPUT_FILE_PATH from dag_run.conf or environment variables
    and returns the full file content as a string.

    Returns:
        The raw file content.
    """
    input_path: str = _get_conf("INPUT_FILE_PATH", "/tmp/input.txt", **context)
    with open(input_path, "r", encoding="utf-8") as f:
        content: str = f.read()
    return content


def process(**context: dict) -> int:
    """Count the number of lines in the file content.

    Pulls the file content from XCom and returns the line count.

    Returns:
        Number of lines in the file.
    """
    ti = context["ti"]
    content: str = ti.xcom_pull(task_ids="read_file")
    if content is None:
        raise ValueError("No data received from read_file task")
    line_count: int = len(content.splitlines())
    return line_count


def write_output(**context: dict) -> str:
    """Write the line count to the configured output file.

    Reads OUTPUT_FILE_PATH from dag_run.conf or environment variables
    and writes the line count.

    Returns:
        Path of the output file.
    """
    ti = context["ti"]
    line_count: int = ti.xcom_pull(task_ids="process")
    if line_count is None:
        raise ValueError("No data received from process task")

    output_path: str = _get_conf("OUTPUT_FILE_PATH", "/tmp/file_output.txt", **context)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Line count: {line_count}\n")
    return output_path


# Default arguments for all tasks in this DAG
default_args = {
    "owner": "airflow",
    "retries": 3,
    "execution_timeout": timedelta(seconds=600),
}

with DAG(
    dag_id="file_dag",
    description="File read-process-write pipeline",
    default_args=default_args,
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["self-healing", "file"],
) as dag:
    # BEGIN PRECHECKS
    # Precheck tasks can be added here for validation before main pipeline
    /nonexistent/path/data.csv
    /nonexistent/path/data.csv
    /nonexistent/path/data.csv
    /nonexistent/path/data.csv
    /nonexistent/path/data.csv
    /nonexistent/path/data.csv
    /nonexistent/path/data.csv
    /nonexistent/path/data.csv
    /nonexistent/path/data.csv
    /nonexistent/path/data.csv
    /nonexistent/path/data.csv
    # END PRECHECKS

    t_read = PythonOperator(
        task_id="read_file",
        python_callable=read_file,
    )

    t_process = PythonOperator(
        task_id="process",
        python_callable=process,
    )

    t_write = PythonOperator(
        task_id="write_output",
        python_callable=write_output,
    )

    t_read >> t_process >> t_write
