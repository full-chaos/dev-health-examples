resource "random_pet" "users" {
  count     = var.generated_user_count
  length    = 2
  separator = "."
}

resource "random_password" "user_passwords" {
  count   = var.generated_user_count
  length  = 16
  special = true
}

# Fetch the current admin user via Atlassian Operations (JSM) provider
data "atlassian-operations_user" "admin" {
  email_address = var.jira_user
}

resource "jira_user" "generated" {
  # Only create users if enabled (defaults to false to avoid API errors on SSO-enabled instances)
  count = var.enable_user_creation ? var.generated_user_count : 0

  name          = "${random_pet.users[count.index].id}@${var.generated_user_domain}"
  email         = "${random_pet.users[count.index].id}@${var.generated_user_domain}"
  display_name  = title(replace(random_pet.users[count.index].id, ".", " "))
}

output "generated_user_candidates" {
  description = "List of randomized users (candidates for creation)"
  value = {
    for i, p in random_pet.users : title(replace(p.id, ".", " ")) => "${p.id}@${var.generated_user_domain}"
  }
}

output "created_user_ids" {
  description = "IDs of successfully created users"
  value = var.enable_user_creation ? [for u in jira_user.generated : u.id] : []
}

output "admin_user_id" {
  value = data.atlassian-operations_user.admin.account_id
}
