output "project_keys" {
  value = module.jira_structure.project_keys
}

output "ops_team_ids" {
  value = module.ops_structure.ops_team_ids
}

data "local_file" "manifest" {
  filename   = "${path.module}/out/manifest.json"
  depends_on = [null_resource.seed]
}

output "sprints" {
  description = "Map of sprints created per project"
  value       = jsondecode(data.local_file.manifest.content).sprints
}