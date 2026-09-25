# Criminal Network Intelligence Platform

A Windows-first, evidence-first criminal network intelligence prototype built from the project specification in [`criminal_network_intelligence_project_plan.md`](./criminal_network_intelligence_project_plan.md).

## Current milestone

A working Windows-local MVP is implemented: React + FastAPI, role-scoped access, synthetic evidence/graph data, extraction review, graph exploration, analytics, grounded assistant responses, reports, and audit logging.

The application is designed around these invariants:

- Source evidence is separated from extracted facts, graph relationships, analytical findings, and AI explanations.
- Analysts are read-only for core data; authorization is enforced by the backend.
- Extracted relationships enter a review queue before becoming trusted graph data.
- AI responses are grounded in stored graph and evidence records.
- Mutations and investigation actions are audited.

## Windows quick start

Prerequisites:

- Windows 10/11
- Python 3.12+
- Node.js 20+
- Git for Windows

From PowerShell in the repository root:

```powershell
.\scripts\setup.ps1
```

Then start the two development servers in separate PowerShell windows:

```powershell
.\scripts\start-backend.ps1
```

```powershell
.\scripts\start-frontend.ps1
```

Open `http://127.0.0.1:5173`.

The API health endpoint is available at:

```text
http://127.0.0.1:8000/api/v1/health
```

## Included MVP workflows

- Admin, Analyst, and Auditor login with server-side RBAC.
- Manual entity/relationship management with evidence links and soft archival.
- Secure TXT/CSV/PDF/image intake metadata and protected downloads.
- Deterministic extraction candidates with an Admin review queue.
- Duplicate scoring, explicit merge confirmation, and relationship reconciliation.
- Interactive SVG network explorer with depth, relationship, entity-type, and date filters.
- Degree, betweenness, PageRank, component, timeline, geographic, and review-signal analysis.
- Unified search, case context/notes/history, saved searches/views, grounded assistant, and reports.
- Synthetic demonstration data under `datasets/` and an end-to-end Windows demo script.

OCR, production Neo4j/PostgreSQL services, PDF export, and asynchronous multi-agent execution remain explicitly documented follow-up work.

## Verification

Run the Phase 0 checks:

```powershell
.\scripts\verify.ps1
```

The local development database defaults to SQLite so the skeleton can run without installing PostgreSQL or Neo4j. PostgreSQL and Neo4j adapters/configuration are reserved for later phases; the Windows-native service setup is documented in [`docs/windows-setup.md`](./docs/windows-setup.md).

## Project layout

```text
backend/       FastAPI service and tests
frontend/      React + TypeScript investigator workspace
datasets/      Synthetic demonstration data (later phases)
docs/          Architecture and Windows operations notes
scripts/       PowerShell setup, run, and verification commands
tests/         Cross-layer verification (later phases)
docker/        Optional container definitions
```

## Security note

The development seed credentials in `.env.example` are intentionally visible for local setup only. Copy the file to `.env`, change the passwords, and never commit `.env` to Git.
