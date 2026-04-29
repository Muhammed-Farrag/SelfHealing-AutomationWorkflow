# Self-Healing Workflow AI — Evaluation Report

## 1. Executive Summary
The Self-Healing Workflow Automation AI was rigorously evaluated across 60 historical Airflow failure episodes against an Airflow-retries-only simulation baseline. The system attained a repair success rate of 100.0% and an average MTTR of 27.5s. Overall, it successfully met ALL criteria target goals.

## 2. Metric Comparison
| Metric | Self-Healing | Baseline | Delta | Target | Status |
|--------|--------------|----------|-------|--------|--------|
| RSR | 100.0% | 18.3% | +81.7% | >70.0% | ✅ |
| MTTR (s) | 27.5s | 499.5s | -94.5% | >40.0% red. | ✅ |
| FRR | 0.0% | 0.0% | 0.0% | <10.0% | ✅ |
| GV | 0 | 0 | 0 | 0 | ✅ |

## 3. Per-Class Breakdown
| Failure Class | SH RSR | SH MTTR (s) | BL RSR | BL MTTR (s) |
|---------------|--------|-------------|--------|-------------|
| http_error | 100.0% | 27.8s | 50.0% | 325.0s |
| missing_column | 100.0% | 28.8s | 0.0% | 600.0s |
| missing_db | 100.0% | 26.5s | 0.0% | 600.0s |
| missing_file | 100.0% | 28.3s | 0.0% | 600.0s |
| timeout | 100.0% | 26.3s | 41.7% | 372.5s |

## 4. MTTR Analysis
The most significant MTTR gains originated from configuration failures (e.g. missing_db, missing_file, missing_column) which structurally cannot resolve via baseline retries (resulting strictly in 600s operator interventions). Comparatively, transient behaviors yielded proportional time savings reflecting the reduction of retry stalling overhead.

## 5. Success Criteria Checklist
- [x] RSR > 0.7  →  achieved: 1.00
- [x] MTTR reduction > 40%  →  achieved: 94%
- [x] FRR < 0.1  →  achieved: 0.00
- [x] GV = 0  →  achieved: 0

## 6. Retrieval Quality (Playbook RAG)
| Metric | Value | Description |
|--------|-------|-------------|
| Hit Rate | 0.6333 | ≥1 correct entry in top-K |
| Precision@3 | 0.2778 | Correct entries / K |
| MRR | 0.6167 | Mean Reciprocal Rank |
| NDCG@3 | 0.7167 | Normalised Discounted CG |
| Episodes w/ retrieval | 120 / 120 | Episodes that had playbook entries |

## 7. Baseline Methodology
The Airflow-retries-only simulation models transient failures (timeout, http_error) with an observed 40% overarching success rate, whereby temporal recovery consumes multiple 30s-delay retries. Structural configuration failures algorithmically default to consistent failure mappings inducing standard 600s operator handling windows. (Seed=42 for perfect reproduction).

## 8. Raw Data Sources
- `data/episodes_classified.jsonl`
- `data/repair_plans.jsonl`
- `data/validation_results.jsonl`
- `data/governance_log.jsonl`
- `data/audit_log.jsonl`
