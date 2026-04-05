terraform {
  backend "gcs" {
    bucket = "terraform-state-project-221a7ff0-ceb3-422b-bf0"
    prefix = "terraform/state"
  }
}
