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
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "eventarc.googleapis.com",
    "artifactregistry.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
    "firestore.googleapis.com",
    "run.googleapis.com",
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
    "roles/cloudfunctions.admin",
    "roles/firebasehosting.admin",
    "roles/firebase.viewer",
    "roles/iam.serviceAccountUser",
    "roles/serviceusage.serviceUsageConsumer",
  ]
}

variable "manage_feedback_api_invoker_iam" {
  description = "Whether Terraform should manage public invoker IAM on the feedback API Cloud Run service."
  type        = bool
  default     = false
}

variable "feedback_api_region" {
  description = "Region for the feedback API Cloud Run service."
  type        = string
  default     = "us-central1"
}

variable "feedback_api_cloud_run_service_name" {
  description = "Cloud Run service name backing the feedback API function."
  type        = string
  default     = "quizfeedbackapi"
}

variable "feedback_api_allow_public_invoker" {
  description = "Whether to grant allUsers run.invoker on the feedback API service."
  type        = bool
  default     = false
}

variable "manage_feedback_api_runtime_project_roles" {
  description = "Whether Terraform should manage project IAM roles for the feedback API runtime service account."
  type        = bool
  default     = false
}

variable "feedback_api_runtime_service_account_email" {
  description = "Runtime service account email used by feedback API. Required when managing runtime roles."
  type        = string
  default     = null
}

variable "feedback_api_runtime_project_roles" {
  description = "Project roles to grant to the feedback API runtime service account."
  type        = list(string)
  default     = []
}
