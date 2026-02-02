# AGENTS.md — dev-health-examples

> **Canonical Reference:** See [`/AGENTS.md`](../AGENTS.md) for the unified Dev Health platform agent briefing.

## Project Overview
This repository (`dev-health-examples`) contains automation tools to seed realistic data into Atlassian Cloud environments (Jira Software, Jira Service Management). It is designed to generate a synthetic 2-year history of software development activity to demonstrate "Developer Health" patterns.

## Key Components

### 1. Infrastructure (Terraform)
*   **Directory:** `atlassian/`
*   **Purpose:** Provisions the structural resources in Atlassian.
*   **Main Files:**
    *   `main.tf`: Orchestrates modules and triggers the seeding script.
    *   `variables.tf`: Configuration (URL, credentials, seed hash).
    *   `users.tf`: Generates random users/emails (using `random_pet`).
*   **Modules:**
    *   `modules/jira_structure`: likely sets up Jira Projects.
    *   `modules/ops_structure`: likely sets up OpsGenie or JSM Teams/Schedules.

### 2. Data Seeder (Python)
*   **Directory:** `atlassian/seed/`
*   **Script:** `seed_jira.py`
*   **Configuration:** `story_map.yaml` defines the "Narrative Arcs" (e.g., Launch, Scale, Reliability Crunch).
*   **Behavior:**
    *   Runs as a `local-exec` provisioner from Terraform.
    *   Authenticates to Jira.
    *   Generates ~12,000 issues across a 24-month timeline.
    *   Supports "MOCK MODE" if invalid URLs are provided.
    *   Assigns issues to users (either real or generated).
    *   Outputs a `manifest.json` with statistics.

## Usage Context
*   **Primary Workflow:** `terraform apply` in `atlassian/` triggers the entire process.
*   **Data Shape:** The data is not random; it follows specific phases defined in `story_map.yaml` to simulate real-world team challenges (e.g., a spike in bugs during a "Reliability Crunch").

## Important Notes for Agents
*   **NEVER commit directly to main** — Always create a feature branch first:
    ```bash
    git checkout -b <type>/<descriptive-name>  # e.g., fix/seed-script, feat/new-arc
    ```
*   **Use git worktrees for parallel work** — When starting a new feature or unrelated task, use a worktree:
    ```bash
    git worktree add ../dev-health-examples-feature-name feature/branch-name
    ```
    This keeps each task isolated, preventing cross-contamination of changes.
*   **Mock Mode:** The Python script has a `MOCK_MODE` variable. If you see it skipping API calls, check the provided URL.
*   **Destruction:** `terraform destroy` removes the structure (Projects/Teams) but the Python script does NOT clean up the individual issues it created inside those projects (projects must be deleted).

---

## Task Tracking (bd + GitHub)

> **Canonical Reference:** See [`/AGENTS.md`](../AGENTS.md#11-task-tracking-bd--github) for full documentation.

**Project Board:** `https://github.com/orgs/full-chaos/projects/1`

### Quick Reference

```bash
# bd (local task tracking)
bd create "Task title" --priority P2 --external-ref gh-123
bd list --status open
bd status <id> in-progress
bd status <id> done
bd dep add <child-id> <parent-id> --type parent-child
bd sync

# GitHub issues (use labels, not --type)
gh issue create --title "Title" --body "Description" --label task
gh issue edit NNN --add-project "https://github.com/orgs/full-chaos/projects/1"
```

### Workflow

1. Create bd issue with `--external-ref gh-NNN` to link to GitHub
2. Update bd status during work
3. Run `bd sync` before `git push`
4. Close GitHub issue when complete

---

## Session Completion

**When ending a work session**, you MUST:

1. **File issues** for remaining work
2. **Run quality gates** (tests, linters)
3. **Update issue status** (close finished, update in-progress)
4. **PUSH TO REMOTE** (mandatory):
   ```bash
   git pull --rebase && bd sync && git push && git status
   ```
5. **Hand off** context for next session

**Work is NOT complete until `git push` succeeds.**

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
