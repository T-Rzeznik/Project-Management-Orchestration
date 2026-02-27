---
name: commit-push
description: Use when someone asks to commit and push, push changes, push to main, commit my work, or ship it.
---

## What This Skill Does

Analyzes the current git diff, runs tests, generates a commit message, and pushes to main — with safety checks and user confirmation.

## Steps

### 1. Check for changes

Run `git status` (never use `-uall`). If there are no staged or unstaged changes AND no unpushed commits, report "Nothing to commit or push." and stop.

### 2. Scan for secrets

Before staging, check for files that should never be committed:
- `.env`, `.env.*` files
- Files containing API keys, tokens, or credentials (e.g., `credentials.json`, `*.pem`, `*.key`)
- Any file matching patterns in `.gitignore` that got force-added

If any sensitive files are found in the changes, **stop immediately** and warn the user. List the offending files. Do NOT proceed.

### 3. Run tests

Run both test suites. If either fails, stop and report the failures. Do not commit.

```bash
# Python tests
pytest

# Frontend tests
cd frontend && npx vitest run
```

If tests pass, continue.

### 4. Stage all changes

```bash
git add -A
```

### 5. Generate commit message

Run `git diff --cached` and `git diff --cached --stat` to analyze what changed. Write a commit message following these rules:
- Simple imperative style (e.g., "Add login page", "Fix null pointer in auth flow")
- First line under 72 characters
- Add a blank line and body paragraph only if the changes are complex enough to warrant explanation
- No Co-Authored-By tag
- Focus on the "why" not the "what" when possible

### 6. Show summary and confirm

Present this to the user before pushing:

```
## Commit Summary

**Message:** [the generated commit message]

**Files changed:**
[output of git diff --cached --stat]

**Target:** origin/main
```

Then ask: "Push to main?" — wait for explicit user confirmation. Do NOT push without it.

### 7. Commit and push

Only after user confirms:

```bash
git commit -m "$(cat <<'EOF'
[commit message here]
EOF
)"
git push origin main
```

Run `git status` after push to verify success. Report the result.

## Notes

- If on a branch other than `main`, warn the user and ask if they want to push to their current branch instead.
- If `git push` is rejected (e.g., remote has new commits), report the error. Do NOT force push. Suggest `git pull --rebase` instead.
- Never use `--force`, `--no-verify`, or `--no-gpg-sign` unless the user explicitly requests it.
- Never amend existing commits — always create new ones.
- If pre-commit hooks fail, fix the issue and create a new commit rather than bypassing hooks.
