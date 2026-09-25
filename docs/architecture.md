# Architecture decisions

## Local Windows profile

The prototype uses a native Windows development profile:

- React/Vite frontend on `127.0.0.1:5173`
- FastAPI backend on `127.0.0.1:8000`
- SQLite through SQLAlchemy for zero-service development
- Optional PostgreSQL and Neo4j adapters/configuration for later deployment profiles
- PowerShell scripts for setup and verification

SQLite is a deliberate development convenience, not a claim that the production relational design is complete. The model boundaries are kept compatible with PostgreSQL, and the graph API is isolated so Neo4j can replace the development graph adapter without changing investigator-facing contracts.

## Evidence chain

The persistence model keeps these concepts separate:

```text
Evidence -> ExtractionCandidate -> Entity/Relationship -> AnalysisRun -> Report
```

An AI response is generated only after querying stored records and returns citations. A generated explanation never becomes an untracked fact.
