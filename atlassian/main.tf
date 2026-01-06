locals {
  team_names = [
    "Team-01",
    "Team-02",
    "Team-03",
    "Team-04",
    "Team-05",
    "Team-06",
    "Team-07",
    "Team-08",
    "Team-09",
    "Team-10",
  ]

  project_map = {
    CORE = "Core"
    PLAT = "Platform"
    DATA = "Data"
    INFR = "Infra"
    SECU = "Security"
    MOBI = "Mobile"
    WEBX = "Web"
    INTG = "Integrations"
    PAY  = "Payments"
    SRE  = "Reliability"
  }

  dry_run_flag      = var.enable_issue_creation ? "" : "--dry-run"
  assignee_flag     = length(var.assignee_emails) > 0 ? "--assignees ${join(",", var.assignee_emails)}" : "--assignees ${var.jira_user}"
  sprints_flag      = var.enable_sprints ? "" : "--disable-sprints"
  transitions_flag  = var.enable_transitions ? "" : "--disable-transitions"
  comments_flag     = var.enable_comments ? "--enable-comments" : ""
  incidents_flag    = var.disable_incidents ? "--disable-incidents" : ""
  start_date_flag   = var.provision_start_date != "" ? "--start-date ${var.provision_start_date}" : ""
  end_date_flag     = var.provision_end_date != "" ? "--end-date ${var.provision_end_date}" : ""
  monthly_issue_flag = var.monthly_issue_count != 0 ? "--monthly-issue-count ${var.monthly_issue_count}" : ""
  date_range_valid  = var.provision_end_date == "" || var.provision_start_date != ""

  project_lead_id = var.project_lead_account_id != "" ? var.project_lead_account_id : data.atlassian-operations_user.admin.account_id
  team_member_ids = length(var.team_member_account_ids) > 0 ? var.team_member_account_ids : (var.enable_user_creation ? jira_user.generated[*].id : [])
}

module "jira_structure" {
  source = "./modules/jira_structure"

  project_lead_account_id = local.project_lead_id
  project_map             = local.project_map
  enable_project_creation = var.enable_project_creation
}

module "ops_structure" {
  source = "./modules/ops_structure"

  organization_id = var.atlassian_org_id
  team_names      = local.team_names
  user_ids        = local.team_member_ids
  admin_user_id   = local.project_lead_id
  enable_schedules = var.enable_schedules
  schedule_timezone = var.schedule_timezone
}

resource "null_resource" "seed" {
  depends_on = [module.jira_structure, module.ops_structure]

  lifecycle {
    precondition {
      condition     = local.date_range_valid
      error_message = "provision_start_date is required when provision_end_date is set."
    }
  }

  triggers = {
    story_map_hash = filesha256("${path.module}/seed/story_map.yaml")
    script_hash    = filesha256("${path.module}/seed/seed_jira.py")
    seed_hash      = sha256(var.seed_string)
    batch_size     = var.batch_size
    dry_run        = tostring(var.enable_issue_creation)
    start_date     = var.provision_start_date
    end_date       = var.provision_end_date
    monthly_issues = var.monthly_issue_count
  }

  provisioner "local-exec" {
    command = join(" ", compact([
      # Install Python dependencies
      "pip3 install -q PyYAML requests &&",
      # Create output directory
      "mkdir -p ${path.module}/out &&",
      # Run seeder
      "python3",
      "${path.module}/seed/seed_jira.py",
      "--url", var.jira_url,
      "--user", var.jira_user,
      "--story", "${path.module}/seed/story_map.yaml",
      "--manifest", "${path.module}/out/manifest.json",
      "--seed", var.seed_string,
      "--batch-size", tostring(var.batch_size),
      local.start_date_flag,
      local.end_date_flag,
      local.monthly_issue_flag,
      local.assignee_flag,
      local.dry_run_flag,
      local.sprints_flag,
      local.transitions_flag,
      local.comments_flag,
      local.incidents_flag,
    ]))
    
    environment = {
      JIRA_TOKEN = var.jira_token
    }
  }
}
