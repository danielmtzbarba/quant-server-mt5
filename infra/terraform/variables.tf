variable "project_id" {
  description = "The GCP project ID to deploy to."
  type        = string
}

variable "region" {
  description = "The GCP region for the deployment."
  type        = string
  default     = "us-east1"
}

variable "zone" {
  description = "The GCP zone for the deployment."
  type        = string
  default     = "us-east1-c"
}

variable "instance_name" {
  description = "The name of the GCE instance."
  type        = string
  default     = "mt5-quant-server-vm"
}

variable "machine_type" {
  description = "The machine type for the instance."
  type        = string
  default     = "e2-micro"
}

