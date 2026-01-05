variable "jira_url" {
  description = "Base URL for Jira instance (e.g., https://your-domain.atlassian.net)"
  type        = string
}

variable "jira_user" {
  description = "Email address for Jira authentication"
  type        = string
}

variable "jira_token" {
  description = "API Token for Jira authentication"
  type        = string
  sensitive   = true
}

variable "atlassian_cloud_id" {
  description = "The Cloud ID of the Atlassian site (required for atlassian-operations provider)"
  type        = string
  default     = ""
}

variable "atlassian_domain" {
  description = "The subdomain of the Atlassian site (e.g. 'chrisgeorge' for 'chrisgeorge.atlassian.net')"
  type        = string
  default     = ""
}

variable "atlassian_org_id" {
  description = "The Organization ID (required for team creation in atlassian-operations)"
  type        = string
  default     = ""
}

variable "seed_random_state" {
  description = "String to seed the deterministic generator"
  type        = string
  default     = "full-chaos-dev-health"
}

variable "generated_user_count" {
  description = "Number of random users to generate"
  type        = number
  default     = 5
}

variable "generated_user_domain" {
  description = "Domain for generated users email addresses"
  type        = string
  default     = "example.com"
}

variable "enable_user_creation" {
  description = "Set to true to provision generated users in Jira (requires appropriate permissions/non-SSO)"
  type        = bool
  default     = false
}

variable "project_template_key" {
  description = "The template key for the Jira projects"
  type        = string
  default     = "com.pyxis.greenhopper.jira:gh-simplified-agility-scrum"
}

variable "enable_schedules" {
  description = "Set to true to provision OpsGenie/Atlassian Operations schedules and rotations"
  type        = bool
  default     = false
}

variable "enable_issue_creation" {
  description = "Set to false to run the seeder in dry-run mode (no Jira issues created)"
  type        = bool
  default     = true
}
