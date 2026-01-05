# Atlassian Data Seeder

This module provisions Atlassian resources (Teams, Projects) and populates them with realistic sample data for the Developer Health Platform.

## Prerequisites

- Terraform >= 1.5
- Python >= 3.9
- An Atlassian Cloud site (Jira Software + Jira Service Management)

## Usage

1. **Configure Variables**:
   Create a `terraform.tfvars` file or use environment variables.

   ```hcl
   jira_url   = "https://your-site.atlassian.net"
   jira_user  = "admin@example.com"
   jira_token = "ATATT3xFfGF0..." # Your API Token
   ```

2. **Init & Apply**:
   ```bash
   cd infra/atlassian_seed
   terraform init
   terraform apply
   ```

3. **What happens**:
   - Terraform creates a basic structure.
   - The `seed_jira.py` script runs, authenticating to your Jira instance.
   - ~12,000 issues are generated across 10 projects, following a 24-month narrative arc.
   - A `manifest.json` is generated in `infra/atlassian_seed/manifest.json`.

## Narrative Arcs

The data follows 5 phases:
1. **Launch**: Feature-heavy.
2. **Scale**: Maintenance rises.
3. **Reliability Crunch**: Incidents spike (Months 13-16).
4. **Recovery**: Refactoring.
5. **Roadmap Reset**: Balanced state.

## Cleaning Up

To remove generated configuration (Projects/Teams), run:
```bash
terraform destroy
```
*Note: The Python seeder does not delete issues on destroy. You must delete the projects manually or via bulk delete.*
