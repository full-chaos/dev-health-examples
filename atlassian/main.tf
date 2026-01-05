locals {
  # Generate email list from the random_pet resource in users.tf
  generated_emails = [for p in random_pet.users : "${p.id}@${var.generated_user_domain}"]
  dry_run_flag     = var.enable_issue_creation ? "" : " --dry-run"
}

module "jira_structure" {
  source                  = "./modules/jira_structure"
  project_lead_account_id = data.atlassian-operations_user.admin.account_id
  project_template_key    = var.project_template_key
}

module "ops_structure" {
  source          = "./modules/ops_structure"
  # Use generated users if created, otherwise fallback to admin user to ensure at least one member
  user_ids        = concat(
    var.enable_user_creation ? jira_user.generated[*].id : [],
    [data.atlassian-operations_user.admin.account_id]
  )
  organization_id  = var.atlassian_org_id
  enable_schedules = var.enable_schedules
}

resource "null_resource" "seeder" {
  triggers = {
    seed_hash = var.seed_random_state
    # Re-run if the script or map changes
    script_hash = filesha256("${path.module}/seed/seed_jira.py")
    map_hash    = filesha256("${path.module}/seed/story_map.yaml")
  }

  depends_on = [
    module.jira_structure,
    module.ops_structure
  ]

  provisioner "local-exec" {
    command = <<EOT
      cd ${path.module}/seed
      pip3 install -r requirements.txt
      python3 seed_jira.py \
        --url "${var.jira_url}" \
        --user "${var.jira_user}" \
        --token "${var.jira_token}" \
        --story story_map.yaml \
        --seed "${var.seed_random_state}" \
        --output ../manifest.json \
        --assignees "${var.enable_user_creation ? join(",", local.generated_emails) : var.jira_user}"${local.dry_run_flag}
    EOT
  }
}

output "manifest_path" {
  value = "${path.module}/manifest.json"
}
