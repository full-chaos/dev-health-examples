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
  
  // This is required to force the provider to delete the project immediately
  // instead of moving it to the trash (which requires manual intervention to clear).
  // Note: This feature is specific to the fourplusone/jira provider.
  delete_permanently = true
}
