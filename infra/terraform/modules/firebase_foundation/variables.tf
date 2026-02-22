variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "project_name" {
  description = "GCP project display name (required when create_project = true)."
  type        = string
  default     = null
}

variable "create_project" {
  description = "Whether Terraform should create the GCP project."
  type        = bool
  default     = false
}

variable "billing_account_id" {
  description = "Billing account ID without the billingAccounts/ prefix (required when create_project = true)."
  type        = string
  default     = null
}

variable "org_id" {
  description = "Optional organization ID for project creation."
  type        = string
  default     = null
}

variable "folder_id" {
  description = "Optional folder ID for project creation."
  type        = string
  default     = null
}

variable "required_services" {
  description = "APIs enabled for this project."
  type        = list(string)
  default = [
    "cloudresourcemanager.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
    "serviceusage.googleapis.com",
  ]
}

variable "enable_hosting_site" {
  description = "Whether to create a Firebase Hosting site."
  type        = bool
  default     = true
}

variable "hosting_site_id" {
  description = "Firebase Hosting site ID."
  type        = string
}

variable "create_github_actions_service_account" {
  description = "Whether to create a service account for GitHub Actions deployment."
  type        = bool
  default     = true
}

variable "github_actions_service_account_id" {
  description = "Service account ID (not email) for GitHub Actions."
  type        = string
  default     = "mindblast-gha-deployer"
}

variable "github_actions_project_roles" {
  description = "Project roles granted to the GitHub Actions deployer service account."
  type        = list(string)
  default = [
    "roles/firebasehosting.admin",
    "roles/firebase.viewer",
    "roles/serviceusage.serviceUsageConsumer",
  ]
}

