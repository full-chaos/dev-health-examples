variable "linear_api_key" {
  type        = string
  description = "Linear personal API key. Used directly in the Authorization header; do not prefix with Bearer."
  sensitive   = true
  default     = ""
}

variable "enable_issue_creation" {
  type        = bool
  description = "Toggle to create Linear data (false = dry-run with manifest only)."
  default     = false
}

variable "enable_comments" {
  type        = bool
  description = "Create comments on a deterministic subset of seeded issues."
  default     = true
}

variable "enable_cycles" {
  type        = bool
  description = "Create historical two-week cycles for each seeded Linear team."
  default     = true
}

variable "seed_string" {
  type        = string
  description = "Deterministic seed input."
  default     = "dev-health-linear-demo"
}

variable "batch_size" {
  type        = number
  description = "Issue creation batch size. Linear does not expose a bulk issue mutation, so this controls progress logging cadence."
  default     = 25
}

variable "provision_start_date" {
  type        = string
  description = "Override the provisioned data start date (ISO-8601, e.g. 2024-01-01)."
  default     = ""
}

variable "provision_end_date" {
  type        = string
  description = "Override the provisioned data end date (ISO-8601, e.g. 2025-12-31). Defaults to today if unset."
  default     = ""
}

variable "monthly_issue_count" {
  type        = number
  description = "Override the total issues created per team per month (0 = use story map defaults, max 1000)."
  default     = 0

  validation {
    condition     = var.monthly_issue_count >= 0 && var.monthly_issue_count <= 1000
    error_message = "monthly_issue_count must be between 0 and 1000."
  }
}

variable "assignee_emails" {
  type        = list(string)
  description = "Optional Linear user emails eligible for deterministic issue assignment."
  default     = []
}
