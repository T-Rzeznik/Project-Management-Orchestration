---
name: current-development
description: Use when someone asks about project status, where we are in development, what's been built, what's the current state of the project, what features exist, or where are we in the build.
---

## What This Skill Does

Scans the codebase across both stacks (Python backend + React frontend) to produce a feature inventory. Shows what's complete, what's in progress, and what's still TODO. Then suggests prioritized next steps.

**This skill is read-only. It never modifies files, runs tests, or starts services.**

## Steps

### 1. Gather context from git

Run this to find the last tag and count commits since:

```bash
git tag --sort=-creatordate | head -5
git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~20)..HEAD 2>/dev/null || git log --oneline -20
```

This anchors the "since last release" framing. If no tags exist, use the last 20 commits as the window.

### 2. Scan backend (Python)

Read these key files using the Read tool. Do these reads in parallel where possible:

**API layer:**
- `api/server.py` — list all endpoints (routes, methods, what they do)
- `api/models.py` — list all Pydantic models and their fields
- `api/storage.py` — note the persistence mechanism

**Framework core:**
- Glob `framework/*.py` — list all modules and note which ones appear complete vs stubbed
- Glob `tools/*.py` — list all tool implementations

**Agents:**
- Glob `agents/*.yaml` — list all agent definitions, note their purpose and model

**Tests:**
- Glob `tests/*.py` — list test files and note which modules have test coverage

For each area, classify as:
- **Complete** — functional implementation with meaningful logic
- **In progress** — partial implementation, has TODOs, or missing key pieces
- **Stubbed** — file exists but is mostly placeholder/boilerplate

### 3. Scan frontend (React + TypeScript)

Read these key files using the Read tool. Do these reads in parallel where possible:

**Routing & entry:**
- `frontend/src/App.tsx` — list all routes and pages

**Components:**
- Glob `frontend/src/components/*.tsx` (exclude `*.test.tsx`) — list all components and their purpose

**API client:**
- `frontend/src/api.ts` — list all API functions and which endpoints they call

**Types:**
- `frontend/src/types.ts` — list shared type definitions

**Tests:**
- Glob `frontend/src/components/*.test.tsx` — note which components have test coverage
- Glob `frontend/e2e/*.spec.ts` — note which e2e scenarios exist

Classify each component/page the same way: Complete, In progress, or Stubbed.

### 4. Scan for TODOs and FIXMEs

Use Grep to search across the codebase:

```
pattern: TODO|FIXME|HACK|XXX
```

Group findings by file/area. These signal incomplete work.

### 5. Print the report

Output the report in this format:

```
Project Status Report
=====================

Last tag: [tag or "none"]
Commits since: [N]

## Backend (Python)

### API Endpoints
| Endpoint            | Method | Status     |
|---------------------|--------|------------|
| /api/projects       | GET    | Complete   |
| /api/analyze        | POST   | In progress|

### Framework Modules
| Module              | Status     | Notes              |
|---------------------|------------|--------------------|
| orchestrator.py     | Complete   |                    |
| agent.py            | Complete   |                    |

### Agents
| Agent               | Model      | Status     |
|---------------------|------------|------------|
| coder.yaml          | claude-... | Complete   |

### Tools
| Tool                | Status     |
|---------------------|------------|
| bash_tool.py        | Complete   |

### Test Coverage
| Test File              | Covers            |
|------------------------|--------------------|
| test_chat_api.py       | api/server.py      |

---

## Frontend (React)

### Pages & Routes
| Route               | Component          | Status     |
|---------------------|--------------------|------------|
| /                   | ProjectDashboard   | Complete   |

### Components
| Component            | Status     | Has Tests? |
|----------------------|------------|------------|
| ChatPanel.tsx        | Complete   | Yes        |

### API Client Functions
| Function             | Endpoint           | Status     |
|----------------------|--------------------|------------|
| fetchProjects()      | GET /api/projects  | Complete   |

---

## Outstanding TODOs
- [file:line] TODO message
- [file:line] FIXME message

---

## Suggested Next Steps
1. [highest priority suggestion]
2. [next suggestion]
3. [next suggestion]
```

### 6. Suggest next steps

Based on the scan, suggest 3-5 prioritized next steps. Prioritize in this order:

1. **Broken or missing fundamentals** — missing API endpoints, broken imports, stubbed core modules
2. **Incomplete features** — features that are partially built but not functional end-to-end
3. **Missing tests** — components or modules with no test coverage
4. **TODOs and FIXMEs** — outstanding items flagged in the code
5. **Polish and optimization** — nice-to-haves, cleanup, refactoring

Be specific: name the file, component, or feature. Don't give vague advice.

## Notes

- **Read-only.** Never modify, create, or delete any files. This skill only reads and reports.
- **Be fast.** Read key structural files only. Do not read every file in the repo — focus on entry points, exports, and index files.
- **Use parallel reads.** Read multiple files at the same time when they don't depend on each other.
- **Don't run tests.** Use `/test-playwright` for that. This skill only checks if test files exist.
- **Don't start services.** Use `/dev` for that.
- **Classify honestly.** If something is incomplete, say so. Don't call a stub "complete" just because the file exists.
- **Keep the report scannable.** Use tables and short phrases, not paragraphs.
