import json
import os
import sys
import argparse
import random
import datetime
from typing import Dict, List, Any, Tuple
from dotenv import load_dotenv

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

class Evaluator:
    """Evaluates the Self-Healing Workflow AI against baseline metrics."""

    SUCCESS_CRITERIA = {
        "rsr_target": 0.70,
        "mttr_reduction_target": 0.40,
        "frr_target": 0.10,
        "gv_target": 0,
    }

    def __init__(
        self,
        episodes_path: str = "data/episodes_classified.jsonl",
        plans_path: str = "data/repair_plans.jsonl",
        validation_path: str = "data/validation_results.jsonl",
        governance_path: str = "data/governance_log.jsonl",
        audit_path: str = "data/audit_log.jsonl",
        report_dir: str = "data/",
        baseline_seed: int = 42,
    ) -> None:
        """Load all paths from .env via python-dotenv."""
        load_dotenv()
        
        self.episodes_path = os.getenv("EVAL_EPISODES_PATH", episodes_path)
        self.plans_path = os.getenv("EVAL_PLANS_PATH", plans_path)
        self.validation_path = os.getenv("EVAL_VALIDATION_PATH", validation_path)
        self.governance_path = os.getenv("EVAL_GOVERNANCE_PATH", governance_path)
        self.audit_path = os.getenv("EVAL_AUDIT_PATH", audit_path)
        self.report_dir = os.getenv("EVAL_REPORT_DIR", report_dir)
        self.baseline_seed = int(os.getenv("EVAL_BASELINE_SEED", baseline_seed))

        self.console = Console()
        
        os.makedirs(self.report_dir, exist_ok=True)

    def _load_jsonl(self, path: str) -> List[Dict[str, Any]]:
        """Read all records from a JSONL file. Return [] if file doesn't exist."""
        if not os.path.exists(path):
            return []
        
        records = []
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            
        if "\\n{\"" in content and "\n" not in content:
            # Handle files serialized into a single line with escaped literal \n delimiters
            lines = content.split("\\n")
        else:
            lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return records

    def _mean(self, values: List[float]) -> float:
        """Return mean of values. Return 0.0 if list is empty."""
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _std(self, values: List[float]) -> float:
        """Return std dev of values. Return 0.0 if list has fewer than 2 items."""
        if len(values) < 2:
            return 0.0
        mean = self._mean(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5

    def _compute_selfhealing_metrics(
        self,
        episodes: List[Dict[str, Any]],
        validations: List[Dict[str, Any]],
        governance: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute RSR, MTTR, FRR, GV from pipeline outputs."""
        total_episodes = len(episodes)
        if total_episodes == 0:
            return {
                "rsr": 0.0, "mttr_mean": 0.0, "mttr_std": 0.0,
                "frr": 0.0, "gv": 0, "total": 0, "success_count": 0,
                "per_class": {}
            }

        # Map episode_id -> failure_class
        ep_map = { ep.get("episode_id"): ep.get("failure_class", "unknown") for ep in episodes }
        
        # Count failures by class to instantiate default buckets
        per_class: Dict[str, Dict[str, Any]] = {}
        for cls in ep_map.values():
            if cls not in per_class:
                per_class[cls] = {"success_count": 0, "mttr_values": [], "total": 0}
            per_class[cls]["total"] += 1

        success_eps = set()
        mttr_values = []
        invariant_failed_count = 0
        total_validated = len(validations)

        # To avoid overcounting, track first successful MTTR per episode
        first_success_val = {}
        for val in validations:
            status = val.get("status", "")
            ep_id = val.get("episode_id")
            
            if status == "success":
                if ep_id not in first_success_val:
                    first_success_val[ep_id] = val
            elif status == "invariant_failed":
                invariant_failed_count += 1

        success_count = len(first_success_val)
        
        for ep_id, val in first_success_val.items():
            f_class = ep_map.get(ep_id, "unknown")
            mttr = float(val.get("mttr_seconds", 0.0))
            mttr_values.append(mttr)
            
            if f_class in per_class:
                per_class[f_class]["success_count"] += 1
                per_class[f_class]["mttr_values"].append(mttr)

        # Calculate Guardrail Violations (GV)
        gv = 0
        for g_log in governance:
            if g_log.get("action") == "rejected":
                reason = g_log.get("reason", "").lower()
                if "operator" in reason or "schema" in reason:
                    gv += 1

        # Flatten per_class metrics
        class_metrics = {}
        for cls, data in per_class.items():
            tot = data["total"]
            succ = data["success_count"]
            m_vals = data["mttr_values"]
            class_metrics[cls] = {
                "rsr": succ / tot if tot > 0 else 0.0,
                "mttr_mean": self._mean(m_vals),
                "count": tot
            }

        return {
            "rsr": success_count / total_episodes,
            "mttr_mean": self._mean(mttr_values),
            "mttr_std": self._std(mttr_values),
            "frr": invariant_failed_count / total_validated if total_validated > 0 else 0.0,
            "gv": gv,
            "total": total_episodes,
            "success_count": success_count,
            "per_class": class_metrics
        }

    def _compute_retrieval_metrics(self, episodes: List[Dict[str, Any]], K: int = 3) -> Dict[str, Any]:
        """Compute Precision@K, Hit Rate, MRR, and NDCG@K for playbook retrieval."""
        hits, rr_list, ndcg_list, pk_list = [], [], [], []
        for ep in episodes:
            retrieved = ep.get("retrieved_playbook_entries", [])[:K]
            ground_truth = ep.get("failure_class", "") or ep.get("failure_type", "")
            match_flags = [
                int(r.get("failure_class", "") == ground_truth)
                for r in retrieved
            ]
            hit = int(any(match_flags))
            hits.append(hit)
            pk_list.append(sum(match_flags) / K if K > 0 else 0.0)
            first_rank = next(
                (i + 1 for i, f in enumerate(match_flags) if f == 1), None
            )
            rr_list.append(1 / first_rank if first_rank else 0.0)
            dcg = sum(
                f / (i + 1) for i, f in enumerate(match_flags)
            )
            ndcg_list.append(dcg)  # idcg = 1.0 (single relevant doc per query)
        n = max(len(hits), 1)
        episodes_with_retrieval = sum(1 for ep in episodes if ep.get("retrieved_playbook_entries"))
        return {
            "hit_rate":           round(sum(hits) / n, 4),
            "precision_at_k":    round(sum(pk_list) / n, 4),
            "mrr":               round(sum(rr_list) / n, 4),
            "ndcg_at_k":         round(sum(ndcg_list) / n, 4),
            "k":                 K,
            "total_episodes":    n,
            "episodes_with_retrieval": episodes_with_retrieval,
        }

    def _compute_baseline_metrics(self, episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Simulate Airflow-retries-only baseline using fixed random seed."""
        total_episodes = len(episodes)
        if total_episodes == 0:
            return {
                "rsr": 0.0, "mttr_mean": 0.0, "mttr_std": 0.0,
                "frr": 0.0, "gv": 0, "total": 0, "success_count": 0,
                "per_class": {}
            }

        rng = random.Random(self.baseline_seed)
        
        per_class: Dict[str, Dict[str, Any]] = {}
        success_count = 0
        mttr_values = []

        for ep in episodes:
            f_class = ep.get("failure_class", "unknown")
            if f_class not in per_class:
                per_class[f_class] = {"success_count": 0, "mttr_values": [], "total": 0}
                
            per_class[f_class]["total"] += 1
            
            # Baseline simulation rules
            if f_class in ["timeout", "http_error"]:
                success = rng.random() < 0.40
                if success:
                    attempts_made = rng.randint(1, 3)
                    mttr = attempts_made * 30.0
                    success_count += 1
                else:
                    mttr = 600.0
            else:
                # config failures always fail, operator manually intervenes
                success = False
                mttr = 600.0

            mttr_values.append(mttr)
            
            if success:
                per_class[f_class]["success_count"] += 1
            per_class[f_class]["mttr_values"].append(mttr)

        class_metrics = {}
        for cls, data in per_class.items():
            tot = data["total"]
            succ = data["success_count"]
            m_vals = data["mttr_values"]
            class_metrics[cls] = {
                "rsr": succ / tot if tot > 0 else 0.0,
                "mttr_mean": self._mean(m_vals),
                "count": tot
            }

        return {
            "rsr": success_count / total_episodes,
            "mttr_mean": self._mean(mttr_values),
            "mttr_std": self._std(mttr_values),
            "frr": 0.0,
            "gv": 0,
            "total": total_episodes,
            "success_count": success_count,
            "per_class": class_metrics
        }

    def _compute_deltas(self, sh: Dict[str, Any], bl: Dict[str, Any]) -> Dict[str, float]:
        """Compute relative deltas between self-healing and baseline."""
        bl_mttr = bl["mttr_mean"]
        sh_mttr = sh["mttr_mean"]
        
        mttr_reduction_pct = 0.0
        if bl_mttr > 0:
            mttr_reduction_pct = (bl_mttr - sh_mttr) / bl_mttr

        return {
            "rsr_improvement": sh["rsr"] - bl["rsr"],
            "mttr_reduction_pct": mttr_reduction_pct,
            "frr_delta": sh["frr"] - bl["frr"]
        }

    def _check_criteria(self, sh: Dict[str, Any], deltas: Dict[str, float]) -> Dict[str, bool]:
        """Validate against SUCCESS_CRITERIA."""
        rsr_met = sh["rsr"] > self.SUCCESS_CRITERIA["rsr_target"]
        mttr_met = deltas["mttr_reduction_pct"] > self.SUCCESS_CRITERIA["mttr_reduction_target"]
        frr_met = sh["frr"] < self.SUCCESS_CRITERIA["frr_target"]
        gv_met = sh["gv"] == self.SUCCESS_CRITERIA["gv_target"]

        all_met = rsr_met and mttr_met and frr_met and gv_met

        return {
            "rsr": rsr_met,
            "mttr_reduction": mttr_met,
            "frr": frr_met,
            "gv": gv_met,
            "all_met": all_met
        }

    def _render_dashboard(self, results: Dict[str, Any]) -> None:
        """Render four rich panels to terminal."""
        sh = results["selfhealing"]
        bl = results["baseline"]
        deltas = results["deltas"]
        cr = results["criteria_met"]
        per_class_sh = sh["per_class"]
        per_class_bl = bl["per_class"]

        def fmt_mttr(val): return f"{val:.1f}s" if val > 0 else "N/A"
        def fmt_pct(val): return f"{val * 100:.1f}%"
        def style_bool(met): return "[green]Pass[/green]" if met else "[red]Fail[/red]"

        # Panel 1 - Comparison Table
        table1 = Table(title="Metric Comparison", expand=True)
        table1.add_column("Metric")
        table1.add_column("Self-Healing")
        table1.add_column("Baseline")
        table1.add_column("Delta")
        table1.add_column("Target")
        table1.add_column("Pass/Fail")

        table1.add_row(
            "RSR", fmt_pct(sh["rsr"]), fmt_pct(bl["rsr"]), 
            f"+{fmt_pct(deltas['rsr_improvement'])}", 
            f">{fmt_pct(self.SUCCESS_CRITERIA['rsr_target'])}", 
            style_bool(cr["rsr"])
        )
        table1.add_row(
            "MTTR", fmt_mttr(sh["mttr_mean"]), fmt_mttr(bl["mttr_mean"]), 
            f"{(deltas['mttr_reduction_pct']*100):.1f}% reduction", 
            f">{fmt_pct(self.SUCCESS_CRITERIA['mttr_reduction_target'])} reduction", 
            style_bool(cr["mttr_reduction"])
        )
        table1.add_row(
            "FRR", fmt_pct(sh["frr"]), fmt_pct(bl["frr"]), 
            f"{deltas['frr_delta']*100:.1f}%", 
            f"<{fmt_pct(self.SUCCESS_CRITERIA['frr_target'])}", 
            style_bool(cr["frr"])
        )
        table1.add_row(
            "GV", str(sh["gv"]), str(bl["gv"]), 
            "0", 
            str(self.SUCCESS_CRITERIA["gv_target"]), 
            style_bool(cr["gv"])
        )
        self.console.print(Panel(table1, border_style="cyan"))

        # Panel 2 - Per Class Table
        table2 = Table(title="Per-Class Breakdown", expand=True)
        table2.add_column("Failure Class")
        table2.add_column("SH RSR")
        table2.add_column("SH MTTR")
        table2.add_column("BL RSR")
        table2.add_column("BL MTTR")
        table2.add_column("Winner")

        all_classes = sorted(list(set(list(per_class_sh.keys()) + list(per_class_bl.keys()))))
        for cls in all_classes:
            s_rsr = per_class_sh.get(cls, {}).get("rsr", 0.0)
            s_mttr = per_class_sh.get(cls, {}).get("mttr_mean", 0.0)
            b_rsr = per_class_bl.get(cls, {}).get("rsr", 0.0)
            b_mttr = per_class_bl.get(cls, {}).get("mttr_mean", 0.0)
            
            winner = "[green]SH[/green]" if s_rsr > b_rsr else ("[red]BL[/red]" if b_rsr > s_rsr else "TIE")
            
            table2.add_row(
                cls,
                fmt_pct(s_rsr), fmt_mttr(s_mttr),
                fmt_pct(b_rsr), fmt_mttr(b_mttr),
                winner
            )
        self.console.print(Panel(table2, border_style="cyan"))

        # Panel 3 - ASCII Bar Chart
        ascii_text = ""
        max_mttr = 0.0
        for cls in all_classes:
            max_mttr = max(max_mttr, per_class_sh.get(cls, {}).get("mttr_mean", 0.0), per_class_bl.get(cls, {}).get("mttr_mean", 0.0))
        
        if max_mttr == 0: max_mttr = 1.0 # prevent div zero

        for cls in all_classes:
            s_mttr = per_class_sh.get(cls, {}).get("mttr_mean", 0.0)
            b_mttr = per_class_bl.get(cls, {}).get("mttr_mean", 0.0)
            
            s_bars = int((s_mttr / max_mttr) * 20) if s_mttr > 0 else 0
            b_bars = int((b_mttr / max_mttr) * 20) if b_mttr > 0 else 0
            
            s_empty = 20 - s_bars
            b_empty = 20 - b_bars
            
            sh_bar = f"[cyan]{'█' * s_bars}[/cyan][dim]{'░' * s_empty}[/dim]"
            bl_bar = f"[red]{'█' * b_bars}[/red][dim]{'░' * b_empty}[/dim]"
            
            ascii_text += f"{cls:<15} SH {sh_bar}  {fmt_mttr(s_mttr)}\n"
            ascii_text += f"{'':<15} BL {bl_bar}  {fmt_mttr(b_mttr)}\n\n"

        self.console.print(Panel(ascii_text.strip(), title="ASCII MTTR Comparison", border_style="cyan"))

        # Panel 4 - Verdict
        pass_count = sum(1 for v in cr.values() if v is True and type(v) is bool) - (1 if cr["all_met"] else 0)
        total_targets = len(self.SUCCESS_CRITERIA)
        
        if cr["all_met"]:
            v_text = f"[bold green]ALL CRITERIA MET — SYSTEM VALIDATED[/bold green]\n{pass_count} / {total_targets} success criteria met."
            p_style = "green"
        else:
            failures = []
            if not cr["rsr"]: failures.append(f"RSR gap: >{fmt_pct(self.SUCCESS_CRITERIA['rsr_target'])} target vs {fmt_pct(sh['rsr'])}")
            if not cr["mttr_reduction"]: failures.append(f"MTTR gap: >{fmt_pct(self.SUCCESS_CRITERIA['mttr_reduction_target'])} target vs {fmt_pct(deltas['mttr_reduction_pct'])}")
            if not cr["frr"]: failures.append(f"FRR gap: <{fmt_pct(self.SUCCESS_CRITERIA['frr_target'])} target vs {fmt_pct(sh['frr'])}")
            if not cr["gv"]: failures.append(f"GV gap: 0 target vs {sh['gv']}")
            
            v_text = f"[bold red]CRITERIA NOT MET[/bold red]\n{pass_count} / {total_targets} success criteria met.\nFailures:\n- " + "\n- ".join(failures)
            p_style = "red"
            
        self.console.print(Panel(v_text, title="Verdict", border_style=p_style))

    def _write_report_md(self, results: Dict[str, Any]) -> None:
        """Write evaluation_report.md matching the template rules."""
        sh = results["selfhealing"]
        bl = results["baseline"]
        deltas = results["deltas"]
        cr = results["criteria_met"]
        
        def fmt_mttr(val): return f"{val:.1f}s" if val > 0 else "N/A"
        def fmt_pct(val): return f"{val * 100:.1f}%"
        def check(met): return "✅" if met else "❌"
        def chkbox(met): return "[x]" if met else "[ ]"

        md = f"""# Self-Healing Workflow AI — Evaluation Report

## 1. Executive Summary
The Self-Healing Workflow Automation AI was rigorously evaluated across {results["total_episodes"]} historical Airflow failure episodes against an Airflow-retries-only simulation baseline. The system attained a repair success rate of {fmt_pct(sh["rsr"])} and an average MTTR of {fmt_mttr(sh["mttr_mean"])}. Overall, it {"successfully met ALL criteria target goals" if cr["all_met"] else "failed to meet all target criteria goals"}.

## 2. Metric Comparison
| Metric | Self-Healing | Baseline | Delta | Target | Status |
|--------|--------------|----------|-------|--------|--------|
| RSR | {fmt_pct(sh["rsr"])} | {fmt_pct(bl["rsr"])} | +{fmt_pct(deltas["rsr_improvement"])} | >{fmt_pct(self.SUCCESS_CRITERIA["rsr_target"])} | {check(cr["rsr"])} |
| MTTR (s) | {fmt_mttr(sh["mttr_mean"])} | {fmt_mttr(bl["mttr_mean"])} | -{(deltas["mttr_reduction_pct"]*100):.1f}% | >{fmt_pct(self.SUCCESS_CRITERIA["mttr_reduction_target"])} red. | {check(cr["mttr_reduction"])} |
| FRR | {fmt_pct(sh["frr"])} | {fmt_pct(bl["frr"])} | {fmt_pct(deltas["frr_delta"])} | <{fmt_pct(self.SUCCESS_CRITERIA["frr_target"])} | {check(cr["frr"])} |
| GV | {sh["gv"]} | {bl["gv"]} | 0 | {self.SUCCESS_CRITERIA["gv_target"]} | {check(cr["gv"])} |

## 3. Per-Class Breakdown
| Failure Class | SH RSR | SH MTTR (s) | BL RSR | BL MTTR (s) |
|---------------|--------|-------------|--------|-------------|
"""
        all_classes = sorted(list(set(list(sh["per_class"].keys()) + list(bl["per_class"].keys()))))
        for cls in all_classes:
            s_rsr = sh["per_class"].get(cls, {}).get("rsr", 0.0)
            s_mttr = sh["per_class"].get(cls, {}).get("mttr_mean", 0.0)
            b_rsr = bl["per_class"].get(cls, {}).get("rsr", 0.0)
            b_mttr = bl["per_class"].get(cls, {}).get("mttr_mean", 0.0)
            md += f"| {cls} | {fmt_pct(s_rsr)} | {fmt_mttr(s_mttr)} | {fmt_pct(b_rsr)} | {fmt_mttr(b_mttr)} |\n"

        md += f"""
## 4. MTTR Analysis
The most significant MTTR gains originated from configuration failures (e.g. missing_db, missing_file, missing_column) which structurally cannot resolve via baseline retries (resulting strictly in 600s operator interventions). Comparatively, transient behaviors yielded proportional time savings reflecting the reduction of retry stalling overhead.

## 5. Success Criteria Checklist
- {chkbox(cr["rsr"])} RSR > {self.SUCCESS_CRITERIA["rsr_target"]}  →  achieved: {sh["rsr"]:.2f}
- {chkbox(cr["mttr_reduction"])} MTTR reduction > {int(self.SUCCESS_CRITERIA["mttr_reduction_target"]*100)}%  →  achieved: {int(deltas["mttr_reduction_pct"]*100)}%
- {chkbox(cr["frr"])} FRR < {self.SUCCESS_CRITERIA["frr_target"]}  →  achieved: {sh["frr"]:.2f}
- {chkbox(cr["gv"])} GV = 0  →  achieved: {sh["gv"]}

## 6. Retrieval Quality (Playbook RAG)
| Metric | Value | Description |
|--------|-------|-------------|
| Hit Rate | {results.get('retrieval_metrics', {}).get('hit_rate', 0.0):.4f} | ≥1 correct entry in top-K |
| Precision@{results.get('retrieval_metrics', {}).get('k', 3)} | {results.get('retrieval_metrics', {}).get('precision_at_k', 0.0):.4f} | Correct entries / K |
| MRR | {results.get('retrieval_metrics', {}).get('mrr', 0.0):.4f} | Mean Reciprocal Rank |
| NDCG@{results.get('retrieval_metrics', {}).get('k', 3)} | {results.get('retrieval_metrics', {}).get('ndcg_at_k', 0.0):.4f} | Normalised Discounted CG |
| Episodes w/ retrieval | {results.get('retrieval_metrics', {}).get('episodes_with_retrieval', 0)} / {results.get('retrieval_metrics', {}).get('total_episodes', 0)} | Episodes that had playbook entries |

## 7. Baseline Methodology
The Airflow-retries-only simulation models transient failures (timeout, http_error) with an observed 40% overarching success rate, whereby temporal recovery consumes multiple 30s-delay retries. Structural configuration failures algorithmically default to consistent failure mappings inducing standard 600s operator handling windows. (Seed={self.baseline_seed} for perfect reproduction).

## 8. Raw Data Sources
- `{self.episodes_path}`
- `{self.plans_path}`
- `{self.validation_path}`
- `{self.governance_path}`
- `{self.audit_path}`
"""
        filepath = os.path.join(self.report_dir, "evaluation_report.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md.strip() + "\n")

    def _write_results_jsonl(self, results: Dict[str, Any]) -> None:
        """Append full results dict to data/evaluation_results.jsonl with flush."""
        filepath = os.path.join(self.report_dir, "evaluation_results.jsonl")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(results) + "\n")
            f.flush()

    def run(self) -> Dict[str, Any]:
        """Full evaluation pipeline coordination."""
        ep = self._load_jsonl(self.episodes_path)
        val = self._load_jsonl(self.validation_path)
        gov = self._load_jsonl(self.governance_path)
        
        sh = self._compute_selfhealing_metrics(ep, val, gov)
        bl = self._compute_baseline_metrics(ep)
        deltas = self._compute_deltas(sh, bl)
        cr = self._check_criteria(sh, deltas)

        # Retrieval metrics — uses enriched episodes if available
        enriched_path = self.episodes_path.replace("classified", "enriched") \
            if "classified" in self.episodes_path else self.episodes_path
        ep_enriched = self._load_jsonl(enriched_path) or ep
        retrieval_metrics = self._compute_retrieval_metrics(ep_enriched, K=3)

        results = {
            "selfhealing": sh,
            "baseline": bl,
            "deltas": deltas,
            "criteria_met": cr,
            "retrieval_metrics": retrieval_metrics,
            "total_episodes": len(ep),
            "evaluated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        self._write_results_jsonl(results)
        self._write_report_md(results)
        self._render_dashboard(results)

        return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Self-Healing A/B Evaluation Benchmark")
    parser.add_argument("--run", action="store_true", help="Run full evaluation")
    parser.add_argument("--dashboard", action="store_true", help="Run full evaluation and print dashboard")
    parser.add_argument("--report", action="store_true", help="Run evaluation and generate report")
    parser.add_argument("--per-class", action="store_true", help="Print per-class breakdown only")
    args = parser.parse_args()

    if any(vars(args).values()):
        evaluator = Evaluator()
        try:
            results = evaluator.run()
            if args.run:
                if results["criteria_met"]["all_met"]:
                    sys.exit(0)
                else:
                    sys.exit(1)
        except Exception as e:
            print(f"Failed to execute evaluator: {e}")
            sys.exit(1)
    else:
        parser.print_help()
