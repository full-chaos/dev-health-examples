variable "jira_url" {
  type        = string
  description = "Base URL for Jira Cloud, e.g. https://your-domain.atlassian.net"
}

variable "jira_user" {
  type        = string
  description = "Jira user email"
}

variable "jira_token" {
  type        = string
  description = "Jira API token"
  sensitive   = true
}

variable "atlassian_cloud_id" {
  type        = string
  description = "Atlassian cloud id for Ops provider"
  
  validation {
    condition     = var.atlassian_cloud_id != ""
    error_message = "The atlassian_cloud_id is required when using Ops features."
  }
}

variable "atlassian_domain" {
  type        = string
  description = "Atlassian domain (your-domain.atlassian.net)"
  
  validation {
    condition     = var.atlassian_domain != ""
    error_message = "The atlassian_domain is required when using Ops features."
  }
}

variable "atlassian_org_id" {
  type        = string
  description = "Atlassian org id for Ops team creation"
  
  validation {
    condition     = var.atlassian_org_id != ""
    error_message = "The atlassian_org_id is required when using Ops features."
  }
}

variable "project_lead_account_id" {
  type        = string
  description = "Account ID used as Jira project lead"
  default     = ""
}

variable "enable_project_creation" {
  type        = bool
  description = "Enable Jira project creation (disable if projects already exist)"
  default     = true
}

variable "team_member_account_ids" {
  type        = list(string)
  description = "Account IDs eligible for Ops team membership"
  default     = []
}

variable "generated_user_count" {
  type        = number
  description = "Number of synthetic users to generate"
  default     = 5
}

variable "generated_user_domain" {
  type        = string
  description = "Email domain used for synthetic users"
  default     = "example.com"
}

variable "enable_user_creation" {
  type        = bool
  description = "Enable Jira user creation"
  default     = false
}

variable "enable_schedules" {
  type        = bool
  description = "Enable Ops schedules/rotations"
  default     = false
}

variable "schedule_timezone" {
  type        = string
  description = "Timezone for on-call schedules"
  default     = "America/New_York"
}

variable "enable_issue_creation" {
  type        = bool
  description = "Toggle to create Jira issues (false = dry-run with manifest only)"
  default     = false
}

variable "seed_string" {
  type        = string
  description = "Deterministic seed input"
  default     = "dev-health-demo"
}

variable "batch_size" {
  type        = number
  description = "Bulk issue batch size"
  default     = 50
}

variable "assignee_emails" {
  type        = list(string)
  description = "List of emails to resolve for assignees"
  default     = []
}

variable "enable_sprints" {
  type        = bool
  description = "Create sprints/boards and assign issues when possible"
  default     = true
}

variable "enable_transitions" {
  type        = bool
  description = "Attempt to transition issues through workflows"
  default     = true
}

variable "enable_comments" {
  type        = bool
  description = "Create comments on a subset of issues"
  default     = false
}

variable "disable_incidents" {
  type        = bool
  description = "Disable JSM incidents + postmortem follow-ups"
  default     = false
}
