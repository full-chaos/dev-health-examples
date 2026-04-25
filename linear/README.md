# Linear Demo Data Seeder

This module seeds deterministic Linear fixture data for Developer Health analytics. It mirrors the `atlassian/` fixture pattern: Terraform orchestrates a local Python seeder, while the seeder writes teams, projects, cycles, issues, comments, and `out/manifest.json` via the Linear GraphQL API.

## Terraform support

Linear does not maintain an official Terraform provider. A community provider exists, but its resource coverage and maintenance cadence may not match the fixture needs. This module therefore uses Terraform only as an orchestrator (`null_resource` + `local-exec`) and performs Linear writes through `seed/seed_linear.py`.

## Requirements

- Python 3.10+
- Terraform (optional, for orchestration)
- Linear personal API key with permission to create teams/projects/issues

## Environment variables

- `LINEAR_API_KEY` — required for real writes. Pass the raw API key in the `Authorization` header value; do not prefix it with `Bearer`.

## Dry run

Dry run is the default Terraform behavior and does not require `LINEAR_API_KEY`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r linear/seed/requirements.txt
python linear/seed/seed_linear.py --dry-run
```

The dry run creates `linear/out/manifest.json` with deterministic counts and samples but performs no API writes.

## Terraform usage

```bash
cd linear
terraform init
terraform apply
```

To perform real writes:

```hcl
# terraform.tfvars
linear_api_key        = "lin_api_..."
```

Optional toggles:

- `enable_issue_creation` (default `false`): when false, runs `--dry-run`
- `enable_cycles` (default `true`): create two-week cycles for each seeded team
- `enable_comments` (default `true`): create deterministic comments on a subset of issues
- `monthly_issue_count` (default `0`): override issue volume per team per month
- `assignee_emails`: optional Linear user emails for deterministic assignment
- `provision_start_date` / `provision_end_date`: override the 24-month date range

## Direct seeder usage

```bash
export LINEAR_API_KEY="lin_api_..."
python linear/seed/seed_linear.py \
  --story linear/seed/story_map.yaml \
  --manifest linear/out/manifest.json \
  --seed dev-health-linear-demo
```

## Idempotency and timestamps

The seeder uses stable hashes in issue titles (`[<external_id>]`) and checks for existing issues before writing. Linear does not support backdating issue creation timestamps through normal GraphQL mutations, so simulated historical dates are encoded in issue descriptions, due dates, cycles, and the manifest.

## Investment View themes

`seed/story_map.yaml` uses the canonical Investment View themes only:

- Feature Delivery
- Operational / Support
- Maintenance / Tech Debt
- Quality / Reliability
- Risk / Security
