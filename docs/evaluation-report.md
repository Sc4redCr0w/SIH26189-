# Evaluation report

## Reproducible command

From the repository root in PowerShell:

```powershell
.\scripts\evaluate.ps1
```

## Current local result

Recorded on 2026-09-25 against the synthetic Windows development dataset:

- Backend tests: **27 passed**
- Frontend TypeScript check: **passed**
- Frontend production build: **passed**
- Health endpoint live check: **passed**
- Alembic fresh-database upgrade: **passed**
- Security headers/unauthenticated checks: **passed**
- Role enforcement checks: **passed**
- Evidence traceability checks: **passed**
- Grounded assistant checks: **passed**

## Coverage

The automated suite covers health/readiness, authentication/logout, role enforcement, user management, entity CRUD/archive/merge, duplicate candidates, evidence upload/download/validation, extraction review/approval, graph traversal/filters, centrality, timeline, geographic points, pattern signals, search, cases/notes/saved context, assistant grounding, report synthesis/export, and audit immutability surface.

## Known evaluation gaps

- Entity/relationship extraction precision and recall have no labeled real corpus yet.
- Entity-resolution thresholds have not been calibrated against representative data.
- Neo4j-specific algorithm performance has not been measured because Neo4j is not installed.
- OCR accuracy, browser interaction, load/performance, backup restore, and deployment security remain manual or future work.
- Synthetic data validates mechanics and traceability, not real-world investigative outcomes.

No metric in this report should be interpreted as a claim about real-world criminal activity or model reliability.
