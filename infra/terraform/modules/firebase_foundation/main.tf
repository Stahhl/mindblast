locals {
  effective_project_id = var.create_project ? google_project.this[0].project_id : var.project_id
  additional_services = [
    for svc in var.required_services : svc
    if svc != "serviceusage.googleapis.com"
  ]
}

resource "google_project" "this" {
  count           = var.create_project ? 1 : 0
  project_id      = var.project_id
  name            = var.project_name
  billing_account = var.billing_account_id
  org_id          = var.org_id
  folder_id       = var.folder_id
}

resource "google_project_service" "required" {
  for_each           = toset(local.additional_services)
  project            = local.effective_project_id
  service            = each.value
  disable_on_destroy = false

  depends_on = [google_project_service.serviceusage]
}

resource "google_project_service" "serviceusage" {
  project            = local.effective_project_id
  service            = "serviceusage.googleapis.com"
  disable_on_destroy = false
}

resource "google_firebase_project" "this" {
  provider = google-beta
  project  = local.effective_project_id

  depends_on = [
    google_project_service.serviceusage,
    google_project_service.required,
  ]
}

resource "google_firestore_database" "default" {
  count = var.enable_firestore_database ? 1 : 0

  project     = local.effective_project_id
  name        = var.firestore_database_name
  location_id = var.firestore_database_location
  type        = var.firestore_database_type

  depends_on = [google_firebase_project.this]
}

resource "google_firebase_hosting_site" "default" {
  provider = google-beta
  count    = var.enable_hosting_site ? 1 : 0

  project = local.effective_project_id
  site_id = var.hosting_site_id

  depends_on = [google_firebase_project.this]
}

resource "google_service_account" "github_actions" {
  count = var.create_github_actions_service_account ? 1 : 0

  account_id   = var.github_actions_service_account_id
  display_name = "GitHub Actions deployer for Mindblast"
  project      = local.effective_project_id
}

resource "google_project_iam_member" "github_actions_roles" {
  for_each = var.create_github_actions_service_account ? toset(var.github_actions_project_roles) : toset([])

  project = local.effective_project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions[0].email}"
}

data "google_iam_policy" "feedback_api_invoker" {
  count = var.manage_feedback_api_invoker_iam ? 1 : 0

  dynamic "binding" {
    for_each = var.feedback_api_allow_public_invoker ? [1] : []
    content {
      role    = "roles/run.invoker"
      members = ["allUsers"]
    }
  }
}

resource "google_cloud_run_service_iam_policy" "feedback_api_invoker" {
  count = var.manage_feedback_api_invoker_iam ? 1 : 0

  project     = local.effective_project_id
  location    = var.feedback_api_region
  service     = var.feedback_api_cloud_run_service_name
  policy_data = data.google_iam_policy.feedback_api_invoker[0].policy_data
}

resource "google_project_iam_member" "feedback_api_runtime_roles" {
  for_each = var.manage_feedback_api_runtime_project_roles && var.feedback_api_runtime_service_account_email != null ? toset(var.feedback_api_runtime_project_roles) : toset([])

  project = local.effective_project_id
  role    = each.value
  member  = "serviceAccount:${var.feedback_api_runtime_service_account_email}"
}
