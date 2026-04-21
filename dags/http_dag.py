"""
HTTP API Pipeline DAG.

Extracts data from a configurable HTTP API endpoint, transforms the JSON
response, and loads the result to a local file. Configuration is read from
dag_run.conf (passed at trigger time) with fallback to environment variables,
so failures can be injected without modifying DAG code.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

import requests


# Default arguments for all tasks in this DAG
default_args = {
    "owner": "airflow",
    "retries": 5,
}


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


def extract_api(**context: dict) -> str:
    """Make an HTTP GET request to the configured API URL.

    Reads API_URL, API_TIMEOUT, and API_RETRIES from dag_run.conf or
    environment variables. Pushes the raw response text to XCom.

    Returns:
        The raw HTTP response text.
    """
    url: str = _get_conf("API_URL", "https://httpbin.org/json", **context)
    timeout: int = int(_get_conf("API_TIMEOUT", "30", **context))
    retries: int = int(_get_conf("API_RETRIES", "3", **context))

    last_exception: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_exception = exc
            if attempt < retries:
                continue
            raise last_exception


def transform(**context: dict) -> dict:
    """Parse the raw JSON response from the extract_api task.

    Pulls the raw text from XCom, parses it as JSON, and pushes the
    resulting dict back to XCom.

    Returns:
        Parsed JSON as a Python dict.
    """
    ti = context["ti"]
    raw_text: str = ti.xcom_pull(task_ids="extract_api")
    if raw_text is None:
        raise ValueError("No data received from extract_api task")
    data: dict = json.loads(raw_text)
    return data


def load(**context: dict) -> str:
    """Write the transformed data to an output JSON file.

    Pulls the parsed dict from XCom and writes it to /tmp/output.json.

    Returns:
        Path of the output file.
    """
    ti = context["ti"]
    data: dict = ti.xcom_pull(task_ids="transform")
    if data is None:
        raise ValueError("No data received from transform task")

    output_path: str = "/tmp/output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return output_path


with DAG(
    dag_id="http_dag",
    description="HTTP API extract-transform-load pipeline",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["self-healing", "http"],
) as dag:
    t_extract = PythonOperator(
        task_id="extract_api",
        python_callable=extract_api,
    )

    t_transform = PythonOperator(
        task_id="transform",
        python_callable=transform,
    )

    t_load = PythonOperator(
        task_id="load",
        python_callable=load,
    )

    t_extract >> t_transform >> t_load
