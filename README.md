# Self-Healing Workflow AI

Autonomous, self-healing diagnostics and repair system for data pipelines. This project combines static code analysis, machine learning classification, and LLM-driven patch generation to automatically detect, classify, and fix failures in workflows (e.g., Apache Airflow DAGs).

## 🚀 Features

- **Failure Diagnostics**: Parses logs and identifies error signatures using both rule-based (Regex) and ML (TF-IDF/Random Forest) classifiers.
- **Autonomous Repair**: Generates repair plans via LLM (Llama-3.3-70b via Groq), complete with justifications and AST-based code modifications.
- **Human-in-the-Loop Review**: "Review Queue" isolates high-risk changes (e.g., confidence < 80%) for human approval before application.
- **Playbook Retrieval**: Uses FAISS vector search to find and apply historical solutions to new errors.
- **Rollback Manager**: Instantly reverse applied patches with dry-run support.
- **Rich Intelligence Dashboard**: Visualize ML classifier accuracy, confusion matrix, and system KPIs in real-time.

---

## 🏗 System Architecture

### 1. Frontend (React + Vite)
- **Stack**: React 18, Vite, React Router v6.
- **UI System**: Custom built with HTML/CSS, highly stylized terminal aesthetic (JetBrains Mono).
- **Service Layer**: Centralized `api.ts` handles all CRUD operations to the backend.
- **Error Handling**: Custom `PageErrorBoundary` isolates crashes to individual pages.

### 2. Backend (FastAPI)
- **Core API**: Exposes endpoints for data retrieval, plan generation, and action execution.
- **Data Layer**: Stores state locally in JSONL files (`episodes_raw.jsonl`, `repair_plans.jsonl`, `audit_log.jsonl`).
- **AI Modules**:
  - `classifier`: ML + Regex failure classification.
  - `planner`: LLM integration for reasoning and generating repair actions.
  - `patcher`: AST-based code modifier for applying fixes to `.env` or python files.
  - `playbook`: RAG system using FAISS to query past knowledge.

### 3. Infrastructure
- **Docker Compose**: Full-stack orchestration (Frontend on Nginx, Backend on Uvicorn).

---

## 🛠 Tech Stack

- **Frontend**: React, TypeScript, Vite
- **Backend**: Python 3.10, FastAPI, Uvicorn, Pydantic
- **AI/ML**: Scikit-Learn (Random Forest), FAISS, Groq API (LLaMA 3)
- **DevOps**: Docker, Docker Compose

---

## 🏃 Setup & Run Instructions

### Option A: Local Development (Manual)

**1. Start Backend**
```bash
# Activate virtual environment
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn main:app --reload --port 8000
```
*API runs on `http://localhost:8000` | Swagger UI at `http://localhost:8000/docs`*

**2. Start Frontend**
```bash
cd frontend
npm install
npm run dev
```
*App runs on `http://localhost:5173`*

### Option B: Full Stack (Docker)

```bash
# 1. Set your Groq API Key
echo "GROQ_API_KEY=your_api_key_here" > .env

# 2. Build and run containers
docker compose up --build
```
- Frontend: `http://localhost:80`
- Backend API: `http://localhost:8000`

---

## 📖 Application Flow & Screens

1. **Dashboard**: High-level KPIs (total episodes, auto-patch rate, MTTR).
2. **Episodes**: Browse raw failure events. Displays the exact error, ML confidence, and which AI classifiers agreed on the issue.
3. **Repair Plans**: View all historical AI-generated plans. Approvals/Rejections are handled here (for pending plans).
4. **Review Queue**: Focused workflow for plans flagged as `Requires Human Approval` due to low confidence.
5. **Audit Trail**: Immutable log of all system actions (plan generations, approvals, rejections, executions).
6. **Rollback**: Manage and revert previously applied patches.
7. **Intelligence**: In-depth ML metrics, confusion matrix, training accuracy plot, and failure class distribution.
8. **Settings**: Dynamic configuration for governance thresholds (e.g., auto-patch confidence levels).

---

## 🔌 API Overview

*See `http://localhost:8000/docs` for the interactive OpenAPI spec.*

### Data Retrieval
- `GET /api/dashboard/stats`: Returns KPI metrics and failure distributions.
- `GET /api/episodes`: Retrieves all logged failure episodes, joined with plan statuses and confidence.
- `GET /api/plans`: Retrieves all repair plans.
- `GET /api/review-queue`: Fetches pending plans flagged for human review.
- `GET /api/audit`: Returns the system event log.
- `GET /api/intelligence`: Retrieves ML classification reports, confusion matrix, and agreement rates.

### Actions
- `POST /api/review-queue/{plan_id}/approve`: Approves and executes a pending plan.
- `POST /api/review-queue/{plan_id}/reject`: Rejects a pending plan and archives it.
- `POST /api/rollback/{plan_id}`: Reverts an applied plan (supports dry-run via `?dry_run=true`).
- `PUT /api/settings/thresholds`: Updates system governance thresholds.

---

## 🐛 Troubleshooting & Debugging

**1. Swagger UI shows blank white screen**
- *Fix*: Hard-refresh your browser (`Ctrl+Shift+R`). This is typically a CDN caching issue with the Swagger UI assets, the API itself is working.

**2. Frontend stays on "LOADING..." forever**
- *Fix*: Ensure the FastAPI backend is running on port 8000. Check the terminal for python syntax errors. If using Docker, check `docker compose logs backend`.

**3. Docker compose fails with "variable is not set"**
- *Fix*: You must create a `.env` file in the root directory. At minimum, it should contain `GROQ_API_KEY=xxx` and `OPENAI_API_KEY=xxx`.

**4. ReferenceError or React Crash on a Page**
- *Fix*: The app uses `PageErrorBoundary`. Click "RETRY" or check the developer console for the exact stack trace. If a UI variable is missing, verify the backend API payload matches `frontend/src/app/services/api.ts`.
