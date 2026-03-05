# Self-Healing Workflow AI — Milestone 1

A Self-Healing Workflow Automation AI built on Apache Airflow. This milestone
implements failure detection, injection, and classification to produce a labeled
episode dataset for downstream RAG + LLM repair planning.

## Architecture

```
Airflow failure event
  → Failure Intelligence (this milestone)
  → Playbook RAG (M2)
  → Constrained LLM Planner (M2)
  → Safety Gate + Preflight (M3)
  → Patch Applier (M3)
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
├── classifier/                 # Failure classification
│   └── classifier.py           # RegexFailureClassifier class
├── data/                       # Output directory for JSONL datasets
└── requirements.txt            # Python dependencies
```

## Usage

### Inject a failure
```bash
python -m failure_injection.injector inject timeout http_dag
```

### Generate all 60 episodes
```bash
python -m episode_generator.generate_episodes
```

### Classify episodes
```bash
python -m classifier.classifier --classify-all data/episodes_raw.jsonl
```

### Classify a single log
```bash
python -m classifier.classifier --log "ReadTimeout: HTTPSConnectionPool..."
```

### Dry run (no Airflow needed)
```bash
python -m episode_generator.generate_episodes --dry-run
```

## Dependencies

Install Python dependencies (for local non-Docker usage):
```bash
pip install -r requirements.txt
```
