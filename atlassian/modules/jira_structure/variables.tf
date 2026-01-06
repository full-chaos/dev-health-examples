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
