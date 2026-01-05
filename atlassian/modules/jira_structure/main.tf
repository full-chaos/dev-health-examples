terraform {
  required_providers {
    jira = {
      source = "fourplusone/jira"
    }
  }
}

variable "project_lead_account_id" {
  description = "Account ID of the project lead"
  type        = string
}

variable "project_template_key" {
  description = "The template key for the Jira projects"
  type        = string
  default     = "com.pyxis.greenhopper.jira:gh-simplified-agility-scrum"
}

resource "jira_project" "projects" {
  for_each = toset(["CORE", "PLAT", "DATA", "INFR", "SECU", "MOBI", "WEBX", "INTG", "PAY", "SRE"])

  key                  = each.key
  name                 = "Project ${each.key}"
  project_type_key     = "software"
  project_template_key = var.project_template_key
  lead_account_id      = var.project_lead_account_id
}

output "project_keys" {
  value = [for p in jira_project.projects : p.key]
}
