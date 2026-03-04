module "firebase_foundation" {
  source = "../../modules/firebase_foundation"

  project_id                                 = var.project_id
  project_name                               = var.project_name
  create_project                             = var.create_project
  billing_account_id                         = var.billing_account_id
  org_id                                     = var.org_id
  folder_id                                  = var.folder_id
  required_services                          = var.required_services
  enable_firestore_database                  = var.enable_firestore_database
  firestore_database_name                    = var.firestore_database_name
  firestore_database_location                = var.firestore_database_location
  firestore_database_type                    = var.firestore_database_type
  enable_hosting_site                        = var.enable_hosting_site
  hosting_site_id                            = var.hosting_site_id
  create_github_actions_service_account      = var.create_github_actions_service_account
  github_actions_service_account_id          = var.github_actions_service_account_id
  github_actions_project_roles               = var.github_actions_project_roles
  manage_feedback_api_invoker_iam            = var.manage_feedback_api_invoker_iam
  feedback_api_region                        = var.feedback_api_region
  feedback_api_cloud_run_service_name        = var.feedback_api_cloud_run_service_name
  feedback_api_allow_public_invoker          = var.feedback_api_allow_public_invoker
  manage_feedback_api_runtime_project_roles  = var.manage_feedback_api_runtime_project_roles
  feedback_api_runtime_service_account_email = var.feedback_api_runtime_service_account_email
  feedback_api_runtime_project_roles         = var.feedback_api_runtime_project_roles
}
