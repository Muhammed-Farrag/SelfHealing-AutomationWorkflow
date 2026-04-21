from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import json
from pathlib import Path
import os
import sys

# Add project root to sys.path to ensure module imports work smoothly
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Internal modules
from classifier.classifier import RegexFailureClassifier
from playbook.retriever import PlaybookRetriever
from planner.repair_planner import RepairPlanner
from patcher.patch_applier import PatchApplier
from sandbox.validator import SandboxValidator

# Load .env variables for the planner/patcher
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(
    title="Self-Healing Workflow AI API",
    description="Diagnostics and Autonomous Repair Endpoints",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = PROJECT_ROOT / "data"
EPISODES_FILE = DATA_DIR / "episodes_raw.jsonl"
AUDIT_LOG_FILE = DATA_DIR / "audit_log.jsonl"

# --- Keep track of our singletons so we do not repeatedly instantiate large models ---
classifier: Optional[RegexFailureClassifier] = None
retriever: Optional[PlaybookRetriever] = None
planner: Optional[RepairPlanner] = None
patcher: Optional[PatchApplier] = None
validator: Optional[SandboxValidator] = None

@app.on_event("startup")
async def startup_event():
    """Initialize Heavy Models on Startup."""
    global classifier, retriever, planner, patcher, validator
    
    # Initialize Regex classifier
    classifier = RegexFailureClassifier()
    
    # Initialize Retriever (loads sentence transformer)
    # Note: the default PlaybookRetriever doesn't build FAISS index automatically
    # if it exists, it loads it.
    retriever = PlaybookRetriever()
    
    # Initialize Planner (uses OpenAI/Groq keys from environment)
    planner = RepairPlanner(
        use_local=False,
        model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    )
    
    # Initialize Patch Applier
    patcher = PatchApplier(project_root=str(PROJECT_ROOT))

    # Initialize Sandbox Validator
    validator = SandboxValidator(
        airflow_base_url=os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080"),
        airflow_user=os.getenv("AIRFLOW_USER", "airflow"),
        airflow_password=os.getenv("AIRFLOW_PASSWORD", "airflow")
    )


# --- Pydantic Schemas to improve typing and swagger UI ---

class LogExcerptRequest(BaseModel):
    log_excerpt: str = Field(..., description="The raw log text to classify.")

class DashboardLegacyResponse(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    plan: Optional[Dict[str, Any]] = None
    audit_entry: Optional[Dict[str, Any]] = None

# We accept open dictionaries for Episode and RepairPlan to be flexible,
# but define generic requests for documentation.
class EpisodeRecord(BaseModel):
    episode_id: str
    dag_id: str
    task_id: str
    failure_type: str
    log_excerpt: str
    
    # These fields might be missing in raw data or populated later
    failure_class: Optional[str] = ""
    template: Optional[str] = ""
    event_id: Optional[str] = ""
    ml_confidence: Optional[float] = 0.0
    retrieved_playbook_entries: Optional[List[Dict[str, Any]]] = None

    model_config = {
        "extra": "allow"
    }

# --- API Endpoints ---

@app.get("/api/episodes", tags=["Data Data Retrieval"], response_model=List[EpisodeRecord])
def get_episodes():
    """Retrieve all available failure episodes from the data store."""
    if not EPISODES_FILE.exists():
        raise HTTPException(status_code=404, detail="Data file not found")
    
    episodes = []
    with open(EPISODES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    episodes.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return episodes

@app.post("/api/classify", tags=["Diagnostics"], response_model=DashboardLegacyResponse)
def classify_log(request: LogExcerptRequest):
    """Run the regex classifier on a single log excerpt."""
    if classifier is None:
        return DashboardLegacyResponse(success=False, stderr="Classifier not initialized")
        
    try:
        result = classifier.classify(request.log_excerpt)
        if "error" in result:
            return DashboardLegacyResponse(success=False, stderr=result["error"])
            
        return DashboardLegacyResponse(
            success=True,
            stdout=json.dumps(result, indent=2)
        )
    except Exception as e:
        return DashboardLegacyResponse(success=False, stderr=str(e))

@app.post("/api/plan", tags=["Action Planning"], response_model=DashboardLegacyResponse)
def generate_repair_plan(episode: Dict[str, Any]):
    """Generate a repair plan using FAISS retrieval and the LLM Planner."""
    if retriever is None or planner is None:
        return DashboardLegacyResponse(success=False, stderr="Planner/Retriever not initialized")
        
    try:
        retrieved_entries = retriever.retrieve_for_episode(episode, top_k=2)
        plan_dict = planner.plan(episode=episode, retrieved_entries=retrieved_entries)
        
        return DashboardLegacyResponse(
            success=True,
            stdout=f"Plan generated successfully!\n{json.dumps(plan_dict, indent=2)}",
            plan=plan_dict
        )
    except Exception as e:
        return DashboardLegacyResponse(success=False, stderr=str(e))

@app.post("/api/apply", tags=["System Configuration"], response_model=DashboardLegacyResponse)
def apply_repair_plan(plan: Dict[str, Any]):
    """Apply an approved repair plan to the system configuration."""
    if patcher is None:
        return DashboardLegacyResponse(success=False, stderr="PatchApplier not initialized")
        
    try:
        patch_result = patcher.apply(plan)
        
        audit_entry = None
        if AUDIT_LOG_FILE.exists():
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    if last_line:
                        audit_entry = json.loads(last_line)
                        
        return DashboardLegacyResponse(
            success=True,
            stdout="Patch applied successfully.",
            audit_entry=audit_entry
        )
    except Exception as e:
        return DashboardLegacyResponse(success=False, stderr=str(e))

class ValidationRequest(BaseModel):
    plan: Dict[str, Any]
    episode: Dict[str, Any]

@app.post("/api/validate", tags=["System Validation"], response_model=DashboardLegacyResponse)
def validate_repair_plan(request: ValidationRequest):
    """Run sandbox validation for a single repair plan against its source episode."""
    if validator is None:
        return DashboardLegacyResponse(success=False, stderr="SandboxValidator not initialized")
        
    try:
        val_result = validator.validate(request.plan, request.episode)
        
        return DashboardLegacyResponse(
            success=True,
            stdout=f"Validation completed successfully.\\n{json.dumps(val_result, indent=2)}",
        )
    except Exception as e:
        return DashboardLegacyResponse(success=False, stderr=str(e))
