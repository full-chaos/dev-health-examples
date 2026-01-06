output "project_keys" {
  description = "List of created Jira project keys"
  value       = [for p in jira_project.projects : p.key]
}
