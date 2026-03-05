"""
Initialization script for Airflow workers.

Creates sample data files needed by the DAGs to run successfully in their
default (non-injected) configuration. This script is called on container
startup to ensure the required test fixtures exist.
"""

from __future__ import annotations

import sqlite3
import os


def create_sample_db(db_path: str = "/tmp/sample.db") -> None:
    """Create a sample SQLite database with test data.

    Args:
        db_path: Path where the SQLite database should be created.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sample_data (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            value REAL NOT NULL
        )
    """)
    # Insert sample rows
    sample_rows = [
        (1, "alpha", 10.5),
        (2, "beta", 20.3),
        (3, "gamma", 30.7),
        (4, "delta", 40.1),
        (5, "epsilon", 50.9),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO sample_data (id, name, value) VALUES (?, ?, ?)",
        sample_rows,
    )
    conn.commit()
    conn.close()


def create_sample_input_file(file_path: str = "/tmp/input.txt") -> None:
    """Create a sample input text file for the file_dag.

    Args:
        file_path: Path where the input file should be created.
    """
    with open(file_path, "w", encoding="utf-8") as f:
        for i in range(1, 11):
            f.write(f"Sample line {i}\n")


if __name__ == "__main__":
    create_sample_db()
    create_sample_input_file()
    print("✓ Sample data initialized")
