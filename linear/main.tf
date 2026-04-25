locals {
  dry_run_flag       = var.enable_issue_creation ? "" : "--dry-run"
  comments_flag      = var.enable_comments ? "" : "--disable-comments"
  cycles_flag        = var.enable_cycles ? "" : "--disable-cycles"
  start_date_flag    = var.provision_start_date != "" ? "--start-date ${var.provision_start_date}" : ""
  end_date_flag      = var.provision_end_date != "" ? "--end-date ${var.provision_end_date}" : ""
  monthly_issue_flag = var.monthly_issue_count != 0 ? "--monthly-issue-count ${var.monthly_issue_count}" : ""
  assignees_flag     = length(var.assignee_emails) > 0 ? "--assignees ${join(",", var.assignee_emails)}" : ""
  date_range_valid   = var.provision_end_date == "" || var.provision_start_date != ""
  auth_valid         = !var.enable_issue_creation || var.linear_api_key != ""
}

resource "null_resource" "seed" {
  lifecycle {
    precondition {
      condition     = local.date_range_valid
      error_message = "provision_start_date is required when provision_end_date is set."
    }
    precondition {
      condition     = local.auth_valid
      error_message = "linear_api_key is required when enable_issue_creation is true."
    }
  }

  triggers = {
    story_map_hash = filesha256("${path.module}/seed/story_map.yaml")
    script_hash    = filesha256("${path.module}/seed/seed_linear.py")
    seed_hash      = sha256(var.seed_string)
    batch_size     = var.batch_size
    dry_run        = tostring(!var.enable_issue_creation)
    start_date     = var.provision_start_date
    end_date       = var.provision_end_date
    monthly_issues = var.monthly_issue_count
  }

  provisioner "local-exec" {
    command = join(" ", compact([
      "pip3 install -q -r ${path.module}/seed/requirements.txt &&",
      "mkdir -p ${path.module}/out &&",
      "python3",
      "${path.module}/seed/seed_linear.py",
      "--story", "${path.module}/seed/story_map.yaml",
      "--manifest", "${path.module}/out/manifest.json",
      "--seed", var.seed_string,
      "--batch-size", tostring(var.batch_size),
      local.start_date_flag,
      local.end_date_flag,
      local.monthly_issue_flag,
      local.assignees_flag,
      local.dry_run_flag,
      local.comments_flag,
      local.cycles_flag,
    ]))

    environment = {
      LINEAR_API_KEY = var.linear_api_key
    }
  }
}
