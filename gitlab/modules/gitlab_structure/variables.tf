variable "group_name" {
  type        = string
  description = "GitLab group display name"
}

variable "group_path" {
  type        = string
  description = "GitLab group URL path"
}

variable "project_map" {
  type        = map(string)
  description = "Map of GitLab project path to display name"
}

variable "enable_group_creation" {
  type        = bool
  description = "Enable GitLab group creation"
  default     = true
}

variable "enable_project_creation" {
  type        = bool
  description = "Enable GitLab project creation"
  default     = true
}

variable "project_visibility" {
  type        = string
  description = "Visibility level for generated projects"
  default     = "private"
}
