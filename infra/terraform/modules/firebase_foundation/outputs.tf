output "project_id" {
  description = "Effective project ID used by Firebase resources."
  value       = local.effective_project_id
}

output "hosting_site_name" {
  description = "Hosting site resource name."
  value       = var.enable_hosting_site ? google_firebase_hosting_site.default[0].name : null
}

output "firestore_database_name" {
  description = "Firestore database name managed by Terraform."
  value       = var.enable_firestore_database ? google_firestore_database.default[0].name : null
}

output "hosting_site_id" {
  description = "Hosting site ID."
  value       = var.enable_hosting_site ? google_firebase_hosting_site.default[0].site_id : null
}

output "github_actions_service_account_email" {
  description = "Service account email for CI deploys."
  value       = var.create_github_actions_service_account ? google_service_account.github_actions[0].email : null
}
