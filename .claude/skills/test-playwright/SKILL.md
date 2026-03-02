---
name: test-playwright
description: Use when someone asks to run all tests, run the test suite, test everything, run tests and e2e, run pytest vitest and playwright, or check if all tests pass.
---

## What This Skill Does

Runs the full test pipeline: pytest (Python backend) + vitest (React unit tests) + Playwright (e2e tests). Checks that dev services are running first, starts them if needed, then executes all three suites and prints a combined pass/fail summary.

## Steps

### 1. Check if dev services are running

Run these checks in parallel:

```bash
# Check backend (port 8000)
netstat -ano | grep :8000 | grep LISTENING
```

```bash
# Check frontend (port 5173)
netstat -ano | grep :5173 | grep LISTENING
```

- If backend is **down**: start it in background:
  ```bash
  python -m uvicorn api.server:app --reload --port 8000
  ```
  Wait up to 10 seconds for port 8000 to become available. If it doesn't start, log "Backend failed to start" and set `backend_up = false`.

- If frontend is **down**: start it in background:
  ```bash
  cd frontend && npm run dev
  ```
  Wait up to 15 seconds for port 5173 to become available. If it doesn't start, log "Frontend failed to start" and set `frontend_up = false`.

- If both are already running: proceed silently.

### 2. Run pytest (Python backend tests)

```bash
pytest --timeout=120 -v 2>&1
```

- Run from project root.
- Capture the exit code, total tests, passed, failed counts.
- Timeout: 2 minutes max. If pytest hangs, kill it and record as "TIMEOUT".
- Do NOT stop if tests fail — continue to step 3.

### 3. Run vitest (React unit tests)

```bash
cd frontend && npx vitest run 2>&1
```

- Capture the exit code, total tests, passed, failed counts.
- Timeout: 2 minutes max. If vitest hangs, kill it and record as "TIMEOUT".
- Do NOT stop if tests fail — continue to step 4.

### 4. Run Playwright (e2e tests)

**Pre-check:** If `frontend_up` is false (frontend failed to start in step 1), skip Playwright and record as "SKIPPED — frontend not running".

```bash
cd frontend && npx playwright test 2>&1
```

- Playwright config uses `reuseExistingServer: true`, so it will use the already-running dev server.
- Capture the exit code, total tests, passed, failed counts.
- Timeout: 3 minutes max (e2e tests are slower).
- If Playwright hangs, kill it and record as "TIMEOUT".

### 5. Print combined summary

Output a clean summary in this exact format:

```
Test Pipeline Results
=====================

  pytest:      ✓ PASSED  (X passed, Y failed, Z total)
  vitest:      ✗ FAILED  (X passed, Y failed, Z total)
  playwright:  ✓ PASSED  (X passed, Y failed, Z total)

  Overall: 2/3 suites passed
```

Use `✓ PASSED` for passing suites, `✗ FAILED` for failures, `⏱ TIMEOUT` for timeouts, `⊘ SKIPPED` for skipped.

If all suites pass, add: `All tests green!`
If any suite fails, add: `Fix failing tests before committing.`

## Notes

- **Always run all three suites** regardless of individual failures. The point is a combined report.
- **Never skip pytest or vitest.** Only Playwright can be skipped (if services won't start).
- **Timeouts are hard limits.** pytest/vitest get 2 minutes each, Playwright gets 3 minutes. Kill hung processes rather than waiting indefinitely.
- **Do not install dependencies.** If pytest, vitest, or playwright are not installed, report the error. Do not auto-install.
- **Do not modify any test files.** This skill only runs tests, never changes them.
- **Start backend before frontend** if both need starting — the frontend proxies API calls to the backend.
