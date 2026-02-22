variable "region" {
  description = "Default GCP region."
  type        = string
  default     = "us-central1"
}

variable "project_id" {
  description = "Staging GCP project ID."
  type        = string
}

variable "project_name" {
  description = "Staging project display name."
  type        = string
  default     = null
}

variable "create_project" {
  description = "Whether Terraform should create the staging project."
  type        = bool
  default     = false
}

variable "billing_account_id" {
  description = "Billing account ID for project creation."
  type        = string
  default     = null
}

variable "org_id" {
  description = "Organization ID for project creation."
  type        = string
  default     = null
}

variable "folder_id" {
  description = "Folder ID for project creation."
  type        = string
  default     = null
}

variable "required_services" {
  description = "APIs enabled in staging."
  type        = list(string)
  default = [
    "cloudresourcemanager.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
    "serviceusage.googleapis.com",
  ]
}

variable "enable_hosting_site" {
  description = "Whether to create a staging hosting site."
  type        = bool
  default     = true
}

variable "hosting_site_id" {
  description = "Staging Firebase Hosting site ID."
  type        = string
  default     = "mindblast-staging"
}

variable "create_github_actions_service_account" {
  description = "Whether to create a CI deploy service account."
  type        = bool
  default     = true
}

variable "github_actions_service_account_id" {
  description = "Service account ID for CI deploys."
  type        = string
  default     = "mindblast-staging-gha"
}

variable "github_actions_project_roles" {
  description = "Project roles for the CI service account."
  type        = list(string)
  default = [
    "roles/firebasehosting.admin",
    "roles/firebase.viewer",
    "roles/serviceusage.serviceUsageConsumer",
  ]
}

