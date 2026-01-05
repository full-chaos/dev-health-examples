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

resource "random_pet" "teams" {
  count = 4
  length = 1
  prefix = "Squad"
  separator = "-"
}

# Add a stagger to avoid 422 error from Atlassian API (Another request being processed)
resource "time_sleep" "stagger" {
  count           = length(random_pet.teams)
  create_duration = "${count.index * 30}s"
}

# Randomly select members for each team using provided IDs
resource "random_shuffle" "team_members" {
  count        = length(random_pet.teams)
  input        = var.user_ids
  result_count = length(var.user_ids) > 0 ? min(2, length(var.user_ids)) : 0
}

resource "atlassian-operations_team" "teams" {
  count           = length(random_pet.teams)
  display_name    = random_pet.teams[count.index].id
  # Reference time_sleep stagger to force sequential creation
  description     = "Auto-generated team (delay: ${time_sleep.stagger[count.index].create_duration})"
  organization_id = var.organization_id
  team_type       = "OPEN"

  member = [
    for m in random_shuffle.team_members[count.index].result : {
      account_id = m
      role       = "member"
    }
  ]
}

resource "atlassian-operations_schedule" "oncall" {
  # Trigger to enable/disable schedule creation
  count    = var.enable_schedules ? length(random_pet.teams) : 0
  
  name     = "${random_pet.teams[count.index].id}_schedule"
  team_id  = atlassian-operations_team.teams[count.index].id
  timezone = "America/New_York"
  enabled  = true
}

resource "atlassian-operations_schedule_rotation" "rotation" {
  # Trigger to enable/disable rotation creation
  count       = var.enable_schedules ? length(random_pet.teams) : 0
  
  schedule_id = atlassian-operations_schedule.oncall[count.index].id
  name        = "Weekly Rotation"
  type        = "weekly"
  start_date  = "2024-01-01T00:00:00Z"
  length      = 1

  participants = [
    for p in random_shuffle.team_members[count.index].result : {
      type = "user"
      id   = p
    }
  ]
}

output "ops_teams" {
  value = random_pet.teams[*].id
}
