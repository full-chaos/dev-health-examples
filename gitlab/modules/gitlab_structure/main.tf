terraform {
  required_providers {
    gitlab = {
      source = "gitlabhq/gitlab"
    }
  }
}

resource "gitlab_group" "demo" {
  count = var.enable_group_creation ? 1 : 0

  name        = var.group_name
  path        = var.group_path
  description = "Seeded group for developer health demo"
  visibility_level = "private"
}

data "gitlab_group" "existing" {
  count = var.enable_group_creation ? 0 : 1

  full_path = var.group_path
}

locals {
  group_id   = var.enable_group_creation ? gitlab_group.demo[0].id : data.gitlab_group.existing[0].id
  group_path = var.enable_group_creation ? gitlab_group.demo[0].full_path : data.gitlab_group.existing[0].full_path
}

resource "gitlab_project" "projects" {
  for_each = var.enable_project_creation ? var.project_map : {}

  name             = each.value
  path             = each.key
  namespace_id     = local.group_id
  description      = "Seeded ${each.value} project for developer health demo"
  visibility_level = var.project_visibility
  initialize_with_readme = true
}

output "group_id" {
  description = "GitLab group id used for seeded projects"
  value       = local.group_id
}

output "group_path" {
  description = "GitLab group full path used by the seeder"
  value       = local.group_path
}

output "project_paths" {
  description = "Full paths for projects created by Terraform"
  value = var.enable_project_creation ? {
    for key, project in gitlab_project.projects : key => project.path_with_namespace
  } : {}
}
