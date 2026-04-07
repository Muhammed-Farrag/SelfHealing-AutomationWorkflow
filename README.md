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
  → Patch Applier (M2 — patch_applier)
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
├── data/                       # Output directory for JSONL datasets
│   ├── episodes_raw.jsonl      # Raw episodes from M1
│   ├── episodes_classified.jsonl # Classified episodes from M1
│   └── parsed_logs.jsonl       # Parsed & enriched episodes from M2
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

## Team — M2 Split

| Member   | Component                           | Module               |
|----------|-------------------------------------|----------------------|
| Member 1 | Drain Log Template Parser           | `log_parser/`        |
| Member 2 | TF-IDF + Logistic Regression Classifier | `classifier_ml/` |
| Member 3 | YAML Playbook + FAISS Retrieval     | `rag/`               |
| Member 4 | LLM Repair Planner (JSON constrained) | `planner/`         |
| Member 5 | Patch Applier (config + DAG edits)  | `patch_applier/`     |

## Dependencies

Install Python dependencies (for local non-Docker usage):
```bash
pip install -r requirements.txt
```
