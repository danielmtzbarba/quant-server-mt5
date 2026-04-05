# Setup Guide: Zero-Secret CI/CD (Workload Identity Federation)

To activate the **Continuous Deployment (CD)** pipeline without using sensitive JSON keys, we use **Workload Identity Federation (WIF)**. This allow GitHub to securely impersonate your GCP Service Account for each run.

---

## 1. Prepare Google Cloud Resources

I have already added the WIF pool and provider to your `main.tf`. To activate them:

1.  **Run Terraform Locally**:
    ```bash
    cd infra/terraform
    terraform init
    terraform apply
    ```
2.  **Enable Required APIs**:
    Ensure these APIs are enabled in your GCP Console:
    - `IAM Service Account Credentials API` (iamcredentials.googleapis.com)
    - `Security Token Service API` (sts.googleapis.com)

---

## 2. Add Secrets to GitHub

Go to your repository on GitHub: **Settings > Secrets and variables > Actions**. Click **New repository secret** for these:

| Secret Name | Description | Example / Source |
| :--- | :--- | :--- |
| **`GCP_PROJECT_ID`** | Your Google Cloud Project ID | `quant-project-123` |
| **`GCP_WIF_PROVIDER`**| The full name of the WIF Provider | `projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| **`GCP_VM_IP`**       | The External IP address of your VM | `34.1.2.3` (Find this in GCP Console) |
| **`GCP_SSH_PRIVATE_KEY`**| Your SSH Private Key used for VM access | Result of `ssh-keygen` (Begin with `-----BEGIN...`) |

### How to find the `GCP_WIF_PROVIDER` string:
After running `terraform apply`, check the output or run:
```bash
gcloud iam workload-identity-pools providers describe github-provider \
    --project="YOUR_PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="github-pool" \
    --format="value(name)"
```

---

## 3. Verify the Deployment

1.  **Push a change** to the `main` branch.
2.  Check the **Actions** tab in GitHub.
3.  The `Authenticate to GCP (Keyless)` step will now perform the identity handshake without any JSON keys!

---

## Security Note

**You can now safely delete any `GCP_SA_KEY` or JSON files from your computer and from GitHub Secrets.** Your security posture is now at a professional, zero-secret standard.
