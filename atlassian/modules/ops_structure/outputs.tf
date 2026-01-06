output "ops_team_ids" {
  description = "List of created Operations team IDs"
  value       = atlassian-operations_team.teams[*].id
}
