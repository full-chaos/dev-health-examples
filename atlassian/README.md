# Atlassian Demo Data Seeder

This module provisions Atlassian structure (Jira projects, Ops teams/schedules) and invokes a deterministic seeder to generate narrative-shaped demo data for Developer Health analytics.

## What this creates

- 10 Jira Software projects
- 10 Ops teams with weekly on-call rotations
- ~12k Jira issues across 24 months
- Incidents + postmortem follow-ups (labeled and linked)
- Sprint history and spillover (when Agile APIs are available)
- `out/manifest.json` with distribution summaries

## Requirements

- Jira Cloud + Jira Software
- Atlassian Ops (JSM Ops/On-call) access for the same site
- API token with project admin access
- Python 3 with `pip3` (PyYAML and requests will be auto-installed by Terraform)

## Environment variables

Set the following via `terraform.tfvars` or environment variables:

- `jira_url` (e.g. `https://your-domain.atlassian.net`)
- `jira_user` (email)
- `jira_token`
- `atlassian_cloud_id`
- `atlassian_domain`
- `atlassian_org_id`
- `project_lead_account_id` (optional; defaults to current admin user)
- `enable_project_creation` (optional; set to false if projects already exist)
- `team_member_account_ids` (list; optional)
- `generated_user_count` (optional)
- `generated_user_domain` (optional)
- `enable_user_creation` (optional)

Optional toggles:

- `enable_issue_creation` (default `false` - set to `true` to create issues)
- `enable_sprints` (default `true`)
- `enable_transitions` (default `true`)
- `disable_incidents` (default `false` - set to `true` to skip incidents)
- `enable_comments` (default `false`)

## Usage

```bash
cd atlassian
terraform init
terraform apply
```

To run in dry-run mode (manifest only):

```hcl
# terraform.tfvars
# enable_issue_creation defaults to false, so dry-run is the default behavior
# To actually create issues, set:
enable_issue_creation = true
```

## Reset / destroy

```bash
terraform destroy
```

The seeder is idempotent for issues: it uses a deterministic external id stored as a label (`extid-<hash>`). Re-running `terraform apply` skips previously seeded issues.

## Rate limits and retries

The seeder retries failed API calls up to 3 times with a short sleep. If you hit rate limits, re-run `terraform apply` after a few minutes.

## Permissions needed

- Project admin for Jira project creation
- Issue create + transition for Jira and JSM projects
- Ops team and schedule management access

## Notes on timestamps

Jira Cloud does not allow backdating `created`/`resolved` without import permissions. This seeder stores simulated timestamps in the issue property `seed_meta` and in `out/manifest.json` for analytics.

## Files

- `seed/story_map.yaml` controls project/team mapping and arc distributions
- `seed/seed_jira.py` contains the deterministic data generator
- `out/manifest.json` is produced after seeding
