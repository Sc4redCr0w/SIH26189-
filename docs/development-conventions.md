# Development conventions

## Naming

- REST resources use plural nouns: `/entities`, `/relationships`, `/cases`, `/evidence`.
- Relationship verbs are represented as relationship types, not as arbitrary URL verbs.
- IDs are opaque strings with a readable prefix (`ENT-`, `REL-`, `EVD-`, `CASE-`).
- API payloads use `snake_case`; frontend TypeScript models mirror the API contract.

## Backend

- Route modules live in `backend/app/routers/`.
- Database changes are represented in SQLAlchemy models first. A versioned migration tool will be introduced before production deployment; the development bootstrap currently uses `create_all()`.
- Every mutation records an audit event in the same database transaction.
- Authorization is checked in the backend dependency, not in the React UI.

## Frontend

- The Vite development server proxies `/api` to the local FastAPI server.
- Authentication tokens are kept in browser local storage for this local prototype only. A production deployment should use an HttpOnly, Secure, SameSite cookie or a managed session service.
- Components use native CSS tokens in `src/styles.css`; the palette is locked to a graphite/cyan intelligence-workspace direction.

## Branch strategy

- `main` is the stable integration branch.
- Short-lived feature branches use `feature/<phase>-<short-name>`.
- Fix branches use `fix/<short-name>`.
- Do not commit `.env`, local SQLite files, uploaded evidence, or generated build output.
