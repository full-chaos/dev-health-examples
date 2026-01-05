terraform {
  required_providers {
    jira = {
      source = "fourplusone/jira"
    }
  }
}

variable "project_lead_account_id" {
  type        = string
  description = "Account ID of the project lead"
}

variable "project_template_key" {
  type        = string
  description = "Jira project template key"
  default     = "com.pyxis.greenhopper.jira:gh-simplified-agility-scrum"
}

variable "project_map" {
  type        = map(string)
  description = "Map of project key to display name"
}

variable "enable_project_creation" {
  type        = bool
  description = "Enable Jira project creation"
  default     = true
}

resource "jira_project" "projects" {
  for_each = var.enable_project_creation ? var.project_map : {}

  key                  = each.key
  name                 = "${each.value} (${each.key})"
  project_type_key     = "software"
  project_template_key = var.project_template_key
  lead_account_id      = var.project_lead_account_id
}

output "project_keys" {
  value = [for p in jira_project.projects : p.key]
}
