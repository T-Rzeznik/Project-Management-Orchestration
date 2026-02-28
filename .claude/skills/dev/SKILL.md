---
name: dev
description: Use when someone asks to start the app, run dev, spin up services, launch the dev environment, or start all services.
---

## What This Skill Does

Starts the full development stack: FastAPI backend (port 8000) + React frontend (port 5173). Checks dependencies and port availability before launching. Both services run in background so you can keep working.

## Steps

### 1. Check port availability

Run these checks in parallel:

```bash
# Check port 8000 (backend)
netstat -ano | grep :8000 | grep LISTENING
# Check port 5173 (frontend)
netstat -ano | grep :5173 | grep LISTENING
```

- If port 8000 is in use: warn the user "Port 8000 is already in use — the backend may already be running. Want me to continue anyway?" and wait for confirmation.
- If port 5173 is in use: warn the user "Port 5173 is already in use — the frontend may already be running. Want me to continue anyway?" and wait for confirmation.
- If both ports are free: proceed silently.

### 2. Check and install dependencies (if needed)

Run these checks in parallel:

**Python deps:** Check if `fastapi` is importable:
```bash
python -c "import fastapi" 2>/dev/null
```
If it fails, run: `pip install -r requirements.txt`

**Node deps:** Check if `frontend/node_modules/` exists:
```bash
ls frontend/node_modules/ > /dev/null 2>&1
```
If it doesn't exist, run: `cd frontend && npm install`

### 3. Start backend server

Run in background using Bash with `run_in_background: true`:
```bash
cd "C:\Users\tommy\Desktop\CODING STUFF\Orchestration framework" && python -m uvicorn api.server:app --reload --port 8000
```

### 4. Start frontend dev server

Run in background using Bash with `run_in_background: true`:
```bash
cd "C:\Users\tommy\Desktop\CODING STUFF\Orchestration framework\frontend" && npm run dev
```

### 5. Wait briefly then open browser

Wait 3 seconds for Vite to start, then open the browser:
```bash
start http://localhost:5173
```

### 6. Print status summary

Output this to the user:

```
Dev environment is running:
  Backend:  http://localhost:8000  (FastAPI + uvicorn --reload)
  Frontend: http://localhost:5173  (Vite dev server)

Both servers are running in background. Use /tasks to check on them.
```

## Notes

- Always start the backend BEFORE the frontend (the frontend proxies API calls to the backend).
- Both servers run in background — do NOT block on their output.
- If a dependency install fails, stop and report the error. Do not proceed to starting servers.
- Do NOT run `npm install` if `node_modules/` already exists — it's slow and unnecessary.
- Do NOT run `pip install` if deps are already importable.
- The Vite config proxies `/api/*` to `http://localhost:8000`, so the backend must be up for API calls to work.
