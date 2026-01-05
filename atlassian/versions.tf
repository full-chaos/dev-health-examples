terraform {
  required_version = ">= 1.5.0"

  required_providers {
    jira = {
      source  = "fourplusone/jira"
      version = ">= 0.1.0"
    }
    atlassian-operations = {
      source  = "atlassian/atlassian-operations"
      version = ">= 1.0.0"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.9.1"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5.0"
    }
  }
}
