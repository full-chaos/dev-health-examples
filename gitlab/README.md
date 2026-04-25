# GitLab Demo Data Seeder

This module provisions GitLab structure and invokes a deterministic seeder to generate narrative-shaped GitLab fixture data for Developer Health analytics.

## What this creates

- 1 GitLab group
- 10 GitLab projects mirroring the Atlassian fixture project set
- GitLab issues across a 24-month timeline
- Merge requests with reviewers, optional comments, and fixture commits
- CI pipeline triggers backed by a generated `.gitlab-ci.yml` with build/test/security/deploy stages and jobs
- Tags and releases aligned to story arcs
- `out/manifest.json` with distribution summaries, pipeline success/failure rates, and Investment View theme counts

## Requirements

- GitLab.com or self-managed GitLab with API access
- Personal access token with `api` scope
- Python 3 with `pip3`
- Terraform provider `gitlabhq/gitlab`

## Environment variables

The seeder reads authentication from environment variables:

- `GITLAB_TOKEN` — GitLab personal access token (required outside `--dry-run`)
- `GITLAB_BASE_URL` — GitLab API URL (optional, default `https://gitlab.com/api/v4`)
- `GITLAB_GROUP_PATH` — target group path for direct seeder runs (optional, default `dev-health-demo`)
- `GITLAB_REVIEWERS` — comma-separated usernames eligible for MR reviews (optional)

Terraform equivalents:

- `gitlab_token`
- `gitlab_base_url`
- `group_name`
- `enable_group_creation`
- `enable_project_creation`
- `enable_seed_creation` (default `false`, so Terraform runs the seeder in dry-run mode)
- `reviewer_usernames`

Optional toggles:

- `enable_comments` (default `false`)
- `enable_pipelines` (default `true`)
- `enable_merge_requests` (default `true`)
- `enable_releases` (default `true`)

## Usage

```bash
cd gitlab
terraform init
terraform apply
```

Dry-run is the default in Terraform (`enable_seed_creation = false`). To create GitLab data:

```hcl
gitlab_token         = "..."
gitlab_base_url      = "https://gitlab.com/api/v4"
group_name           = "Dev Health Demo"
enable_seed_creation = true
reviewer_usernames   = ["alice", "bob"]
```

Run the seeder directly in dry-run mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r gitlab/seed/requirements.txt
python gitlab/seed/seed_gitlab.py --dry-run
```

Run the seeder directly against GitLab:

```bash
export GITLAB_TOKEN="..."
export GITLAB_BASE_URL="https://gitlab.com/api/v4"
python gitlab/seed/seed_gitlab.py \
  --group-path dev-health-demo \
  --reviewers alice,bob \
  --enable-comments
```

## Story map

`seed/story_map.yaml` defines the 24-month narrative arcs:

- Launch
- Scale
- Reliability Crunch
- Recovery
- Roadmap Reset

Each arc includes Investment View canonical theme mix (`Feature Delivery`, `Operational / Support`, `Maintenance / Tech Debt`, `Quality / Reliability`, `Risk / Security`), issue mix, merge request behavior, and pipeline success/failure rates.

## Idempotency and timestamps

The seeder uses deterministic external IDs (`extid::<hash>`) derived from the story map, project, month, and work type. Re-runs skip existing seeded issues by label. GitLab does not generally allow arbitrary historical pipeline/job timestamps through public APIs, so simulated dates and arc metadata are stored in labels, descriptions, and `out/manifest.json`; live GitLab resources are created at run time.

## Reset / destroy

```bash
terraform destroy
```

Destroy removes Terraform-managed groups/projects. The Python seeder does not independently delete issues, merge requests, pipelines, or releases inside projects.
