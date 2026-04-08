"""
LLM Repair Planner — Milestone 2
Self-Healing Automation Workflow AI

Generates constrained, schema-validated JSON repair plans for Apache Airflow
failure episodes using GPT-4o (OpenAI) or Llama 3 (Ollama local fallback).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Load environment variables from .env as early as possible
load_dotenv()

import os  # noqa: E402 – must come after load_dotenv

console = Console()

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------
FAILURE_CLASSES = {
    "missing_env_var",
    "path_not_found",
    "timeout",
    "retry_exceeded",
    "dependency_failure",
}

SYSTEM_PROMPT = (
    "You are a constrained repair planner for Apache Airflow pipeline failures.\n"
    "Your ONLY output must be a single JSON object — no prose, no markdown, no\n"
    "code fences.\n\n"
    "You must choose repair actions exclusively from this operator allowlist:\n"
    "  set_env | set_retry | set_timeout | replace_path | add_precheck\n\n"
    "Violation of the schema or use of unlisted operators will be rejected.\n\n"
    "You MUST output exactly this JSON schema:\n"
    "{\n"
    "  \"plan_id\": \"plan_<episode_id>\",\n"
    "  \"failure_class\": \"<match one of the 5 classes>\",\n"
    "  \"confidence\": <float 0.0-1.0>,\n"
    "  \"reasoning\": \"<1-2 sentence explanation>\",\n"
    "  \"repair_actions\": [\n"
    "    {\n"
    "      \"operator\": \"<one of allowlist operators>\",\n"
    "      \"param\": \"<key name>\",\n"
    "      \"value\": \"<new value as string>\",\n"
    "      \"justification\": \"<short reason>\"\n"
    "    }\n"
    "  ],\n"
    "  \"fallback_action\": \"escalate_to_human\",\n"
    "  \"requires_human_approval\": <true|false>\n"
    "}"
)


def _build_user_message(episode: dict[str, Any], retrieved_entries: list[dict[str, Any]]) -> str:
    """
    Build the structured user message from an episode record and retrieved
    playbook entries.

    Parameters
    ----------
    episode : dict
        Single episode record.
    retrieved_entries : list[dict]
        Top-K playbook entries from the FAISS retriever.

    Returns
    -------
    str
        Formatted user message string ready to send to the LLM.
    """
    return (
        f"Failure context:\n"
        f"  episode_id: {episode.get('episode_id', 'unknown')}\n"
        f"  dag_id: {episode.get('dag_id', 'unknown')}\n"
        f"  task_id: {episode.get('task_id', 'unknown')}\n"
        f"  failure_class: {episode.get('failure_class', 'unknown')}\n"
        f"  log_excerpt: {episode.get('log_excerpt', '')}\n"
        f"  drain_template: {episode.get('template', '')}\n\n"
        f"Relevant repair playbook entries (use these as reference):\n"
        f"{json.dumps(retrieved_entries, indent=2)}\n\n"
        f"Output a single JSON repair plan. confidence must reflect your certainty."
    )


def _strip_code_fences(text: str) -> str:
    """
    Strip markdown code fences (```json ... ``` or ``` ... ```) from a string.

    Parameters
    ----------
    text : str
        Raw LLM output that may contain code fences.

    Returns
    -------
    str
        Cleaned string with code fences removed.
    """
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


class RepairPlanner:
    """
    Constrained LLM-based repair planner for Apache Airflow failure episodes.

    Supports two backends:
    - OpenAI GPT-4o (default, requires OPENAI_API_KEY in .env)
    - Ollama / Llama 3 (local, set use_local=True)

    The planner enforces a strict JSON schema and operator allowlist.
    On validation failure it retries once, and if still invalid returns a safe
    human-escalation fallback plan.
    """

    ALLOWED_OPERATORS: set[str] = {
        "set_env",
        "set_retry",
        "set_timeout",
        "replace_path",
        "add_precheck",
    }

    def __init__(
        self,
        use_local: bool = False,
        model_name: str = "gpt-4o",
        ollama_base_url: str = "http://localhost:11434",
    ) -> None:
        """
        Initialise the planner.

        Parameters
        ----------
        use_local : bool
            If True, use Ollama/Llama3 instead of OpenAI GPT-4o.
        model_name : str
            Model identifier. Defaults to "gpt-4o" for OpenAI or "llama3" for Ollama.
        ollama_base_url : str
            Base URL of the locally running Ollama server.
        """
        self.use_local = use_local
        self.ollama_base_url = ollama_base_url.rstrip("/")

        if use_local:
            self.model_name = model_name if model_name != "gpt-4o" else "llama3"
            console.print(
                f"[bold cyan]RepairPlanner[/bold cyan] -> using local Ollama model "
                f"[bold]{self.model_name}[/bold] at {self.ollama_base_url}"
            )
        else:
            self.model_name = model_name
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                console.print(
                    "[bold yellow]Warning:[/bold yellow] OPENAI_API_KEY is not set. "
                    "Set it in your .env file to use GPT-4o."
                )
                sys.exit(1)
            # Import here so the module is usable without openai installed in local mode
            try:
                from openai import OpenAI  # type: ignore[import-untyped]
                
                base_url = os.getenv("OPENAI_BASE_URL")
                if base_url:
                    self._openai_client = OpenAI(api_key=api_key, base_url=base_url)
                else:
                    self._openai_client = OpenAI(api_key=api_key)
            except ImportError as exc:
                raise ImportError(
                    "openai package is required for cloud mode. "
                    "Install it with: pip install openai"
                ) from exc
            console.print(
                f"[bold cyan]RepairPlanner[/bold cyan] -> using OpenAI model "
                f"[bold]{self.model_name}[/bold]"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, episode: dict[str, Any], retrieved_entries: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Generate a constrained repair plan for a single failure episode.

        Steps:
          1. Build system + user prompts from episode & playbook entries.
          2. Call the configured LLM backend.
          3. Strip code fences and parse the JSON response.
          4. Validate the plan against the schema and operator allowlist.
          5. On failure, retry once with an error-correction prompt.
          6. If still invalid, return a safe fallback plan.

        Parameters
        ----------
        episode : dict
            Single episode record with fields: episode_id, dag_id, task_id,
            failure_class, log_excerpt, template, event_id, ml_confidence.
        retrieved_entries : list[dict]
            Top-K playbook entries from the FAISS retriever.

        Returns
        -------
        dict
            A validated RepairPlan dict matching the JSON schema.
        """
        episode_id = episode.get("episode_id", "unknown")
        user_msg = _build_user_message(episode, retrieved_entries)

        # --- First attempt ---
        raw_response = self._call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_msg,
        )

        parsed, parse_err = self._parse_json(raw_response)
        if parsed is not None:
            is_valid, validation_err = self._validate_plan(parsed)
            if is_valid:
                console.print(
                    f"[green][+][/green] Plan generated for [bold]{episode_id}[/bold] "
                    f"(confidence={parsed.get('confidence', '?'):.2f})"
                )
                return parsed
            error_msg = validation_err
        else:
            error_msg = parse_err

        console.print(
            f"[yellow][!][/yellow] First attempt failed for [bold]{episode_id}[/bold]: {error_msg}. "
            "Retrying with correction prompt…"
        )

        # --- Retry with correction ---
        correction_msg = (
            f"{user_msg}\n\n"
            f"IMPORTANT: Your previous response was invalid. Error: {error_msg}\n"
            f"Fix it. Output ONLY a valid JSON object. No markdown, no prose."
        )
        raw_retry = self._call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_message=correction_msg,
        )

        parsed_retry, parse_retry_err = self._parse_json(raw_retry)
        if parsed_retry is not None:
            is_valid_retry, validation_retry_err = self._validate_plan(parsed_retry)
            if is_valid_retry:
                console.print(
                    f"[green][+][/green] Plan generated (retry) for [bold]{episode_id}[/bold] "
                    f"(confidence={parsed_retry.get('confidence', '?'):.2f})"
                )
                return parsed_retry
            retry_error = validation_retry_err
        else:
            retry_error = parse_retry_err

        console.print(
            f"[bold red][-][/bold red] Retry also failed for [bold]{episode_id}[/bold]: {retry_error}. "
            "Returning safe fallback plan."
        )
        return self._safe_fallback_plan(episode, reason=retry_error)

    def plan_batch(self, jsonl_path: str, output_path: str) -> None:
        """
        Run plan() for every episode in a JSONL file and write results to output.

        Each episode in jsonl_path may optionally contain a
        ``retrieved_playbook_entries`` field. If absent, an empty list is used
        (caller should pre-populate via the FAISS retriever).

        Prints a summary: total plans, human-approval-required count, average
        confidence.

        Parameters
        ----------
        jsonl_path : str
            Path to input JSONL file (episodes_ml_classified.jsonl or similar).
        output_path : str
            Path to output JSONL file for RepairPlans.
        """
        input_path = Path(jsonl_path)
        if not input_path.exists():
            console.print(f"[bold red]File not found:[/bold red] {jsonl_path}")
            sys.exit(1)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        episodes: list[dict[str, Any]] = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    episodes.append(json.loads(line))

        console.print(
            Panel(
                f"[bold]Batch Planning[/bold]\n"
                f"Input : [cyan]{jsonl_path}[/cyan]\n"
                f"Output: [cyan]{output_path}[/cyan]\n"
                f"Episodes to process: [bold]{len(episodes)}[/bold]",
                title="RepairPlanner",
                border_style="blue",
            )
        )

        plans: list[dict[str, Any]] = []
        human_approval_count: int = 0
        total_confidence: float = 0.0

        with open(output_path, "w", encoding="utf-8") as out_f:
            for idx, episode in enumerate(episodes, start=1):
                console.print(
                    f"[dim][{idx}/{len(episodes)}][/dim] Processing "
                    f"[bold]{episode.get('episode_id', 'unknown')}[/bold]…"
                )
                retrieved_entries: list[dict[str, Any]] = episode.get(
                    "retrieved_playbook_entries", []
                )
                plan = self.plan(episode, retrieved_entries)
                plans.append(plan)
                out_f.write(json.dumps(plan) + "\n")

                if plan.get("requires_human_approval"):
                    human_approval_count += 1  # type: ignore[operator]
                total_confidence += float(plan.get("confidence", 0.0))  # type: ignore[operator]

        avg_confidence = total_confidence / len(plans) if plans else 0.0  # type: ignore[operator]

        # Summary table
        table = Table(title="Batch Planning Summary", border_style="green")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")
        table.add_row("Total Plans", str(len(plans)))
        table.add_row("Requires Human Approval", str(human_approval_count))
        table.add_row("Average Confidence", f"{avg_confidence:.4f}")
        table.add_row("Output File", output_path)
        console.print(table)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_plan(self, plan: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate a parsed plan dict against the RepairPlan schema and operator
        allowlist.

        Checks:
        - Required top-level keys are present.
        - ``failure_class`` is one of the five recognised classes.
        - ``confidence`` is a float in [0.0, 1.0].
        - ``reasoning`` is a non-empty string.
        - ``fallback_action`` is exactly "escalate_to_human".
        - ``repair_actions`` has 1–3 items, each with valid operator in allowlist.
        - ``requires_human_approval`` is True when confidence < 0.5.

        Parameters
        ----------
        plan : dict
            Parsed plan dictionary from LLM output.

        Returns
        -------
        tuple[bool, str]
            (is_valid, error_message). error_message is empty on success.
        """
        required_keys = {
            "plan_id",
            "failure_class",
            "confidence",
            "reasoning",
            "repair_actions",
            "fallback_action",
            "requires_human_approval",
        }
        missing = required_keys - set(plan.keys())
        if missing:
            return False, f"Missing required keys: {missing}"

        # failure_class
        if plan["failure_class"] not in FAILURE_CLASSES:
            return False, (
                f"Invalid failure_class '{plan['failure_class']}'. "
                f"Must be one of: {FAILURE_CLASSES}"
            )

        # confidence
        try:
            confidence = float(plan["confidence"])
        except (TypeError, ValueError):
            return False, f"confidence must be a float, got: {plan['confidence']!r}"
        if not (0.0 <= confidence <= 1.0):
            return False, f"confidence must be in [0.0, 1.0], got: {confidence}"

        # reasoning
        if not isinstance(plan["reasoning"], str) or not plan["reasoning"].strip():
            return False, "reasoning must be a non-empty string"

        # fallback_action
        if plan["fallback_action"] != "escalate_to_human":
            return False, (
                f"fallback_action must be 'escalate_to_human', "
                f"got: '{plan['fallback_action']}'"
            )

        # repair_actions
        actions = plan["repair_actions"]
        if not isinstance(actions, list):
            return False, "repair_actions must be a list"
        if not (1 <= len(actions) <= 3):
            return False, f"repair_actions must have 1–3 items, got {len(actions)}"

        required_action_keys = {"operator", "param", "value", "justification"}
        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                return False, f"repair_actions[{i}] must be a dict"
            missing_action_keys = required_action_keys - set(action.keys())
            if missing_action_keys:
                return False, (
                    f"repair_actions[{i}] missing keys: {missing_action_keys}"
                )
            operator = action["operator"]
            if operator not in self.ALLOWED_OPERATORS:
                return False, (
                    f"repair_actions[{i}].operator '{operator}' is not in the "
                    f"allowlist: {self.ALLOWED_OPERATORS}"
                )

        # requires_human_approval must be True when confidence < 0.5
        requires_human = plan["requires_human_approval"]
        if not isinstance(requires_human, bool):
            return False, "requires_human_approval must be a boolean"
        if confidence < 0.5 and not requires_human:
            return False, (
                f"requires_human_approval must be true when confidence ({confidence}) < 0.5"
            )

        return True, ""

    # ------------------------------------------------------------------
    # Fallback plan
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_fallback_plan(episode: dict[str, Any], reason: str) -> dict[str, Any]:
        """
        Return a safe fallback repair plan that escalates to a human operator.

        Used when the LLM cannot produce a valid plan after one retry.

        Parameters
        ----------
        episode : dict
            The original episode record.
        reason : str
            Human-readable reason why the LLM plan was rejected.

        Returns
        -------
        dict
            A minimal valid RepairPlan with requires_human_approval=True and
            a single add_precheck action indicating manual review is needed.
        """
        episode_id = episode.get("episode_id", "unknown")
        failure_class = episode.get("failure_class", "dependency_failure")
        # Normalise to a known class
        if failure_class not in FAILURE_CLASSES:
            failure_class = "dependency_failure"

        return {
            "plan_id": f"plan_{episode_id}",
            "failure_class": failure_class,
            "confidence": 0.0,
            "reasoning": (
                f"LLM could not produce a valid repair plan after retry. "
                f"Reason: {reason}. Manual review required."
            ),
            "repair_actions": [
                {
                    "operator": "add_precheck",
                    "param": "manual_review_required",
                    "value": "true",
                    "justification": "Automated planner failed; escalation to human operator.",
                }
            ],
            "fallback_action": "escalate_to_human",
            "requires_human_approval": True,
        }

    # ------------------------------------------------------------------
    # LLM backends
    # ------------------------------------------------------------------

    def _call_llm(self, system_prompt: str, user_message: str) -> str:
        """
        Call the configured LLM backend and return the raw text response.

        Routes to :meth:`_call_openai` or :meth:`_call_ollama` based on
        ``self.use_local``.

        Parameters
        ----------
        system_prompt : str
            System-level instructions for the LLM.
        user_message : str
            User-turn message (failure context + instructions).

        Returns
        -------
        str
            Raw text from the LLM (may contain code fences).
        """
        if self.use_local:
            return self._call_ollama(system_prompt, user_message)
        return self._call_openai(system_prompt, user_message)

    def _call_openai(self, system_prompt: str, user_message: str) -> str:
        """
        Call the OpenAI Chat Completions API (GPT-4o or configured model).

        Parameters
        ----------
        system_prompt : str
            System prompt text.
        user_message : str
            User message text.

        Returns
        -------
        str
            The assistant's reply text.

        Raises
        ------
        RuntimeError
            If the OpenAI API call fails.
        """
        try:
            response = self._openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise RuntimeError(f"OpenAI API call failed: {exc}") from exc

    def _call_ollama(self, system_prompt: str, user_message: str) -> str:
        """
        Call the local Ollama REST API (POST /api/chat).

        Parameters
        ----------
        system_prompt : str
            System prompt text.
        user_message : str
            User message text.

        Returns
        -------
        str
            The model's reply text extracted from the streaming/non-streaming response.

        Raises
        ------
        RuntimeError
            If the Ollama HTTP request fails or returns a non-200 status.
        """
        url = f"{self.ollama_base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            # Ollama returns {"message": {"role": "assistant", "content": "..."}}
            return data.get("message", {}).get("content", "")
        except requests.RequestException as exc:
            raise RuntimeError(f"Ollama API call failed: {exc}") from exc

    # ------------------------------------------------------------------
    # JSON parsing helper
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(raw: str) -> tuple[dict[str, Any] | None, str]:
        """
        Strip code fences from ``raw`` and parse as JSON.

        Parameters
        ----------
        raw : str
            Raw string (possibly with ```json fences) from the LLM.

        Returns
        -------
        tuple[dict | None, str]
            (parsed_dict, error_message). If parsing succeeds, error_message is
            empty. If it fails, parsed_dict is None and error_message describes
            the problem.
        """
        cleaned = _strip_code_fences(raw)
        try:
            data = json.loads(cleaned)
            if not isinstance(data, dict):
                return None, f"Expected a JSON object, got {type(data).__name__}"
            return data, ""
        except json.JSONDecodeError as exc:
            return None, f"JSON parse error: {exc}"


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="LLM Repair Planner — Milestone 2 Self-Healing Workflow AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Single episode plan\n"
            "  python -m planner.repair_planner --episode ep_001 \\\n"
            "      --episodes data/episodes_ml_classified.jsonl \\\n"
            "      --playbook-results data/retrieved_entries.jsonl\n\n"
            "  # Batch planning\n"
            "  python -m planner.repair_planner --plan-all \\\n"
            "      --episodes data/episodes_ml_classified.jsonl \\\n"
            "      --out data/repair_plans.jsonl\n\n"
            "  # Use local Llama3\n"
            "  python -m planner.repair_planner --plan-all --local\n"
        ),
    )

    parser.add_argument(
        "--episode",
        type=str,
        default=None,
        help="episode_id to plan for (single-episode mode)",
    )
    parser.add_argument(
        "--episodes",
        type=str,
        default="data/episodes_ml_classified.jsonl",
        help="Path to input JSONL file with classified episodes",
    )
    parser.add_argument(
        "--playbook-results",
        type=str,
        default=None,
        help=(
            "Path to JSONL file with pre-retrieved playbook entries "
            "(one record per episode, keyed by episode_id). "
            "Optional; if omitted, retrieved_playbook_entries field in the "
            "episodes file is used."
        ),
    )
    parser.add_argument(
        "--plan-all",
        action="store_true",
        help="Run batch planning over all episodes",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="data/repair_plans.jsonl",
        help="Output path for repair plans JSONL (batch mode)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local Ollama/Llama3 instead of OpenAI GPT-4o",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override model name (default: gpt-4o, or llama3 with --local)",
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://localhost:11434",
        help="Ollama base URL (default: http://localhost:11434)",
    )

    args = parser.parse_args()

    # Determine model name
    if args.model:
        model_name = args.model
    elif args.local:
        model_name = "llama3"
    else:
        model_name = "gpt-4o"

    planner = RepairPlanner(
        use_local=args.local,
        model_name=model_name,
        ollama_base_url=args.ollama_url,
    )

    # ------------------------------------------------------------------ batch
    if args.plan_all:
        planner.plan_batch(jsonl_path=args.episodes, output_path=args.out)

    # ------------------------------------------------------------------ single
    elif args.episode:
        # Load episodes
        episodes_path = Path(args.episodes)
        if not episodes_path.exists():
            console.print(f"[bold red]Episodes file not found:[/bold red] {args.episodes}")
            sys.exit(1)

        episode_record = None
        with open(episodes_path, "r", encoding="utf-8") as ep_file:
            for ep_line in ep_file:
                ep_line = ep_line.strip()
                if not ep_line:
                    continue
                import json
                rec = json.loads(ep_line)
                if isinstance(rec, dict) and rec.get("episode_id") == args.episode:
                    episode_record = rec
                    break

        if episode_record is None:
            console.print(
                f"[bold red]Episode not found:[/bold red] '{args.episode}' "
                f"in {args.episodes}"
            )
            sys.exit(1)
        assert episode_record is not None

        # Load pre-retrieved entries if provided
        retrieved: list = episode_record.get(
            "retrieved_playbook_entries", []
        )
        if args.playbook_results and not retrieved:
            pb_path = Path(args.playbook_results)
            if pb_path.exists():
                with open(pb_path, "r", encoding="utf-8") as pb_file:
                    for pb_line in pb_file:
                        pb_line = pb_line.strip()
                        if not pb_line:
                            continue
                        import json
                        pb_rec = json.loads(pb_line)
                        if isinstance(pb_rec, dict) and pb_rec.get("episode_id") == args.episode:
                            retrieved = pb_rec.get("retrieved_entries", [])
                            break

        console.print(
            Panel(
                f"[bold]Single Episode Plan[/bold]\n"
                f"episode_id : [cyan]{args.episode}[/cyan]\n"
                f"failure_class: {episode_record.get('failure_class', 'unknown')}",
                title="RepairPlanner",
                border_style="blue",
            )
        )

        plan = planner.plan(episode_record, retrieved)
        console.print_json(json.dumps(plan, indent=2))

    else:
        parser.print_help()
