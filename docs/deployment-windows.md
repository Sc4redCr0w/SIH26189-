# Native Windows deployment runbook

This runbook avoids requiring a Linux host. The default local profile uses Windows processes, PowerShell, SQLite, and the Vite/React build served by FastAPI.

## 1. Prepare the host

- Windows 10/11 x64.
- Python 3.12+ and Node.js 20+.
- Git for Windows.
- A Windows user with permission to run the application and write `backend/data` and `backend/storage`.
- For a shared deployment, install PostgreSQL and Neo4j using their Windows installers or approved Windows packages.

## 2. Configure secrets

```powershell
Copy-Item .env.example .env
notepad .env
```

Set a unique `CNI_JWT_SECRET`, change all seed passwords, and set `CNI_DATABASE_URL`/Neo4j values when those services are available. Never commit `.env`.

## 3. Build a release

```powershell
.\scripts\build-release.ps1
```

The script runs backend tests, applies Alembic migrations, typechecks/builds the frontend, and creates a timestamped `release/` bundle.

## 4. Run locally as one service

```powershell
.\scripts\serve-windows.ps1
```

Open `http://127.0.0.1:8000`. The API remains under `/api/v1`; the built React application is served by FastAPI when `frontend/dist` exists.

## 5. Run as a Windows service

Use an approved Windows service wrapper such as WinSW or NSSM. The service command should run:

```powershell
D:\Codes\SIH26189-\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir D:\Codes\SIH26189-\backend --host 127.0.0.1 --port 8000
```

Set the working directory to the repository/release directory, grant the service account only the required data/upload permissions, and configure restart-on-failure. Validate the service account cannot modify audit history at the database layer.

## 6. TLS and reverse proxy

For a shared deployment, place the FastAPI service behind a Windows-supported TLS reverse proxy or IIS ARR. Forward only `127.0.0.1:8000`, enable HTTPS/HSTS, restrict CORS, and do not expose the development Vite server.

## 7. Backups and recovery

```powershell
.\scripts\backup.ps1 -Destination D:\SecureBackups\SignalAtlas
```

Test restoring the SQLite database and uploads into a clean directory. For PostgreSQL/Neo4j, use their Windows-native backup procedures and encrypt backups.

## 8. Go-live checklist

- [ ] Secrets rotated and `.env` protected.
- [ ] PostgreSQL/Neo4j connectivity tested if enabled.
- [ ] HTTPS/HSTS and reverse-proxy headers verified.
- [ ] Database roles enforce audit append-only behavior.
- [ ] Backup restore tested.
- [ ] OCR/LLM optional services disabled unless approved.
- [ ] Synthetic data clearly labeled.
- [ ] Security and evaluation reports reviewed.
