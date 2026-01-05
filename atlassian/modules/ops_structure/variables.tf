variable "organization_id" {
  type        = string
  description = "Atlassian org id"
}

variable "team_names" {
  type        = list(string)
  description = "Team display names"
}

variable "user_ids" {
  type        = list(string)
  description = "Account IDs available for team membership"
  default     = []
}

variable "admin_user_id" {
  type        = string
  description = "Fallback account ID used when no team members are provided"
}

variable "enable_schedules" {
  type        = bool
  description = "Enable schedule + rotation creation"
  default     = true
}

variable "schedule_timezone" {
  type        = string
  description = "Timezone for on-call schedules"
  default     = "America/New_York"
}
