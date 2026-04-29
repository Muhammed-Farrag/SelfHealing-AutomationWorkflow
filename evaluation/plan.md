# Self-Healing Automation Workflow — Milestone Evaluation Report

> **Reviewer:** Senior AI Systems Architect  
> **Codebase:** `SelfHealing-AutomationWorkflow`  
> **Date:** 2026-04-29  
> **Completion estimate:** ~88% (revised down from claimed 94% — explained below)

---

## TASK 1 — Planned vs Delivered Feature Matrix

| Feature | Planned | Delivered | Status | Notes |
|---|---|---|---|---|
| Regex Failure Classifier | ✅ | ✅ | **Done** | 5-class, ordered rules, catch-all fallback. Solid. |
| ML Failure Classifier (TF-IDF + LogReg) | ✅ | ✅ | **Done** | `ml_classifier.py` trains, saves `pipeline.pkl`, plots confusion matrix. |
| ML Classifier live inference in API | ✅ | ❌ | **Missing** | `main.py` only loads `RegexFailureClassifier`. `MLClassifier` is never wired into the API or startup. |
| Dual-classifier agreement signal | ✅ | **Partial** | **Partial** | `ml_class` / `regex_class` fields computed in `/api/episodes`, but both come from the same regex source — ML model is not running live. |
| FAISS Playbook Retriever | ✅ | ✅ | **Done** | `all-MiniLM-L6-v2`, `IndexFlatIP` cosine similarity, class-filtered retrieval. |
| Playbook YAML (10 entries) | ✅ | ✅ | **Done** | 10 entries covering all 5 failure classes. |
| LLM Repair Planner (Groq/OpenAI) | ✅ | ✅ | **Done** | Prompt-based with schema enforcement, retry loop, fallback plan. |
| Ollama/local LLM fallback | ✅ | ✅ | **Done** | `_call_ollama()` implemented. |
| PatchApplier (5 operators) | ✅ | ✅ | **Done** | All 5 operators: `set_env`, `set_retry`, `set_timeout`, `replace_path`, `add_precheck`. |
| Path traversal / security checks | ✅ | ✅ | **Done** | `_validate_target_file()` enforces project root containment. |
| Git commit per patch | ✅ | ✅ | **Done** | `_git_commit()` in PatchApplier. |
| Audit Log (JSONL) | ✅ | ✅ | **Done** | Every apply, reject, rollback appended to `audit_log.jsonl`. |
| SandboxValidator | ✅ | ✅ | **Done** | `sandbox/validator.py` exists and is wired into startup. |
| Governance Layer (Governor) | ✅ | ✅ | **Done** | Review queue, approve/reject, threshold monitoring, git rollback with conflict resolution. |
| Safety Threshold Auto-Pause | ✅ | ✅ | **Done** | FRR, RSR, pending queue thresholds; logs breach and pauses. |
| Human Review Queue (REST API) | ✅ | ✅ | **Done** | `/api/review-queue`, approve, reject endpoints. |
| Git Rollback via API | ✅ | ✅ | **Done** | `/api/rollback/{plan_id}` with dry-run support. |
| A/B Evaluator (RSR, MTTR, FRR, GV) | ✅ | ✅ | **Done** | Full per-class breakdown, baseline simulation, markdown report. |
| Precision@K / Recall@K retrieval metrics | ✅ | ❌ | **NOT IMPLEMENTED** | Evaluator only measures RSR/MTTR/FRR/GV. No retrieval ranking metrics anywhere. |
| MRR / NDCG / Hit Rate | ✅ | ❌ | **NOT IMPLEMENTED** | Completely absent from evaluator and any other module. |
| Failure Episode Generator | ✅ | ✅ | **Done** | `episode_generator/generate_episodes.py` + `playbook/enrich_episodes.py`. |
| Drain Log Parser | ✅ | ✅ | **Done** | `log_parser/drain_parser.py` — template extraction. |
| Failure Injection | ✅ | ✅ | **Done** | `failure_injection/injector.py`. |
| Airflow DAGs (3 synthetic) | ✅ | ✅ | **Done** | `http_dag.py`, `db_dag.py`, `file_dag.py`. |
| FastAPI Backend (main.py) | ✅ | ✅ | **Done** | 20+ endpoints across all modules. |
| Frontend (React/Vite) | ✅ | ✅ | **Done** | 10 pages, single API service layer, no direct OpenAI calls. |
| SSE startup health check | ✅ | ✅ | **Done** | `/api/health/startup` streams stage-by-stage readiness. |
| MTTR computation (real) | Planned | ❌ | **Partial** | `mttr_minutes` in `/api/dashboard/stats` is **hardcoded to `4.2`** — not computed. |
| Docker Compose (full stack) | ✅ | ✅ | **Done** | Airflow + Postgres + Redis + backend + frontend containers. |
| ML model not wired to live API | — | ❌ | **Bug** | `pipeline.pkl` exists but `MLClassifier` never loaded at runtime. |
| Accuracy plot is hardcoded | — | ❌ | **Bug** | `Intelligence.tsx` `AccuracyPlot()` uses **hardcoded static arrays**, not `results/accuracy_plot.png`. |
| Accuracy stats in UI are hardcoded | — | ❌ | **Bug** | `AgreementStat` cards render `0.942` and `0.967` as literals. |

---

## TASK 2 — Live System Readiness

### Entry Points

| Entry Point | Type | Status |
|---|---|---|
| `main.py` (uvicorn) | FastAPI backend | ✅ Runnable |
| `frontend/` (vite) | React UI | ✅ Runnable |
| `docker-compose.yml` | Full stack | ⚠️ Airflow worker known-unhealthy |
| `governance/governor.py` | CLI tool | ✅ Runnable standalone |
| `classifier/ml_classifier.py` | CLI training script | ✅ Runnable (one-shot) |

### Demo Flow (Step-by-Step)

1. **Start backend:** `uvicorn main:app --reload`
2. **Start frontend:** `cd frontend && npm run dev`
3. **Open UI → Loading Screen:** SSE health check streams docker/model/faiss/llm stages.
4. **Navigate to Episodes:** Loads `episodes_raw.jsonl`, merged with `repair_plans.jsonl` and `audit_log.jsonl`.
5. **Click an Episode → Detail Panel:** Shows failure class, confidence, repair actions, playbook matches.
6. **Navigate to Repair Plans:** Filter by status/class; view plan details with diff preview.
7. **Review Queue:** Shows plans with `requires_human_approval=True`. Approve → triggers `PatchApplier.apply()` + git commit + audit entry.
8. **Audit Trail:** Shows all applied/rejected events, git hashes, timestamps.
9. **Rollback:** Select applied plan → dry-run or live `git revert`.
10. **Benchmark:** Calls `/api/benchmark/run` → `Evaluator.run()` → displays RSR/MTTR/FRR/GV vs baseline.
11. **Intelligence:** Shows ML metrics from `results/metrics.json` + classifier agreement rate.
12. **Settings:** Adjust confidence/auto-patch thresholds, persisted to `settings.json`.

### What Works Fully ✅
- Episode loading, classification, and enrichment display
- Repair plan generation via Groq LLM (GROQ_API_KEY present in `.env`)
- Patch application with git commit and audit logging
- Human review queue (approve/reject) via REST
- Git rollback (dry-run + live)
- A/B Benchmark evaluation
- Governance threshold monitoring and auto-pause
- Export audit report (markdown download)

### What May Break During Demo ⚠️

| Risk | Severity | Description |
|---|---|---|
| `GROQ_API_KEY` exposed in `.env` | 🔴 Critical | Key `gsk_5bLBJES...` is committed in plaintext. Likely already rotated or will be during review. |
| Airflow Docker worker unhealthy | 🟠 High | `SandboxValidator` calls Airflow REST API; if Docker is not running, validation fails silently. |
| ML model not live | 🟠 High | `ml_class` in episode enrichment always equals `failure_class` from regex — dual-classifier demo broken. |
| Hardcoded MTTR = 4.2 | 🟡 Medium | Dashboard KPI is fake. An evaluator who checks the code will immediately notice. |
| Hardcoded accuracy plot in UI | 🟡 Medium | `AccuracyPlot` SVG renders static numbers regardless of actual `results/metrics.json`. |
| `pipeline.pkl` not loaded at startup | 🟡 Medium | `/api/intelligence` returns real metrics from `metrics.json`, but the model is never used for inference. |
| Git repo state for rollback | 🟡 Medium | If no patches have real git commit hashes (e.g., commits made in dry-run mode), rollback list will be empty. |
| `fastapi`, `openai`, `rich` missing from `requirements.txt` | 🔴 Critical | These are major dependencies not listed — fresh install will fail immediately. |

---

## TASK 3 — System & Retrieval Quality Evaluation

### 1. Design Choices

#### Embedding Model
- **Model:** `all-MiniLM-L6-v2` (sentence-transformers)
- **Why:** Fast, lightweight (80MB), good semantic quality for short technical text. Correct choice for a demo-scale playbook of 10 entries.
- **Critique:** With only 10 entries, any embedding model would work. There is no evaluation of retrieval quality. The FAISS index is rebuilt only when explicitly called (`--build` flag), meaning stale embeddings are possible.

#### Chunking Strategy
- **None.** Each YAML playbook entry is embedded as a single rich-text string: `"Title: ... Class: ... Description: ... Tags: ..."`.
- **Critique:** Acceptable for 10 entries. Would not scale — playbooks with 500+ entries and long descriptions would need proper chunking.

#### Retriever Type
- **FAISS `IndexFlatIP` (cosine similarity after L2 normalization)**
- **Class-filtered:** Retrieval is pre-filtered by `failure_class` before ranking.
- **Critique:** Correct approach. Pure semantic retrieval without BM25 hybrid is acceptable here given the small corpus. However, class-filtered retrieval means if the classifier is wrong, ALL retrieved entries are also wrong (cascading error). A hybrid approach would be more robust.

#### Re-ranking
- **NOT IMPLEMENTED.** No cross-encoder, no MMR, no score threshold. Top-K is returned in FAISS order after class filtering.

#### LLM Usage
- **Role:** Generator + constrained planner (single-turn prompt)
- **Model:** `llama-3.3-70b-versatile` via Groq
- **Pattern:** System prompt enforces JSON schema + operator allowlist. Two-shot retry on validation failure. Fallback plan on second failure.
- **Temperature:** 0.2 (correct — low for structured output)
- **Critique:** Using `response_format={"type": "json_object"}` is good. The retry-with-error-correction loop is a solid pattern. However, there is no chain-of-thought reasoning step before generating the plan (reasoning happens inside the same LLM call).

### 2. Evaluation Metrics

#### Implemented ✅
| Metric | Where | Notes |
|---|---|---|
| RSR (Repair Success Rate) | `evaluator.py` | `success_count / total_episodes` from validation results |
| MTTR (Mean Time to Repair) | `evaluator.py` | Mean of `mttr_seconds` from validation results |
| FRR (False Repair Rate) | `evaluator.py` | `invariant_failed / total_validated` |
| GV (Guardrail Violations) | `evaluator.py` | Counts `rejected` governance logs with schema/operator reason |
| Classifier Agreement Rate | `main.py` + `Intelligence.tsx` | `ml_class == failure_class` ratio |

#### NOT IMPLEMENTED ❌
| Metric | Suggested Implementation |
|---|---|
| **Precision@K** | For each episode, check if ground-truth playbook entry is in top-K retrieved. `precision_at_k = hits / K` |
| **Recall@K** | `recall_at_k = hits / total_relevant` per failure class |
| **MRR (Mean Reciprocal Rank)** | `mrr = mean(1/rank_of_first_correct_hit)` across all episodes |
| **NDCG** | Weight hits by position: `dcg / idcg` per query |
| **Hit Rate** | Binary: did any of top-K match? `hit_rate = hits_with_any_match / total` |
| **Context Relevance** | LLM-as-judge: score retrieved entries against episode text (0–1) |

#### How to Add Retrieval Metrics (exact code pattern):

```python
# In evaluator.py — add _compute_retrieval_metrics()
def _compute_retrieval_metrics(self, episodes, K=3):
    hits, rr_list, ndcg_list = [], [], []
    for ep in episodes:
        retrieved = ep.get("retrieved_playbook_entries", [])[:K]
        ground_truth_class = ep.get("failure_class", "")
        hit = any(r.get("failure_class") == ground_truth_class for r in retrieved)
        hits.append(int(hit))
        rank = next((i+1 for i, r in enumerate(retrieved)
                     if r.get("failure_class") == ground_truth_class), None)
        rr_list.append(1/rank if rank else 0)
        dcg = sum((1 / (i+1)) for i, r in enumerate(retrieved)
                  if r.get("failure_class") == ground_truth_class)
        ndcg_list.append(dcg)  # idcg=1 since 1 relevant doc
    return {
        "hit_rate": sum(hits)/len(hits),
        "mrr": sum(rr_list)/len(rr_list),
        "ndcg_at_k": sum(ndcg_list)/len(ndcg_list),
        "precision_at_k": sum(hits)/(len(hits)*K),
    }
```

### 3. Reliability Checks

#### Validation Mechanisms ✅
- `RepairPlanner._validate_plan()`: schema + operator allowlist + confidence checks
- `PatchApplier._validate_action()`: path traversal, operator whitelist, param type checks
- `PatchApplier._validate_target_file()`: project root containment
- `Governor._check_thresholds()`: FRR/RSR/queue monitoring with auto-pause

#### Error Handling ✅ (mostly)
- Planner: retry loop + safe fallback plan
- PatchApplier: per-action try/except, partial status on failure
- Governor: git conflict auto-resolution for data files

#### Self-Healing Logic ✅
- If LLM fails → retry with correction prompt → fallback to human escalation
- If patch fails → partial status logged, git commit skipped, audit entry written
- If thresholds breached → auto-patching paused, governance log updated
- If git revert conflicts → auto-resolve by keeping HEAD for data files

#### Improvements Needed

| Area | Issue | Fix |
|---|---|---|
| `_pause_auto_patching` | Only logs to file — `PatchApplier` never reads this flag | Add a shared state file/flag that `apply()` checks before proceeding |
| Retry strategy | Fixed 1-retry; no exponential backoff on LLM API calls | Add `tenacity`-based retry with jitter for transient API failures |
| Validator timeout | If Airflow is down, `SandboxValidator` blocks the request | Add `asyncio.wait_for` timeout wrapper |
| JSONL corruption | No transaction-safety on concurrent writes to audit files | Use file locking (`fcntl`/`portalocker`) for production |

---

## TASK 4 — Correctness Check

### Can It Actually Run?

**Answer: Partially.** The backend will start and most endpoints will work IF these blockers are resolved:

### Missing Dependencies in `requirements.txt`

```
# MISSING — will cause ImportError on fresh install:
fastapi
uvicorn
openai         # Used in repair_planner.py
rich           # Used in classifier, planner, patcher, governor
python-dotenv  # Used everywhere (listed — ✅)
pydantic       # Used by FastAPI models

# PRESENT but version-unspecified (risky):
sentence-transformers  # no pin — version drift breaks API
torch                  # no pin — huge package, version matters
faiss-cpu              # no pin
```

### Broken Parts

| Issue | File | Impact |
|---|---|---|
| `MLClassifier` never loaded in `main.py` | `main.py:59` | `/api/intelligence` shows 0% if `metrics.json` missing |
| MTTR hardcoded to `4.2` | `main.py:333` | Dashboard KPI is fabricated |
| `dependency_failure` in fallback plan | `repair_planner.py:502` | Not in `FAILURE_CLASSES` set — normalization comment exists but `dependency_failure` is not normalized to a valid class |
| `AccuracyPlot` uses static data | `Intelligence.tsx:259-260` | Training history never reflects actual training runs |
| `AgreementStat` hardcoded values | `Intelligence.tsx:133-134` | `0.942` and `0.967` are static literals |
| `results/pipeline.pkl` exists but unused | `main.py` startup | Model available but never wired to inference |
| `SandboxValidator` path relative | `sandbox/validator.py` | If run from different CWD, may fail |
| No `GROQ_MODEL` in `.env` | `.env` | Falls back to env default; docstring says `llama-3.3-70b-versatile` — works currently |

### Quick Fixes

```python
# Fix 1 — requirements.txt (add):
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
openai>=1.12.0
rich>=13.0.0
pydantic>=2.0.0

# Fix 2 — main.py startup — load ML model:
from classifier.ml_classifier import MLClassifier
import pickle
ml_model: Optional[MLClassifier] = None

@app.on_event("startup")
async def startup_event():
    global ml_model
    pkl_path = RESULTS_DIR / "pipeline.pkl"
    if pkl_path.exists():
        with open(pkl_path, "rb") as f:
            pipeline = pickle.load(f)
        ml_model = MLClassifier()
        ml_model.pipeline = pipeline

# Fix 3 — main.py compute real MTTR:
# Replace: mttr = 4.2
# With:
applied = [a for a in audit_entries if a.get("status") == "applied" and a.get("mttr_seconds")]
mttr = round(sum(a["mttr_seconds"] for a in applied) / max(len(applied), 1) / 60, 1)
```

---

## TASK 5 — LLM Planner → Agent Conversion

### Current Planner Type

The `RepairPlanner` is a **single-turn, prompt-based constrained planner**:
- No tools (cannot query external state)
- No memory (each call is stateless)
- No decision loop (one LLM call + 1 retry = done)
- Chain-of-thought reasoning is **implicit** (inside single JSON output)
- Schema enforcement is done **post-hoc** by Python validation

### Can It Be Converted to an Agent?

**Yes.** The structure is well-suited for agent conversion because:
1. The 5 operators map naturally to 5 tools
2. The validation logic already exists as a separate layer
3. The playbook retriever is already a discrete retrieval step

### Migration Plan

#### Step 1 — Define Tools (1 per operator)

```python
from langchain.tools import tool

@tool
def set_env_tool(param: str, value: str) -> str:
    """Set an environment variable in .env.inject. param=VAR_NAME, value=new_value."""
    return json.dumps({"operator": "set_env", "param": param, "value": value})

@tool
def set_retry_tool(dag_id: str, retries: int) -> str:
    """Set retry count for a DAG. Requires dag_id and integer retries >= 0."""
    return json.dumps({"operator": "set_retry", "dag_id": dag_id, "param": "retries", "value": str(retries)})

@tool
def set_timeout_tool(dag_id: str, seconds: int) -> str:
    """Set execution_timeout for a DAG task in seconds. Must be > 0."""
    return json.dumps({"operator": "set_timeout", "dag_id": dag_id, "param": "execution_timeout", "value": str(seconds)})

@tool
def replace_path_tool(param: str, value: str) -> str:
    """Replace a PATH-type env variable in .env.inject."""
    return json.dumps({"operator": "replace_path", "param": param, "value": value})

@tool
def add_precheck_tool(dag_id: str, precheck_code: str) -> str:
    """Add a precheck task to a DAG's PRECHECKS block."""
    return json.dumps({"operator": "add_precheck", "dag_id": dag_id, "value": precheck_code})

@tool
def escalate_to_human_tool(reason: str) -> str:
    """Escalate to human review when confidence is low or fix is unclear."""
    return json.dumps({"operator": "escalate", "reason": reason})
```

#### Step 2 — Add Memory

```python
from langchain.memory import ConversationSummaryMemory

memory = ConversationSummaryMemory(
    llm=llm,
    return_messages=True,
    memory_key="chat_history"
)
# Memory stores: past failure patterns, what was tried, what worked
```

#### Step 3 — Build ReAct Agent Loop

```python
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub

tools = [set_env_tool, set_retry_tool, set_timeout_tool,
         replace_path_tool, add_precheck_tool, escalate_to_human_tool]

prompt = hub.pull("hwchase17/react")

agent = create_react_agent(llm=groq_llm, tools=tools, prompt=prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    max_iterations=5,
    handle_parsing_errors=True,
    verbose=True
)

result = agent_executor.invoke({
    "input": f"Failure episode: {episode}\nRetrieved playbook: {retrieved_entries}"
})
```

#### Step 4 — Recommended Architecture (LangGraph)

For production, use LangGraph for explicit state control:

```
[START]
   ↓
[Retrieve Playbook] → FAISS retriever tool
   ↓
[Classify Intent] → identify failure_class
   ↓
[Plan Actions] → LLM selects 1-3 tools
   ↓
[Validate Schema] → Python validator (existing code)
   ↓
[Confidence Check] → branch: high → apply, low → human queue
   ↓
[Apply or Queue] → PatchApplier tool OR governance queue
   ↓
[END]
```

```python
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    episode: dict
    retrieved: list
    actions: list
    validation_result: dict
    confidence: float
    final_status: str

graph = StateGraph(AgentState)
graph.add_node("retrieve", retrieve_node)
graph.add_node("plan", plan_node)
graph.add_node("validate", validate_node)
graph.add_node("apply", apply_node)
graph.add_node("queue", queue_for_human_node)

graph.add_conditional_edges("validate", 
    lambda s: "apply" if s["confidence"] >= 0.5 else "queue")
```

---

## TASK 6 — UI Refactoring (Remove OpenAI from UI)

### Current State

**Good news:** The frontend **already has NO direct OpenAI API calls.**

All API calls in `frontend/src/app/services/api.ts` go to `http://localhost:8000` (the FastAPI backend). The frontend never imports or calls OpenAI directly.

### Where OpenAI Is Used

OpenAI (via Groq-compatible client) is used **only in the backend**:

| File | Lines | Usage |
|---|---|---|
| `planner/repair_planner.py` | 177–205 | `from openai import OpenAI` — constructs client with Groq base_url |
| `main.py` | 61–64 | Passes `GROQ_MODEL` to `RepairPlanner(use_local=False, model_name=...)` |

### Current Architecture (Already Clean)

```
UI (React)
    ↓ fetch('/api/plan')
FastAPI (main.py)
    ↓ planner.plan(episode, retrieved_entries)
RepairPlanner._call_openai()
    ↓ OpenAI client → Groq API (https://api.groq.com/openai/v1)
```

### Recommended Improvements (Not Blockers)

The coupling that DOES exist is the `openai` Python package being used as the Groq client. To fully decouple:

#### Option A — Use `httpx` directly (no openai package needed)

```python
# In repair_planner.py, replace _call_openai with:
def _call_groq_direct(self, system_prompt: str, user_message: str) -> str:
    import httpx
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {self.api_key}"},
        json={
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
```

#### Option B — Use `groq` SDK (explicit, no OpenAI branding)

```python
# requirements.txt: add groq>=0.5.0
from groq import Groq
self._groq_client = Groq(api_key=groq_key)
response = self._groq_client.chat.completions.create(...)
```

This removes the `openai` package entirely and makes the LLM dependency explicit.

#### Frontend Communication Pattern (Already Correct)

The current pattern is ideal — keep it:

```
All AI logic → Backend only (main.py endpoints)
All secrets → Backend .env (never sent to browser)
Frontend → REST calls to /api/* (no AI SDK in browser)
```

No WebSocket is needed unless you want streaming plan generation (currently not implemented). If you want streaming:

```python
# Backend: stream the LLM response
@app.post("/api/plan/stream")
async def stream_plan(episode: dict):
    async def generator():
        stream = groq_client.chat.completions.create(..., stream=True)
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            yield f"data: {json.dumps({'token': delta})}\n\n"
    return StreamingResponse(generator(), media_type="text/event-stream")
```

---

## Priority Action List for Evaluation Readiness

### 🔴 Critical (fix before demo)
1. **Add missing deps to `requirements.txt`**: `fastapi`, `uvicorn`, `openai`, `rich`, `pydantic`
2. **Wire `MLClassifier` into `main.py` startup** — load `pipeline.pkl` and use it for inference
3. **Remove or rotate the Groq API key** from `.env` before sharing the repository

### 🟠 High (fix for credibility)
4. **Compute real MTTR** — replace hardcoded `4.2` with actual calculation from audit log
5. **Fix `AccuracyPlot` in UI** — fetch image from `/api/intelligence/accuracy-plot` instead of hardcoded SVG
6. **Fix `AgreementStat` UI** — remove hardcoded `0.942` / `0.967`, derive from API response
7. **Add retrieval metrics** — at minimum Precision@K and Hit Rate (code snippet provided above)

### 🟡 Medium (improves evaluation score)
8. **Add auto-pause flag propagation** — `PatchApplier.apply()` should check governance log for pause signal
9. **Pin versions in requirements.txt** — prevents breakage on fresh install
10. **Add `GROQ_MODEL=llama-3.3-70b-versatile` to `.env`** — makes configuration explicit

### 🟢 Optional (agent conversion — for bonus points)
11. **Convert planner to LangGraph agent** using the migration plan in Task 5
12. **Add streaming plan endpoint** for real-time UI feedback
