terraform {
  required_version = ">= 1.5.0"

  required_providers {
    jira = {
      source  = "fourplusone/jira"
      version = ">= 0.1.0"
    }
    # Using generic/http or similar if specific ops provider is tricky, 
    # but sticking to user request for structure.
    # Note: "atlassian/atlassian-operations" is not a standard registry path 
    # as of my last knowledge (usually opsgenie/opsgenie). 
    # I will use a local-exec fallback for Ops if the provider is strictly required to be this specific name 
    # but likely the user means the 'opsgenie' provider or the unified 'atlassian' provider (unreleased/private).
    # I will proceed with a standard configuration that can be swapped.
    atlassian-operations = {
      source = "atlassian/atlassian-operations"
      version = ">= 0.1.0"
    }
    time = {
      source = "hashicorp/time"
      version = ">= 0.9.1"
    }
    null = {
      source  = "hashicorp/null"
      version = ">= 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0"
    }
  }
}
