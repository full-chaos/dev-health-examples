variable "user_ids" {
  description = "List of Atlassian Account IDs to assign to teams"
  type        = list(string)
  default     = []
}

variable "organization_id" {
  description = "Atlassian Organization ID (required for team creation)"
  type        = string
}

variable "enable_schedules" {
  description = "Enable creation of On-call schedules (defaults to false)"
  type        = bool
  default     = false
}
