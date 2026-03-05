"""
Regex-based Failure Classifier for the Self-Healing Workflow AI.

Classifies task log excerpts into one of 5 failure classes (+ unknown fallback)
using ordered regex rules. Can be used as a standalone module or CLI tool.

Usage:
    # Classify a single log excerpt
    python -m classifier.classifier --log "ReadTimeout: HTTPSConnectionPool..."

    # Classify all episodes in a JSONL file
    python -m classifier.classifier --classify-all data/episodes_raw.jsonl

    # Specify custom output path
    python -m classifier.classifier --classify-all data/episodes_raw.jsonl \\
        --output data/episodes_classified.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, ClassVar


class RegexFailureClassifier:
    """Classifies log excerpts into failure classes using regex pattern matching.

    Rules are evaluated in order; the first matching rule determines the class.
    A catch-all 'unknown' rule at the end ensures every log gets classified.

    Attributes:
        RULES: Ordered list of (failure_class, list_of_regex_patterns) tuples.
    """

    RULES: ClassVar[list[tuple[str, list[str]]]] = [
        (
            "timeout",
            [
                "ReadTimeout",
                "TimeoutError",
                "timed out",
                "HTTPSConnectionPool",
                "execution_timeout",
                "ConnectTimeout",
                "ConnectionPool",
            ],
        ),
        (
            "http_error",
            [
                "HTTPError",
                r"4[0-9]{2} Client Error",
                r"5[0-9]{2} Server Error",
                "ConnectionError",
                "NOT FOUND for url",
            ],
        ),
        (
            "missing_file",
            [
                "FileNotFoundError",
                "No such file or directory",
                "cannot open",
                "ENOENT",
                r"Errno 2",
            ],
        ),
        (
            "missing_column",
            [
                "KeyError",
                r"column.*not found",
                r"missing.*column",
                "nonexistent_column",
                "not found.*Available columns",
            ],
        ),
        (
            "missing_db",
            [
                "OperationalError",
                "unable to open database",
                "sqlite3.OperationalError",
                r"database.*not found",
                "No tables found in database",
            ],
        ),
        (
            "unknown",
            [".*"],  # Fallback catch-all
        ),
    ]

    def classify(self, log_excerpt: str) -> dict[str, Any]:
        """Classify a log excerpt into a failure class.

        Evaluates regex rules in order and returns the first match.
        Confidence is always 1.0 for deterministic regex matching.

        Args:
            log_excerpt: The log text to classify.

        Returns:
            A dict with keys: failure_class, matched_rule, confidence.
        """
        for failure_class, patterns in self.RULES:
            for pattern in patterns:
                if re.search(pattern, log_excerpt, re.IGNORECASE):
                    return {
                        "failure_class": failure_class,
                        "matched_rule": pattern,
                        "confidence": 1.0,
                    }

        # Should never reach here due to catch-all, but just in case
        return {
            "failure_class": "unknown",
            "matched_rule": ".*",
            "confidence": 1.0,
        }

    def classify_episodes(self, jsonl_path: str, output_path: str) -> None:
        """Classify all episodes in a JSONL file and write results.

        Reads each episode record, classifies its log_excerpt, fills in
        the failure_class field, and writes to the output file. Prints
        a classification summary table at the end.

        Args:
            jsonl_path: Path to the input JSONL file (episodes_raw.jsonl).
            output_path: Path to the output JSONL file (episodes_classified.jsonl).
        """
        input_file = Path(jsonl_path)
        output_file = Path(output_path)

        if not input_file.exists():
            print(f"✗ Input file not found: {jsonl_path}")
            sys.exit(1)

        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Classification counters
        class_counts: dict[str, int] = {}
        total_count: int = 0

        with open(input_file, "r", encoding="utf-8") as fin, open(
            output_file, "w", encoding="utf-8"
        ) as fout:
            for line in fin:
                line = line.strip()
                if not line:
                    continue

                episode: dict[str, Any] = json.loads(line)
                log_excerpt: str = episode.get("log_excerpt", "")

                # Classify the log excerpt
                result: dict[str, Any] = self.classify(log_excerpt)
                episode["failure_class"] = result["failure_class"]

                # Write classified episode
                fout.write(json.dumps(episode, ensure_ascii=False) + "\n")
                fout.flush()

                # Update counters
                fc: str = result["failure_class"]
                class_counts[fc] = class_counts.get(fc, 0) + 1
                total_count += 1

        # Print summary
        print(f"\n{'='*50}")
        print(f"✓ {total_count} episodes classified → {output_path}")
        print(f"{'='*50}")
        print("\nClassification summary:")
        print(f"  {'Class':<20s} {'Count':>6s}")
        print(f"  {'─'*20} {'─'*6}")
        for fc in [
            "timeout",
            "http_error",
            "missing_file",
            "missing_column",
            "missing_db",
            "unknown",
        ]:
            count: int = class_counts.get(fc, 0)
            if count > 0:
                print(f"  {fc:<20s} {count:>6d} episodes")
        print(f"  {'─'*20} {'─'*6}")
        print(f"  {'TOTAL':<20s} {total_count:>6d} episodes")


def main() -> None:
    """CLI entry point for the failure classifier.

    Supports two modes:
      --log <text>          Classify a single log excerpt
      --classify-all <path> Classify all episodes in a JSONL file
    """
    parser = argparse.ArgumentParser(
        description="Regex-based Failure Classifier for Self-Healing AI"
    )
    parser.add_argument(
        "--log",
        type=str,
        help="Classify a single log excerpt string",
    )
    parser.add_argument(
        "--classify-all",
        type=str,
        metavar="JSONL_PATH",
        help="Classify all episodes in the given JSONL file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for classified JSONL (default: data/episodes_classified.jsonl)",
    )
    args = parser.parse_args()

    classifier = RegexFailureClassifier()

    if args.log:
        result: dict[str, Any] = classifier.classify(args.log)
        print(json.dumps(result, indent=2))

    elif args.classify_all:
        output: str = args.output or str(
            Path(args.classify_all).parent / "episodes_classified.jsonl"
        )
        classifier.classify_episodes(args.classify_all, output)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
