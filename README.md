# Self-Healing Workflow AI — Milestones 1 & 2

A Self-Healing Workflow Automation AI built on Apache Airflow. The system
detects failures, classifies them, parses log templates, retrieves repair
playbooks via RAG, and plans constrained repairs using an LLM.

## Architecture

```
Airflow failure event
  → Failure Intelligence (M1 ✅)
  → Drain Log Parser (M2 — log_parser)
  → TF-IDF Classifier (M2 — classifier_ml)
  → Playbook RAG (M2 — rag)
  → Constrained LLM Planner (M2 — planner)
  → Patch Applier (M2 — patcher) ✅
  → Safety Gate + Preflight (M3)
  → Human Approval CLI (M3)
```

## How to Start

```bash
# 1. Initialize Airflow (first time only)
docker compose up airflow-init

# 2. Start all services
docker compose up -d

# 3. Access Airflow UI
open http://localhost:8080
# Username: airflow / Password: airflow
```

## Project Structure

```
self-healing-ai/
├── docker-compose.yml          # Airflow Docker environment
├── .env                        # UID/GID config
├── dags/                       # Airflow DAG definitions
│   ├── http_dag.py             # HTTP API pipeline
│   ├── db_dag.py               # SQLite pipeline
│   └── file_dag.py             # File processing pipeline
├── failure_injection/          # Failure injection library
│   └── injector.py             # FailureInjector class
├── episode_generator/          # Episode generation
│   └── generate_episodes.py    # Generates 60 JSONL episodes
├── classifier/                 # Regex failure classification (M1)
│   └── classifier.py           # RegexFailureClassifier class
├── log_parser/                 # Drain log template parser (M2)
│   └── drain_parser.py         # DrainParser class
├── playbook/                   # Repair playbook RAG (M2)
│   ├── retriever.py            # FAISS-based retriever
│   ├── repair_playbook.yaml    # Playbook knowledge base
│   └── __init__.py
├── planner/                    # LLM Repair Planner (M2)
│   └── repair_planner.py       # RepairPlanner class
├── patcher/                    # Patch Applier (M2) ✅
│   ├── __init__.py
│   └── patch_applier.py        # PatchApplier class
├── data/                       # Output dataset directory
│   ├── episodes_raw.jsonl      # Raw episodes from M1
│   ├── episodes_classified.jsonl # Classified episodes from M1
│   ├── parsed_logs.jsonl       # Parsed & enriched episodes from M2
│   ├── repair_plans.jsonl      # Repair plans from M2 planner
│   └── audit_log.jsonl         # Audit trail from M2 patcher
└── requirements.txt            # Python dependencies
```

## Usage

### M1 — Failure Intelligence

#### Inject a failure
```bash
python -m failure_injection.injector inject timeout http_dag
```

#### Generate all 60 episodes
```bash
python -m episode_generator.generate_episodes
```

#### Classify episodes
```bash
python -m classifier.classifier --classify-all data/episodes_raw.jsonl
```

#### Classify a single log
```bash
python -m classifier.classifier --log "ReadTimeout: HTTPSConnectionPool..."
```

#### Dry run (no Airflow needed)
```bash
python -m episode_generator.generate_episodes --dry-run
```

### M2 — Log Parsing (Drain Parser)

#### Parse a single log line
```bash
python -m log_parser.drain_parser --log "ReadTimeout: HTTPSConnectionPool(host='httpbin.org', port=443): Read timed out."
```

#### Enrich all M1 episodes with template + event_id
```bash
python -m log_parser.drain_parser --episodes data/episodes_classified.jsonl --out data/parsed_logs.jsonl --summary
```

#### Parse a plain text log file
```bash
python -m log_parser.drain_parser --file /path/to/logfile.log --out data/parsed_logs.jsonl
```

### M2 — LLM Repair Planner

#### Generate repair plans from parsed episodes
```bash
python -m planner.repair_planner --episodes data/parsed_logs.jsonl --out data/repair_plans.jsonl
```

#### Use local Ollama instead of OpenAI
```bash
python -m planner.repair_planner --local data/parsed_logs.jsonl --out data/repair_plans.jsonl
```

### M2 — Patch Applier

#### Dry-run a single repair plan (no modifications)
```bash
python -m patcher.patch_applier --plan-id plan_ep_001 --dry-run
```

#### Apply a single repair plan
```bash
python -m patcher.patch_applier --plan-id plan_ep_001
```

#### Apply all repair plans from JSONL file
```bash
python -m patcher.patch_applier --apply-all data/repair_plans.jsonl
```

#### View audit log of all applied/rejected patches
```bash
python -m patcher.patch_applier --audit
```

#### Check recent Git commits from patches
```bash
git log --oneline | grep "auto-repair"
```

## Team — M2 Split

| Member   | Component                           | Module             | Status |
|----------|-------------------------------------|--------------------|--------|
| Member 1 | Drain Log Template Parser           | `log_parser/`      | ✅     |
| Member 2 | TF-IDF + Logistic Regression Classifier | `classifier/` | ✅     |
| Member 3 | YAML Playbook + FAISS Retrieval     | `playbook/`        | ✅     |
| Member 4 | LLM Repair Planner (JSON constrained) | `planner/`       | ✅     |
| Member 5 | Patch Applier (config + DAG edits)  | `patcher/`         | ✅     |

## M2 Artifacts

The complete M2 pipeline produces:

1. **parsed_logs.jsonl** — Episodes with Drain templates and event_ids
2. **repair_plans.jsonl** — Constrained JSON repair plans from LLM
3. **audit_log.jsonl** — Audit trail of all applied/rejected patches
4. **.env.inject** — Injected environment variables
5. **dags/*.py (modified)** — Updated DAG configurations
6. **Git commits** — Full patch history for rollback capability

## Patch Applier Features

- ✅ **5 Operators**: set_env, set_retry, set_timeout, replace_path, add_precheck
- ✅ **Safety Rules**: File whitelist, regex-only DAG edits, human approval gate
- ✅ **Audit Trail**: Every patch logged to audit_log.jsonl with diffs
- ✅ **Git Commits**: Automatic commits for full rollback capability
- ✅ **Dry-Run Mode**: Test patches without modifying files
- ✅ **Batch Processing**: Apply multiple plans in sequence
- ✅ **Detailed Docs**: See [PATCH_APPLIER.md](PATCH_APPLIER.md)

## Dependencies

Install Python dependencies (for local non-Docker usage):
```bash
pip install -r requirements.txt
```
