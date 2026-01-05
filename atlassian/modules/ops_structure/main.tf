terraform {
  required_providers {
    atlassian-operations = {
      source = "atlassian/atlassian-operations"
    }
    random = {
      source = "hashicorp/random"
    }
    time = {
      source = "hashicorp/time"
    }
  }
}

resource "time_sleep" "stagger" {
  count           = length(var.team_names)
  # Use 30s per team to reduce risk of "422 Another request being processed" errors
  create_duration = "${count.index * 30}s"
}

resource "random_shuffle" "team_members" {
  count        = length(var.team_names)
  input        = var.user_ids
  result_count = length(var.user_ids) > 0 ? min(2, length(var.user_ids)) : 0
}

resource "atlassian-operations_team" "teams" {
  count           = length(var.team_names)
  display_name    = var.team_names[count.index]
  description     = "Seeded team for developer health demo"
  organization_id = var.organization_id
  team_type       = "OPEN"

  member = length(var.user_ids) > 0 ? [
    for m in random_shuffle.team_members[count.index].result : {
      account_id = m
      role       = "member"
    }
  ] : [
    {
      account_id = var.admin_user_id
      role       = "member"
    }
  ]

  depends_on = [time_sleep.stagger]
}

resource "atlassian-operations_schedule" "oncall" {
  count    = var.enable_schedules ? length(var.team_names) : 0

  name     = "${var.team_names[count.index]} On-call"
  team_id  = atlassian-operations_team.teams[count.index].id
  timezone = var.schedule_timezone
  enabled  = true
}

resource "atlassian-operations_schedule_rotation" "rotation" {
  count       = var.enable_schedules ? length(var.team_names) : 0

  schedule_id = atlassian-operations_schedule.oncall[count.index].id
  name        = "Weekly Rotation"
  type        = "weekly"
  start_date  = "2024-01-01T00:00:00Z"
  length      = 1

  participants = length(var.user_ids) > 0 ? [
    for p in random_shuffle.team_members[count.index].result : {
      type = "user"
      id   = p
    }
  ] : [
    {
      type = "user"
      id   = var.admin_user_id
    }
  ]
}

output "ops_team_ids" {
  value = atlassian-operations_team.teams[*].id
}
