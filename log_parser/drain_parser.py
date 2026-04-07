"""
Drain-style Log Template Parser
================================
Implements a simplified Drain (Fixed-Depth Tree) algorithm for online log
parsing. Drain groups raw log messages into templates by clustering them in a
fixed-depth prefix tree, replacing variable tokens with <*> wildcards to
produce stable event IDs used by the downstream failure classifier.

Reference: He, P. et al. (2017). Drain: An Online Log Parsing Approach with
Fixed Depth Tree. ICWS 2017.

Usage:
    python -m log_parser.drain_parser --log "ReadTimeout: HTTPSConnectionPool..."
    python -m log_parser.drain_parser --file data/episodes_raw.jsonl --out data/parsed_logs.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LogCluster:
    """Represents a group of log messages sharing the same template."""

    cluster_id: str
    template_tokens: list[str]
    size: int = 1

    @property
    def template(self) -> str:
        """Human-readable template string with <*> wildcards."""
        return " ".join(self.template_tokens)

    @property
    def event_id(self) -> str:
        """Stable 8-char hex ID derived from the template (deterministic)."""
        return hashlib.md5(self.template.encode()).hexdigest()[:8]

    def to_dict(self) -> dict:
        """Serialise cluster metadata to a plain dict."""
        return {
            "cluster_id": self.cluster_id,
            "event_id": self.event_id,
            "template": self.template,
            "size": self.size,
        }


@dataclass
class ParseResult:
    """Result returned by DrainParser.parse() for a single log line."""

    raw_log: str
    template: str
    event_id: str
    cluster_id: str
    parameters: list[str]   # variable tokens extracted from the raw line

    def to_dict(self) -> dict:
        """Serialise result to a plain dict (JSON-serialisable)."""
        return {
            "raw_log": self.raw_log,
            "template": self.template,
            "event_id": self.event_id,
            "cluster_id": self.cluster_id,
            "parameters": self.parameters,
        }


@dataclass
class _Node:
    """Internal prefix-tree node used by DrainParser."""

    children: dict[str, "_Node"] = field(default_factory=dict)
    clusters: list[LogCluster] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Drain parser
# ---------------------------------------------------------------------------

class DrainParser:
    """
    Online log parser based on the Drain algorithm.

    The algorithm builds a fixed-depth prefix tree:
      - Depth 1  : log length bucket  (number of tokens)
      - Depth 2  : first token of the log
      - Leaf     : list of LogCluster objects matched by similarity

    Parameters
    ----------
    depth : int
        Depth of the prefix tree (default 4, matching the original paper).
    sim_threshold : float
        Minimum token-overlap ratio to merge a log into an existing cluster
        (default 0.4).
    max_children : int
        Maximum number of children per internal node before falling back to
        a wildcard child (default 100).
    parametrize_numeric : bool
        If True, purely numeric tokens are always treated as variables and
        replaced with <*> before tree lookup (default True).
    """

    # Tokens that are always treated as variable wildcards
    _VARIABLE_RE = re.compile(
        r"""
        (?:                         # any of the following:
            0x[0-9a-fA-F]+         |   # hex number
            \d{4}-\d{2}-\d{2}      |   # date  YYYY-MM-DD
            \d{2}:\d{2}:\d{2}      |   # time  HH:MM:SS
            [\w.-]+@[\w.-]+\.\w+   |   # e-mail
            https?://\S+           |   # URL
            /[\w./\-]+             |   # file path
            \d+                        # plain integer
        )
        """,
        re.VERBOSE,
    )

    _WILDCARD = "<*>"

    def __init__(
        self,
        depth: int = 4,
        sim_threshold: float = 0.4,
        max_children: int = 100,
        parametrize_numeric: bool = True,
    ) -> None:
        """Initialise the Drain parser with tunable hyperparameters."""
        self.depth = max(depth, 2)          # need at least 2 levels
        self.sim_threshold = sim_threshold
        self.max_children = max_children
        self.parametrize_numeric = parametrize_numeric

        self._root: _Node = _Node()
        self._id_counter: int = 0
        self._clusters: dict[str, LogCluster] = {}  # cluster_id → cluster

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, raw_log: str) -> ParseResult:
        """
        Parse a single raw log line and return a ParseResult.

        The log is either assigned to an existing cluster (updating its
        template) or used to create a new cluster.

        Parameters
        ----------
        raw_log : str
            One raw log message (single line).

        Returns
        -------
        ParseResult
            Contains the matched template, stable event_id, cluster_id, and
            the variable tokens extracted from the raw line.
        """
        tokens = self._tokenize(raw_log)
        if not tokens:
            return self._make_result(raw_log, [self._WILDCARD], [], "empty")

        masked = self._mask_variables(tokens) if self.parametrize_numeric else tokens[:]
        cluster = self._tree_search(masked)

        if cluster is None:
            cluster = self._create_cluster(masked)
        else:
            cluster.template_tokens = self._update_template(
                cluster.template_tokens, masked
            )
            cluster.size += 1

        params = self._extract_parameters(cluster.template_tokens, tokens)
        return self._make_result(raw_log, cluster.template_tokens, params, cluster.cluster_id)

    def parse_file(self, path: str | Path) -> list[ParseResult]:
        """
        Parse every line of a plain-text log file.

        Parameters
        ----------
        path : str | Path
            Path to a .log or .txt file.

        Returns
        -------
        list[ParseResult]
            One result per non-empty line.
        """
        results: list[ParseResult] = []
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                results.append(self.parse(line))
        return results

    def parse_jsonl_episodes(
        self,
        jsonl_path: str | Path,
        output_path: str | Path,
        log_field: str = "log_excerpt",
    ) -> list[dict]:
        """
        Read an episodes JSONL file, parse each log_excerpt, and write an
        enriched JSONL file with added fields: template, event_id, parameters.

        Parameters
        ----------
        jsonl_path : str | Path
            Path to data/episodes_raw.jsonl (or episodes_classified.jsonl).
        output_path : str | Path
            Destination path for the enriched JSONL.
        log_field : str
            Field name that contains the log text (default "log_excerpt").

        Returns
        -------
        list[dict]
            Enriched episode records.
        """
        records: list[dict] = []
        with open(jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                log_text = record.get(log_field, "")
                result = self.parse(log_text)
                record["template"]   = result.template
                record["event_id"]   = result.event_id
                record["parameters"] = result.parameters
                records.append(record)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
                fh.flush()

        return records

    @property
    def clusters(self) -> list[LogCluster]:
        """Return all discovered log clusters sorted by size descending."""
        return sorted(self._clusters.values(), key=lambda c: c.size, reverse=True)

    def cluster_summary(self) -> list[dict]:
        """
        Return a list of cluster dicts ordered by frequency (most common first).

        Useful for inspecting discovered templates without touching internals.
        """
        return [c.to_dict() for c in self.clusters]

    # ------------------------------------------------------------------
    # Tree operations
    # ------------------------------------------------------------------

    def _tree_search(self, tokens: list[str]) -> Optional[LogCluster]:
        """
        Navigate the prefix tree to find the best matching cluster.

        Returns the matching LogCluster or None if no suitable cluster exists.
        """
        node = self._root

        # Level 1: length bucket
        length_key = str(len(tokens))
        node = node.children.get(length_key)
        if node is None:
            return None

        # Levels 2 … depth-1: first (depth-2) non-wildcard tokens
        for token in tokens[: self.depth - 2]:
            key = token if token != self._WILDCARD else self._WILDCARD
            child = node.children.get(key) or node.children.get(self._WILDCARD)
            if child is None:
                return None
            node = child

        # Leaf: pick the most-similar cluster
        return self._best_cluster(node.clusters, tokens)

    def _create_cluster(self, tokens: list[str]) -> LogCluster:
        """
        Create a new LogCluster for the given token sequence and insert it
        into the prefix tree.
        """
        self._id_counter += 1
        cluster_id = f"c{self._id_counter:05d}"
        cluster = LogCluster(cluster_id=cluster_id, template_tokens=tokens[:])
        self._clusters[cluster_id] = cluster

        node = self._root

        # Level 1: length bucket
        length_key = str(len(tokens))
        if length_key not in node.children:
            node.children[length_key] = _Node()
        node = node.children[length_key]

        # Levels 2 … depth-1
        for token in tokens[: self.depth - 2]:
            key = token if token != self._WILDCARD else self._WILDCARD
            if len(node.children) >= self.max_children and key not in node.children:
                key = self._WILDCARD
            if key not in node.children:
                node.children[key] = _Node()
            node = node.children[key]

        # Leaf
        node.clusters.append(cluster)
        return cluster

    # ------------------------------------------------------------------
    # Similarity & template update
    # ------------------------------------------------------------------

    def _best_cluster(
        self,
        clusters: list[LogCluster],
        tokens: list[str],
    ) -> Optional[LogCluster]:
        """
        Return the cluster with the highest token-overlap similarity above
        sim_threshold, or None if none qualifies.
        """
        best: Optional[LogCluster] = None
        best_score = -1.0

        for cluster in clusters:
            score = self._similarity(cluster.template_tokens, tokens)
            if score > best_score:
                best_score = score
                best = cluster

        if best_score >= self.sim_threshold:
            return best
        return None

    @staticmethod
    def _similarity(template_tokens: list[str], tokens: list[str]) -> float:
        """
        Token-overlap similarity: fraction of positions where both sequences
        share the same non-wildcard token.
        """
        if len(template_tokens) != len(tokens):
            return 0.0
        matches = sum(
            1
            for t, s in zip(template_tokens, tokens)
            if t != "<*>" and t == s
        )
        return matches / len(template_tokens) if template_tokens else 0.0

    @staticmethod
    def _update_template(
        template_tokens: list[str],
        tokens: list[str],
    ) -> list[str]:
        """
        Merge a new token sequence into an existing template: positions that
        differ become <*> wildcards.
        """
        return [
            t if t == s else "<*>"
            for t, s in zip(template_tokens, tokens)
        ]

    # ------------------------------------------------------------------
    # Tokenisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(log: str) -> list[str]:
        """
        Split a log line into whitespace-delimited tokens, stripping common
        log-level prefixes (INFO, ERROR, WARNING, DEBUG, CRITICAL).
        """
        # Strip leading timestamp + log-level markers
        log = re.sub(
            r"^\[?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\]]*)\]?\s*",
            "",
            log,
        )
        log = re.sub(
            r"^\[?(INFO|ERROR|WARNING|WARN|DEBUG|CRITICAL)\]?\s*",
            "",
            log,
            flags=re.IGNORECASE,
        )
        return log.split()

    def _mask_variables(self, tokens: list[str]) -> list[str]:
        """
        Replace variable-looking tokens (numbers, paths, URLs, …) with <*>
        before tree lookup to improve cluster merging.
        """
        result: list[str] = []
        for token in tokens:
            if self._VARIABLE_RE.fullmatch(token):
                result.append(self._WILDCARD)
            else:
                result.append(token)
        return result

    # ------------------------------------------------------------------
    # Parameter extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_parameters(
        template_tokens: list[str],
        raw_tokens: list[str],
    ) -> list[str]:
        """
        Extract the variable values from a raw log by aligning it with the
        template: positions marked <*> in the template are parameters.
        """
        if len(template_tokens) != len(raw_tokens):
            return []
        return [
            raw
            for tmpl, raw in zip(template_tokens, raw_tokens)
            if tmpl == "<*>"
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_result(
        raw_log: str,
        template_tokens: list[str],
        parameters: list[str],
        cluster_id: str,
    ) -> ParseResult:
        """Construct a ParseResult from its components."""
        template = " ".join(template_tokens)
        event_id = hashlib.md5(template.encode()).hexdigest()[:8]
        return ParseResult(
            raw_log=raw_log,
            template=template,
            event_id=event_id,
            cluster_id=cluster_id,
            parameters=parameters,
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the drain_parser module."""
    p = argparse.ArgumentParser(
        description="Drain-style log template parser for Self-Healing Workflow AI (M2)"
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--log",
        metavar="TEXT",
        help="Parse a single log line passed as a string.",
    )
    group.add_argument(
        "--file",
        metavar="PATH",
        help="Parse a plain-text log file (one log per line).",
    )
    group.add_argument(
        "--episodes",
        metavar="JSONL_PATH",
        help="Enrich an episodes JSONL file with template + event_id fields.",
    )
    p.add_argument(
        "--out",
        metavar="PATH",
        default="data/parsed_logs.jsonl",
        help="Output path for --file or --episodes mode (default: data/parsed_logs.jsonl).",
    )
    p.add_argument(
        "--depth", type=int, default=4,
        help="Drain tree depth (default 4).",
    )
    p.add_argument(
        "--sim", type=float, default=0.4,
        help="Similarity threshold for cluster merging (default 0.4).",
    )
    p.add_argument(
        "--summary", action="store_true",
        help="After parsing, print the discovered cluster summary.",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    """CLI entry point — run with python -m log_parser.drain_parser --help."""
    args = _build_arg_parser().parse_args(argv)
    parser = DrainParser(depth=args.depth, sim_threshold=args.sim)

    if args.log:
        result = parser.parse(args.log)
        print(json.dumps(result.to_dict(), indent=2))

    elif args.file:
        results = parser.parse_file(args.file)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            for r in results:
                fh.write(json.dumps(r.to_dict()) + "\n")
                fh.flush()
        print(f"✓ Parsed {len(results)} lines → {out}")

    elif args.episodes:
        records = parser.parse_jsonl_episodes(args.episodes, args.out)
        print(f"✓ Enriched {len(records)} episodes → {args.out}")

    if args.summary:
        print("\n── Cluster Summary ─────────────────────────────────────────")
        for c in parser.cluster_summary():
            print(
                f"  [{c['event_id']}] size={c['size']:>4}  {c['template'][:80]}"
            )


if __name__ == "__main__":
    main(sys.argv[1:])
