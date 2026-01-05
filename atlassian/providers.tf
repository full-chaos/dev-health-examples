provider "jira" {
  url      = var.jira_url
  user     = var.jira_user
  password = var.jira_token
}

provider "atlassian-operations" {
  cloud_id      = var.atlassian_cloud_id
  domain_name   = var.atlassian_domain
  email_address = var.jira_user
  token         = var.jira_token
}