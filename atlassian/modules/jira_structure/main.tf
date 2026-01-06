terraform {
  required_providers {
    jira = {
      source = "fourplusone/jira"
    }
  }
}

resource "jira_project" "projects" {
  for_each = var.enable_project_creation ? var.project_map : {}

  key                  = each.key
  name                 = "${each.value} (${each.key})"
  project_type_key     = "software"
  project_template_key = var.project_template_key
  lead_account_id      = var.project_lead_account_id
}
