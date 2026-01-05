# AGENTS.md

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
*   **Mock Mode:** The Python script has a `MOCK_MODE` variable. If you see it skipping API calls, check the provided URL.
*   **Destruction:** `terraform destroy` removes the structure (Projects/Teams) but the Python script does NOT clean up the individual issues it created inside those projects (projects must be deleted).
