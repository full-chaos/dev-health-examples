terraform {
  required_providers {
    gitlab = {
      source  = "gitlabhq/gitlab"
      version = "~> 17.0"
    }
    null = {
      source = "hashicorp/null"
    }
  }
}

provider "gitlab" {
  token    = var.gitlab_token
  base_url = var.gitlab_base_url
}

locals {
  group_path = lower(replace(var.group_name, " ", "-"))

  project_map = {
    core = "Core"
    platform = "Platform"
    data = "Data"
    infra = "Infra"
    security = "Security"
    mobile = "Mobile"
    web = "Web"
    integrations = "Integrations"
    payments = "Payments"
    reliability = "Reliability"
  }

  dry_run_flag       = var.enable_seed_creation ? "" : "--dry-run"
  comments_flag      = var.enable_comments ? "--enable-comments" : ""
  pipelines_flag     = var.enable_pipelines ? "" : "--disable-pipelines"
  merge_requests_flag = var.enable_merge_requests ? "" : "--disable-merge-requests"
  releases_flag      = var.enable_releases ? "" : "--disable-releases"
  start_date_flag    = var.provision_start_date != "" ? "--start-date ${var.provision_start_date}" : ""
  end_date_flag      = var.provision_end_date != "" ? "--end-date ${var.provision_end_date}" : ""
  monthly_issue_flag = var.monthly_issue_count != 0 ? "--monthly-issue-count ${var.monthly_issue_count}" : ""
  reviewers_flag     = length(var.reviewer_usernames) > 0 ? "--reviewers ${join(",", var.reviewer_usernames)}" : ""
  date_range_valid   = var.provision_end_date == "" || var.provision_start_date != ""
}

module "gitlab_structure" {
  source = "./modules/gitlab_structure"

  group_name              = var.group_name
  group_path              = local.group_path
  project_map             = local.project_map
  enable_group_creation   = var.enable_group_creation
  enable_project_creation = var.enable_project_creation
  project_visibility      = var.project_visibility
}

resource "null_resource" "seed" {
  depends_on = [module.gitlab_structure]

  lifecycle {
    precondition {
      condition     = local.date_range_valid
      error_message = "provision_start_date is required when provision_end_date is set."
    }
  }

  triggers = {
    story_map_hash = filesha256("${path.module}/seed/story_map.yaml")
    script_hash    = filesha256("${path.module}/seed/seed_gitlab.py")
    seed_hash      = sha256(var.seed_string)
    batch_size     = tostring(var.batch_size)
    dry_run        = tostring(var.enable_seed_creation)
    start_date     = var.provision_start_date
    end_date       = var.provision_end_date
    monthly_issues = tostring(var.monthly_issue_count)
  }

  provisioner "local-exec" {
    command = join(" ", compact([
      "pip3 install -q -r ${path.module}/seed/requirements.txt &&",
      "mkdir -p ${path.module}/out &&",
      "python3",
      "${path.module}/seed/seed_gitlab.py",
      "--base-url", var.gitlab_base_url,
      "--group-path", module.gitlab_structure.group_path,
      "--story", "${path.module}/seed/story_map.yaml",
      "--manifest", "${path.module}/out/manifest.json",
      "--seed", var.seed_string,
      "--batch-size", tostring(var.batch_size),
      local.start_date_flag,
      local.end_date_flag,
      local.monthly_issue_flag,
      local.reviewers_flag,
      local.dry_run_flag,
      local.comments_flag,
      local.pipelines_flag,
      local.merge_requests_flag,
      local.releases_flag,
    ]))

    environment = {
      GITLAB_TOKEN = var.gitlab_token
    }
  }
}
