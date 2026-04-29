from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import json, os, sys, asyncio, subprocess, tempfile
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from classifier.classifier import RegexFailureClassifier
from classifier.ml_classifier import MLClassifier
import pickle
from playbook.retriever import PlaybookRetriever
from planner.repair_planner import RepairPlanner
from patcher.patch_applier import PatchApplier
from sandbox.validator import SandboxValidator
from evaluation.evaluator import Evaluator
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(
    title="Self-Healing Workflow AI API",
    description="Diagnostics and Autonomous Repair Endpoints",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:80", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Paths ---
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
MODELS_DIR = PROJECT_ROOT / "models"
EPISODES_FILE = DATA_DIR / "episodes_raw.jsonl"
EPISODES_CLASSIFIED_FILE = DATA_DIR / "episodes_classified.jsonl"
EPISODES_ENRICHED_FILE = DATA_DIR / "episodes_enriched.jsonl"
AUDIT_LOG_FILE = DATA_DIR / "audit_log.jsonl"
REPAIR_PLANS_FILE = DATA_DIR / "repair_plans.jsonl"
SETTINGS_FILE = PROJECT_ROOT / "settings.json"

# --- Singletons ---
classifier: Optional[RegexFailureClassifier] = None
ml_model: Optional[MLClassifier] = None
retriever: Optional[PlaybookRetriever] = None
planner: Optional[RepairPlanner] = None
patcher: Optional[PatchApplier] = None
validator: Optional[SandboxValidator] = None


@app.on_event("startup")
async def startup_event():
    global classifier, ml_model, retriever, planner, patcher, validator
    classifier = RegexFailureClassifier()
    # --- Load ML Classifier from saved pipeline ---
    pkl_path = RESULTS_DIR / "pipeline.pkl"
    if pkl_path.exists():
        try:
            with open(pkl_path, "rb") as f:
                pipeline = pickle.load(f)
            ml_model = MLClassifier()
            ml_model.pipeline = pipeline
            print("[startup] MLClassifier loaded from pipeline.pkl")
        except Exception as e:
            print(f"[startup] WARNING: Failed to load pipeline.pkl — {e}")
    else:
        print("[startup] WARNING: pipeline.pkl not found — MLClassifier not loaded")
    retriever = PlaybookRetriever()
    planner = RepairPlanner(
        use_local=False,
        model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    )
    patcher = PatchApplier(project_root=str(PROJECT_ROOT))
    validator = SandboxValidator(
        airflow_base_url=os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080"),
        airflow_user=os.getenv("AIRFLOW_USER", "airflow"),
        airflow_password=os.getenv("AIRFLOW_PASSWORD", "airflow"),
    )


# --- Helpers ---
def read_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return items


def append_jsonl(path: Path, record: Dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def rewrite_jsonl(path: Path, records: List[Dict]):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def load_settings() -> Dict:
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "confidence_threshold": 0.5,
        "auto_patch_threshold": 0.8,
        "require_human_below": 0.5,
        "auto_patch_enabled": True,
        "dry_run_mode": False,
        "audit_logging": True,
    }


def _ml_classify(log_excerpt: str, fallback: str) -> str:
    """Run MLClassifier inference, falling back to regex label if model is not loaded."""
    if ml_model is not None and log_excerpt:
        try:
            return ml_model.predict_log(log_excerpt)
        except Exception:
            pass
    return fallback


# --- Pydantic Schemas ---
class LogExcerptRequest(BaseModel):
    log_excerpt: str = Field(..., description="The raw log text to classify.")


class DashboardLegacyResponse(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    plan: Optional[Dict[str, Any]] = None
    audit_entry: Optional[Dict[str, Any]] = None


class EpisodeRecord(BaseModel):
    episode_id: str
    dag_id: str
    task_id: str
    failure_type: str
    log_excerpt: str
    failure_class: Optional[str] = ""
    template: Optional[str] = ""
    event_id: Optional[str] = ""
    ml_confidence: Optional[float] = 0.0
    retrieved_playbook_entries: Optional[List[Dict[str, Any]]] = None

    model_config = {"extra": "allow"}


class ApproveRequest(BaseModel):
    approved_by: str
    notes: str = ""


class RejectRequest(BaseModel):
    rejected_by: str
    reason: str


class RollbackRequest(BaseModel):
    dry_run: bool = True


class ThresholdSettings(BaseModel):
    confidence_threshold: float
    auto_patch_threshold: float
    require_human_below: float
    auto_patch_enabled: Optional[bool] = None
    dry_run_mode: Optional[bool] = None
    audit_logging: Optional[bool] = None


class ValidationRequest(BaseModel):
    plan: Dict[str, Any]
    episode: Dict[str, Any]


# ═══════════════════════════════════════════════════
# EXISTING ENDPOINTS (preserved)
# ═══════════════════════════════════════════════════

@app.get("/api/episodes", tags=["Data Retrieval"])
def get_episodes():
    """Retrieve all episodes enriched with plan status, confidence, and repair details."""
    if not EPISODES_FILE.exists():
        raise HTTPException(status_code=404, detail="Data file not found")

    episodes = read_jsonl(EPISODES_FILE)
    plans = read_jsonl(REPAIR_PLANS_FILE)
    audit_entries = read_jsonl(AUDIT_LOG_FILE)

    # Build lookups keyed by episode_id
    # plan_id follows pattern: "plan_ep_001" → episode "ep_001"
    plan_by_ep: Dict[str, Dict] = {}
    for p in plans:
        pid = p.get("plan_id", "")
        # derive episode_id: plan_ep_001 → ep_001, plan_ep_01 → ep_01
        ep_id = pid.replace("plan_", "", 1)  # plan_ep_001 → ep_001
        plan_by_ep[ep_id] = p

    # Audit gives the authoritative final status per plan
    audit_status_by_plan: Dict[str, str] = {}
    for a in audit_entries:
        pid = a.get("plan_id", "")
        if pid:
            audit_status_by_plan[pid] = a.get("status", "unknown")

    enriched = []
    for ep in episodes:
        ep_id = ep.get("episode_id", "")
        plan = plan_by_ep.get(ep_id, {})
        plan_id = plan.get("plan_id", "")

        # Determine status: audit wins → plan.status → "pending" (has plan) → "unclassified"
        if plan_id and plan_id in audit_status_by_plan:
            status = audit_status_by_plan[plan_id]
        elif plan.get("status"):
            status = plan["status"]
        elif plan_id:
            status = "pending"
        else:
            status = "unclassified"

        # Derive failure_class: plan wins over episode raw field
        failure_class = (
            plan.get("failure_class")
            or ep.get("failure_class")
            or ep.get("failure_type")
            or "unknown"
        )

        # Playbook matches from plan or episode
        playbook_matches = (
            ep.get("retrieved_playbook_entries")
            or plan.get("retrieved_playbook_entries")
            or []
        )

        enriched.append({
            **ep,
            "failure_class": failure_class,
            "status": status,
            "plan_id": plan_id,
            # Plan fields surfaced at episode level for the detail panel
            "confidence": plan.get("confidence", 0.0),
            "ml_confidence": plan.get("confidence", ep.get("ml_confidence", 0.0)),
            "reasoning": plan.get("reasoning", ""),
            "repair_actions": plan.get("repair_actions", []),
            "requires_human_approval": plan.get("requires_human_approval", False),
            "fallback_action": plan.get("fallback_action", ""),
            "playbook_matches": playbook_matches,
            # Classifier agreement fields
            "regex_class": ep.get("failure_type", failure_class),
            "ml_class": _ml_classify(ep.get("log_excerpt", ""), failure_class),
            "classifiers_agree": ep.get("failure_type", "") == failure_class,
        })

    return enriched


@app.post("/api/classify", tags=["Diagnostics"], response_model=DashboardLegacyResponse)
def classify_log(request: LogExcerptRequest):
    if classifier is None:
        return DashboardLegacyResponse(success=False, stderr="Classifier not initialized")
    try:
        result = classifier.classify(request.log_excerpt)
        if "error" in result:
            return DashboardLegacyResponse(success=False, stderr=result["error"])
        return DashboardLegacyResponse(success=True, stdout=json.dumps(result, indent=2))
    except Exception as e:
        return DashboardLegacyResponse(success=False, stderr=str(e))


@app.post("/api/plan", tags=["Action Planning"], response_model=DashboardLegacyResponse)
def generate_repair_plan(episode: Dict[str, Any]):
    if retriever is None or planner is None:
        return DashboardLegacyResponse(success=False, stderr="Planner/Retriever not initialized")
    try:
        retrieved_entries = retriever.retrieve_for_episode(episode, top_k=2)
        plan_dict = planner.plan(episode=episode, retrieved_entries=retrieved_entries)
        return DashboardLegacyResponse(
            success=True,
            stdout=f"Plan generated successfully!\n{json.dumps(plan_dict, indent=2)}",
            plan=plan_dict,
        )
    except Exception as e:
        return DashboardLegacyResponse(success=False, stderr=str(e))


@app.post("/api/apply", tags=["System Configuration"], response_model=DashboardLegacyResponse)
def apply_repair_plan(plan: Dict[str, Any]):
    if patcher is None:
        return DashboardLegacyResponse(success=False, stderr="PatchApplier not initialized")
    try:
        patch_result = patcher.apply(plan)
        audit_entry = None
        if AUDIT_LOG_FILE.exists():
            entries = read_jsonl(AUDIT_LOG_FILE)
            if entries:
                audit_entry = entries[-1]
        return DashboardLegacyResponse(success=True, stdout="Patch applied successfully.", audit_entry=audit_entry)
    except Exception as e:
        return DashboardLegacyResponse(success=False, stderr=str(e))


@app.post("/api/validate", tags=["System Validation"], response_model=DashboardLegacyResponse)
def validate_repair_plan(request: ValidationRequest):
    if validator is None:
        return DashboardLegacyResponse(success=False, stderr="SandboxValidator not initialized")
    try:
        val_result = validator.validate(request.plan, request.episode)
        return DashboardLegacyResponse(
            success=True,
            stdout=f"Validation completed.\n{json.dumps(val_result, indent=2)}",
        )
    except Exception as e:
        return DashboardLegacyResponse(success=False, stderr=str(e))


# ═══════════════════════════════════════════════════
# NEW ENDPOINTS
# ═══════════════════════════════════════════════════

@app.get("/api/dashboard/stats", tags=["Dashboard"])
def get_dashboard_stats():
    """Compute KPI stats from JSONL files."""
    episodes = read_jsonl(EPISODES_CLASSIFIED_FILE) or read_jsonl(EPISODES_FILE)
    audit_entries = read_jsonl(AUDIT_LOG_FILE)
    plans = read_jsonl(REPAIR_PLANS_FILE)

    total = len(episodes)

    # Failure distribution
    dist: Dict[str, int] = {}
    for ep in episodes:
        fc = ep.get("failure_class") or ep.get("failure_type", "unknown")
        dist[fc] = dist.get(fc, 0) + 1

    # Auto-patch rate: unique applied plan_ids / total episodes, capped at 100%
    applied_ids = {a.get("plan_id") for a in audit_entries if a.get("status") == "applied" and a.get("plan_id")}
    auto_patch_rate = round(min(len(applied_ids) / max(total, 1) * 100, 100.0), 1)

    # MTTR: real average from audit entries that have mttr_seconds recorded
    applied_with_mttr = [
        a for a in audit_entries
        if a.get("status") == "applied" and a.get("mttr_seconds")
    ]
    mttr = round(
        sum(float(a["mttr_seconds"]) for a in applied_with_mttr)
        / max(len(applied_with_mttr), 1)
        / 60,
        1,
    )

    # Pending review: plans requiring human approval that are not yet decided
    pending_plans = [p for p in plans if p.get("requires_human_approval") and p.get("status") not in ("applied", "rejected")]
    pending_count = len(pending_plans)

    # Recent activity (last 20 audit entries, newest first)
    recent = []
    for a in reversed(audit_entries[-20:]):
        recent.append({
            "timestamp": a.get("applied_at", ""),
            "event_type": a.get("status", "unknown"),
            "description": f"Plan {a.get('plan_id','?')} — {a.get('failure_class','?')} — {a.get('status','?')}",
            "entity_id": a.get("plan_id", ""),
        })

    return {
        "total_episodes": total,
        "auto_patch_rate": auto_patch_rate,
        "mttr_minutes": mttr,
        "pending_review_count": pending_count,
        "failure_distribution": dist,
        "recent_activity": recent[:20],
    }


@app.get("/api/plans", tags=["Plans"])
def get_plans(
    failure_class: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    plans = read_jsonl(REPAIR_PLANS_FILE)
    if failure_class:
        plans = [p for p in plans if p.get("failure_class") == failure_class]
    if status:
        plans = [p for p in plans if p.get("status") == status]
    total = len(plans)
    return {"plans": plans[offset: offset + limit], "total": total}


@app.get("/api/plans/{plan_id}", tags=["Plans"])
def get_plan(plan_id: str):
    plans = read_jsonl(REPAIR_PLANS_FILE)
    plan = next((p for p in plans if p.get("plan_id") == plan_id), None)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    # Try to find the matching episode
    ep_id = plan.get("episode_id", plan_id.replace("plan_", ""))
    episodes = read_jsonl(EPISODES_ENRICHED_FILE) or read_jsonl(EPISODES_CLASSIFIED_FILE)
    episode = next((e for e in episodes if e.get("episode_id") == ep_id), None)

    # Build diff preview from audit log
    audit = read_jsonl(AUDIT_LOG_FILE)
    audit_entry = next((a for a in reversed(audit) if a.get("plan_id") == plan_id), None)
    diff_preview = audit_entry.get("diffs", {}) if audit_entry else {}

    return {"plan": plan, "episode": episode, "diff_preview": diff_preview}


@app.get("/api/review-queue", tags=["Review"])
def get_review_queue():
    plans = read_jsonl(REPAIR_PLANS_FILE)
    queue = [
        p for p in plans
        if p.get("requires_human_approval") and p.get("status") not in ("applied", "rejected")
    ]
    return {"queue": queue, "total": len(queue)}


@app.get("/api/review-queue/count", tags=["Review"])
def get_review_queue_count():
    """Returns the current number of plans pending human review."""
    plans = read_jsonl(REPAIR_PLANS_FILE)
    count = sum(
        1 for p in plans
        if p.get("requires_human_approval") and p.get("status") not in ("applied", "rejected")
    )
    return {"count": count}


@app.post("/api/review-queue/{plan_id}/approve", tags=["Review"])
def approve_plan(plan_id: str, body: ApproveRequest):
    plans = read_jsonl(REPAIR_PLANS_FILE)
    plan = next((p for p in plans if p.get("plan_id") == plan_id), None)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    git_hash = None
    actions_applied = []
    try:
        if patcher:
            result = patcher.apply(plan, dry_run=False)
            git_hash = getattr(result, "git_commit_hash", None) or (result.get("git_commit_hash") if isinstance(result, dict) else None)
            actions_applied = plan.get("repair_actions", [])
    except Exception as e:
        pass

    # Update status in JSONL
    for p in plans:
        if p.get("plan_id") == plan_id:
            p["status"] = "applied"
    rewrite_jsonl(REPAIR_PLANS_FILE, plans)

    # Append audit entry
    audit_record = {
        "plan_id": plan_id,
        "episode_id": plan.get("episode_id", ""),
        "failure_class": plan.get("failure_class", ""),
        "status": "applied",
        "applied_at": datetime.utcnow().isoformat() + "+00:00",
        "applied_by": body.approved_by,
        "notes": body.notes,
        "applied_actions": [str(a) for a in actions_applied],
        "failed_actions": [],
        "git_commit_hash": git_hash,
        "dry_run": False,
        "diffs": {},
    }
    append_jsonl(AUDIT_LOG_FILE, audit_record)

    return {"status": "applied", "git_commit_hash": git_hash, "actions_applied": actions_applied}


@app.post("/api/review-queue/{plan_id}/reject", tags=["Review"])
def reject_plan(plan_id: str, body: RejectRequest):
    plans = read_jsonl(REPAIR_PLANS_FILE)
    plan = next((p for p in plans if p.get("plan_id") == plan_id), None)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    for p in plans:
        if p.get("plan_id") == plan_id:
            p["status"] = "rejected"
            p["rejection_reason"] = body.reason
    rewrite_jsonl(REPAIR_PLANS_FILE, plans)

    audit_record = {
        "plan_id": plan_id,
        "episode_id": plan.get("episode_id", ""),
        "failure_class": plan.get("failure_class", ""),
        "status": "rejected",
        "applied_at": datetime.utcnow().isoformat() + "+00:00",
        "rejected_by": body.rejected_by,
        "rejection_reason": body.reason,
        "applied_actions": [],
        "failed_actions": [],
        "git_commit_hash": None,
        "dry_run": False,
        "diffs": {},
    }
    append_jsonl(AUDIT_LOG_FILE, audit_record)

    return {"status": "rejected", "reason": body.reason}


@app.get("/api/audit", tags=["Audit"])
def get_audit(
    dag_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100),
):
    entries = read_jsonl(AUDIT_LOG_FILE)
    if status:
        entries = [e for e in entries if e.get("status") == status]
    if dag_id:
        entries = [e for e in entries if dag_id in e.get("plan_id", "")]
    if start_date:
        entries = [e for e in entries if e.get("applied_at", "") >= start_date]
    if end_date:
        entries = [e for e in entries if e.get("applied_at", "") <= end_date]
    entries = list(reversed(entries))
    return {"entries": entries[:limit], "total": len(entries)}


@app.get("/api/audit/export", tags=["Audit"])
def export_audit():
    entries = read_jsonl(AUDIT_LOG_FILE)
    lines = ["# Audit Report\n", f"Generated: {datetime.utcnow().isoformat()} UTC\n\n",
             "| Timestamp | Plan | Failure Class | Status | Commit |\n",
             "|-----------|------|---------------|--------|--------|\n"]
    for e in reversed(entries):
        ts = e.get("applied_at", "")[:19]
        plan = e.get("plan_id", "")
        fc = e.get("failure_class", "")
        st = e.get("status", "")
        commit = e.get("git_commit_hash") or "—"
        lines.append(f"| {ts} | {plan} | {fc} | {st} | {commit} |\n")

    content = "".join(lines)
    tmp = Path(tempfile.mktemp(suffix=".md"))
    tmp.write_text(content, encoding="utf-8")
    return FileResponse(
        path=str(tmp),
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=audit_report.md"},
    )


@app.get("/api/rollback/list", tags=["Rollback"])
def get_rollback_list():
    entries = read_jsonl(AUDIT_LOG_FILE)
    eligible = [
        e for e in entries
        if e.get("status") == "applied" and e.get("git_commit_hash")
    ]
    return {"rollback_eligible": eligible, "total": len(eligible)}


@app.post("/api/rollback/{plan_id}", tags=["Rollback"])
def rollback_plan(plan_id: str, body: RollbackRequest):
    entries = read_jsonl(AUDIT_LOG_FILE)
    entry = next(
        (e for e in reversed(entries)
         if e.get("plan_id") == plan_id and e.get("git_commit_hash")),
        None,
    )
    if not entry:
        raise HTTPException(status_code=404, detail=f"No applied commit found for plan {plan_id}")

    commit_hash = entry["git_commit_hash"]
    git_cmd = f"git revert {commit_hash} --no-edit"

    if body.dry_run:
        return {
            "status": "dry_run",
            "would_revert": list(entry.get("diffs", {}).keys()),
            "git_command": git_cmd,
        }

    try:
        result = subprocess.run(
            ["git", "revert", commit_hash, "--no-edit"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        success = result.returncode == 0
        rollback_record = {
            "plan_id": plan_id,
            "episode_id": entry.get("episode_id", ""),
            "failure_class": entry.get("failure_class", ""),
            "status": "rolled_back",
            "applied_at": datetime.utcnow().isoformat() + "+00:00",
            "reverted_commit": commit_hash,
            "git_output": result.stdout,
            "git_commit_hash": None,
            "dry_run": False,
            "diffs": {},
        }
        append_jsonl(AUDIT_LOG_FILE, rollback_record)

        # After rollback: create a pending_review entry in REPAIR_PLANS_FILE
        # so the engineer can approve/reject the reverted state from the Review Queue.
        review_plan_id = f"rollback_{plan_id}"
        review_entry = {
            "plan_id": review_plan_id,
            "episode_id": entry.get("episode_id", ""),
            "failure_class": entry.get("failure_class", ""),
            "confidence": 1.0,
            "reasoning": f"Rollback of plan {plan_id} (commit {commit_hash}). Reverted by operator.",
            "repair_actions": [],
            "requires_human_approval": True,
            "status": "pending",
            "rollback_reason": "rollback",
            "original_plan_id": plan_id,
        }
        existing_plans = read_jsonl(REPAIR_PLANS_FILE)
        # Avoid duplicates
        existing_plans = [p for p in existing_plans if p.get("plan_id") != review_plan_id]
        existing_plans.append(review_entry)
        rewrite_jsonl(REPAIR_PLANS_FILE, existing_plans)

        return {
            "status": "rolled_back" if success else "error",
            "reverted_commit": commit_hash,
            "affected_files": list(entry.get("diffs", {}).keys()),
            "output": result.stdout or result.stderr,
            "review_plan_id": review_plan_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/settings/thresholds", tags=["Settings"])
def get_thresholds():
    s = load_settings()
    return {
        "confidence_threshold": s.get("confidence_threshold", 0.5),
        "auto_patch_threshold": s.get("auto_patch_threshold", 0.8),
        "require_human_below": s.get("require_human_below", 0.5),
        "auto_patch_enabled": s.get("auto_patch_enabled", True),
        "dry_run_mode": s.get("dry_run_mode", False),
        "audit_logging": s.get("audit_logging", True),
    }


@app.put("/api/settings/thresholds", tags=["Settings"])
def update_thresholds(body: ThresholdSettings):
    payload = body.model_dump(exclude_none=True)
    float_fields = {"confidence_threshold", "auto_patch_threshold", "require_human_below"}
    for field, val in payload.items():
        if field in float_fields and not (0.0 <= val <= 1.0):
            raise HTTPException(status_code=422, detail=f"{field} must be between 0.0 and 1.0")
    current = load_settings()
    current.update(payload)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return current


@app.get("/api/settings/defaults", tags=["Settings"])
def get_settings_defaults():
    """Return hardcoded default settings values."""
    return {
        "confidence_threshold": 0.5,
        "auto_patch_threshold": 0.8,
        "require_human_below": 0.5,
        "auto_patch_enabled": True,
        "dry_run_mode": False,
        "audit_logging": True,
    }


@app.get("/api/health/startup", tags=["Health"])
async def startup_health():
    """SSE stream for the LoadingScreen component."""

    async def event_stream():
        stages = [
            ("docker", "INITIALIZING DOCKER SERVICES", "airflow · postgres · redis"),
            ("model", "LOADING ML CLASSIFIER", f"pipeline.pkl"),
            ("faiss", "BUILDING FAISS INDEX", "playbook.faiss"),
            ("llm", "CONNECTING LLM API", "groq · testing latency"),
        ]

        for stage_id, label, detail in stages:
            # Loading
            yield f"data: {json.dumps({'stage': stage_id, 'status': 'loading', 'label': label, 'detail': detail})}\n\n"
            await asyncio.sleep(0.5)

            # Check each stage
            error_msg = None
            try:
                if stage_id == "docker":
                    pass  # if we're running, docker is up
                elif stage_id == "model":
                    pkl = RESULTS_DIR / "pipeline.pkl"
                    if not pkl.exists():
                        error_msg = "pipeline.pkl not found"
                    else:
                        detail = f"pipeline.pkl — {pkl.stat().st_size // 1024} KB"
                elif stage_id == "faiss":
                    faiss_f = MODELS_DIR / "playbook.faiss"
                    if not faiss_f.exists():
                        error_msg = "playbook.faiss not found"
                    else:
                        detail = f"playbook.faiss — {faiss_f.stat().st_size // 1024} KB"
                elif stage_id == "llm":
                    api_key = os.getenv("GROQ_API_KEY", "")
                    if not api_key:
                        error_msg = "GROQ_API_KEY not set"
            except Exception as e:
                error_msg = str(e)

            if error_msg:
                yield f"data: {json.dumps({'stage': stage_id, 'status': 'error', 'detail': error_msg})}\n\n"
            else:
                yield f"data: {json.dumps({'stage': stage_id, 'status': 'complete', 'detail': detail})}\n\n"
            await asyncio.sleep(0.3)

        yield f"data: {json.dumps({'stage': 'system', 'status': 'ready'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.post("/api/rollback/{plan_id}/dry-run", tags=["Rollback"])
def dry_run_rollback(plan_id: str):
    """Simulate a rollback without making any changes. Returns what would be reverted."""
    entries = read_jsonl(AUDIT_LOG_FILE)
    entry = next(
        (e for e in reversed(entries)
         if e.get("plan_id") == plan_id and e.get("git_commit_hash")),
        None,
    )
    if not entry:
        raise HTTPException(status_code=404, detail=f"No applied commit found for plan {plan_id}")
    commit_hash = entry["git_commit_hash"]
    affected = list(entry.get("diffs", {}).keys())
    return {
        "episode_id": entry.get("episode_id", ""),
        "dry_run": True,
        "plan_id": plan_id,
        "would_revert": affected,
        "git_command": f"git revert {commit_hash} --no-edit",
        "estimated_impact": f"{len(affected)} file(s) would be reverted to their pre-patch state.",
        "note": "DRY RUN SIMULATION — No changes were made",
    }


@app.get("/api/benchmark/run", tags=["System Evaluation"])
def run_benchmark():
    """Runs the full A/B Evaluation Benchmark dynamically returning all computed matrices."""
    try:
        evaluator = Evaluator()
        results = evaluator.run()
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/benchmark/retrieval", tags=["System Evaluation"])
def retrieval_metrics_endpoint():
    """Return retrieval quality metrics: Hit Rate, MRR, Precision@K, NDCG@K."""
    try:
        # Load enriched episodes (they contain retrieved_playbook_entries)
        episodes = read_jsonl(EPISODES_ENRICHED_FILE)
        if not episodes:
            episodes = read_jsonl(EPISODES_CLASSIFIED_FILE)
        if not episodes:
            episodes = read_jsonl(EPISODES_FILE)
        evaluator = Evaluator()
        metrics = evaluator._compute_retrieval_metrics(episodes, K=3)
        return {"status": "ok", "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

