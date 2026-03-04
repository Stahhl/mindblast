variable "region" {
  description = "Default GCP region."
  type        = string
  default     = "us-central1"
}

variable "project_id" {
  description = "Production GCP project ID."
  type        = string
}

variable "project_name" {
  description = "Production project display name."
  type        = string
  default     = null
}

variable "create_project" {
  description = "Whether Terraform should create the production project."
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
  description = "APIs enabled in production."
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

variable "enable_firestore_database" {
  description = "Whether Terraform should create/manage the Firestore database."
  type        = bool
  default     = true
}

variable "firestore_database_name" {
  description = "Firestore database name."
  type        = string
  default     = "(default)"
}

variable "firestore_database_location" {
  description = "Firestore database location/region."
  type        = string
  default     = "us-central1"
}

variable "firestore_database_type" {
  description = "Firestore database type."
  type        = string
  default     = "FIRESTORE_NATIVE"
}

variable "enable_hosting_site" {
  description = "Whether to create a production hosting site."
  type        = bool
  default     = true
}

variable "hosting_site_id" {
  description = "Production Firebase Hosting site ID."
  type        = string
  default     = "mindblast-prod"
}

variable "create_github_actions_service_account" {
  description = "Whether to create a CI deploy service account."
  type        = bool
  default     = true
}

variable "github_actions_service_account_id" {
  description = "Service account ID for CI deploys."
  type        = string
  default     = "mindblast-prod-gha"
}

variable "github_actions_project_roles" {
  description = "Project roles for the CI service account."
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
  description = "Whether Terraform manages feedback API Cloud Run invoker IAM."
  type        = bool
  default     = true
}

variable "feedback_api_region" {
  description = "Region of the feedback API Cloud Run service."
  type        = string
  default     = "us-central1"
}

variable "feedback_api_cloud_run_service_name" {
  description = "Cloud Run service name behind feedback API."
  type        = string
  default     = "quizfeedbackapi"
}

variable "feedback_api_allow_public_invoker" {
  description = "Whether allUsers should have run.invoker on feedback API."
  type        = bool
  default     = false
}

variable "manage_feedback_api_runtime_project_roles" {
  description = "Whether Terraform manages runtime service account project IAM for feedback API."
  type        = bool
  default     = false
}

variable "feedback_api_runtime_service_account_email" {
  description = "Runtime service account email used by feedback API."
  type        = string
  default     = null
}

variable "feedback_api_runtime_project_roles" {
  description = "Project roles for feedback API runtime service account."
  type        = list(string)
  default     = []
}
