module "firebase_foundation" {
  source = "../../modules/firebase_foundation"

  project_id                            = var.project_id
  project_name                          = var.project_name
  create_project                        = var.create_project
  billing_account_id                    = var.billing_account_id
  org_id                                = var.org_id
  folder_id                             = var.folder_id
  required_services                     = var.required_services
  enable_hosting_site                   = var.enable_hosting_site
  hosting_site_id                       = var.hosting_site_id
  create_github_actions_service_account = var.create_github_actions_service_account
  github_actions_service_account_id     = var.github_actions_service_account_id
  github_actions_project_roles          = var.github_actions_project_roles
}

