variable "gitlab_token" {
  type        = string
  description = "GitLab personal access token with API scope"
  sensitive   = true
}

variable "gitlab_base_url" {
  type        = string
  description = "GitLab API base URL, e.g. https://gitlab.com/api/v4 or https://gitlab.example.com/api/v4"
  default     = "https://gitlab.com/api/v4"
}

variable "group_name" {
  type        = string
  description = "Top-level GitLab group name for seeded demo data"
  default     = "Dev Health Demo"
}

variable "enable_group_creation" {
  type        = bool
  description = "Enable GitLab group creation (disable if the group already exists)"
  default     = true
}

variable "enable_project_creation" {
  type        = bool
  description = "Enable GitLab project creation (disable if projects already exist)"
  default     = true
}

variable "project_visibility" {
  type        = string
  description = "Visibility level for generated projects"
  default     = "private"

  validation {
    condition     = contains(["private", "internal", "public"], var.project_visibility)
    error_message = "project_visibility must be private, internal, or public."
  }
}

variable "enable_seed_creation" {
  type        = bool
  description = "Toggle to create GitLab data (false = dry-run manifest only)"
  default     = false
}

variable "seed_string" {
  type        = string
  description = "Deterministic seed input"
  default     = "dev-health-demo"
}

variable "batch_size" {
  type        = number
  description = "API batch pacing size"
  default     = 50
}

variable "provision_start_date" {
  type        = string
  description = "Override the provisioned data start date (ISO-8601, e.g. 2024-01-31)"
  default     = ""
}

variable "provision_end_date" {
  type        = string
  description = "Override the provisioned data end date (ISO-8601, e.g. 2025-12-31). Defaults to today if unset."
  default     = ""
}

variable "monthly_issue_count" {
  type        = number
  description = "Override issues created per project per month (0 = use story map defaults, max 10000)"
  default     = 0

  validation {
    condition     = var.monthly_issue_count >= 0 && var.monthly_issue_count <= 10000
    error_message = "monthly_issue_count must be between 0 and 10000."
  }
}

variable "reviewer_usernames" {
  type        = list(string)
  description = "GitLab usernames eligible for MR reviewers"
  default     = []
}

variable "enable_comments" {
  type        = bool
  description = "Create comments/notes on a subset of issues and merge requests"
  default     = false
}

variable "enable_pipelines" {
  type        = bool
  description = "Trigger pipelines from seeded branches when CI config exists"
  default     = true
}

variable "enable_merge_requests" {
  type        = bool
  description = "Create seeded merge requests"
  default     = true
}

variable "enable_releases" {
  type        = bool
  description = "Create seeded tags and releases"
  default     = true
}
