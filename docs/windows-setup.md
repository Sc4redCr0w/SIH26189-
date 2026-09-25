# Windows setup and operations

## Native development services

The Phase 0 skeleton intentionally uses SQLite so it can run on a clean Windows machine without a database server. The API still exposes a SQLAlchemy engine and can switch to PostgreSQL through `CNI_DATABASE_URL` when the relational schema phase begins.

### Required now

- Python 3.12 or newer
- Node.js 20 or newer
- Git for Windows

### Optional later services

- PostgreSQL 16+ for the relational store
- Neo4j 5.x for the graph store
- Ollama for local LLM experiments

Install optional services with Windows Package Manager when appropriate, for example:

```powershell
winget search PostgreSQL
winget search Neo4j
winget search Ollama
```

Use the vendor's Windows installer or the package identifier shown by `winget search`. Do not assume a Linux-only package or command is available.

## Environment

Copy `.env.example` to `.env` and update secrets. The API reads `CNI_`-prefixed variables. The frontend reads `VITE_API_URL`.

## Two-terminal workflow

Terminal one:

```powershell
.\scripts\start-backend.ps1
```

Terminal two:

```powershell
.\scripts\start-frontend.ps1
```

The UI is served at `http://127.0.0.1:5173`; API documentation is at `http://127.0.0.1:8000/docs`.

## Local persistence

SQLite data is written below `backend/data/` and is ignored by Git. Uploaded evidence will be written below `backend/storage/uploads/` and will also be ignored. Delete those directories only when resetting a local demonstration.

## Optional containers

Container definitions may be added for teams that already use Docker Desktop. They are not required for the native Windows workflow and are not a substitute for the PowerShell commands above.
