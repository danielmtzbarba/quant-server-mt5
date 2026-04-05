# Hybrid Cloud Setup Guide (GCP + Local Databases)

This guide details how to securely connect the **MT5 Quant Server** running on a Google Cloud VM to **PostgreSQL** and **InfluxDB** databases hosted on your local machine.

---

## 1. Networking Strategy: Tailscale (Recommended)

To allow the GCP VM to communicate with your local PC without exposing your databases to the public internet, we use **Tailscale**. It creates a private mesh VPN.

### Step A: Install Tailscale
1.  **On your Local PC**: Download and install [Tailscale](https://tailscale.com/download). Log in.
2.  **On the GCP VM**: (Handled automatically by the upgraded Terraform startup script, or run):
    ```bash
    curl -fsSL https://tailscale.com/install.sh | sh
    sudo tailscale up
    ```

### Step B: Identify IPs
- Run `tailscale ip` on both machines.
- Your Local PC will have an IP like `100.x.y.z`. **This is the IP the VM will use to reach your databases.**

---

## 2. Local Database Configuration

By default, PostgreSQL and InfluxDB only listen on `localhost`. You must tell them to listen on the Tailscale interface.

### A. PostgreSQL Setup
1.  **Edit `postgresql.conf`**:
    Ensure Postgres *only* listens on your internal interfaces. Find `listen_addresses` and change it to:
    ```conf
    # Replace 100.x.y.z with your Local PC's Tailscale IP
    listen_addresses = 'localhost,100.x.y.z' 
    ```
2.  **Edit `pg_hba.conf`**:
    Configure strict access rules. **Do not use 'trust'**. Add this line:
    ```conf
    # host    DATABASE    USER         GCP_VM_IP/32    METHOD
    host      tradedb     danielmtz    100.a.b.c/32    md5
    ```
    *(Replace `100.a.b.c` with your GCP VM's Tailscale IP)*.
3.  **Restart PostgreSQL**.

### B. InfluxDB Setup
Ensure InfluxDB is bound to `0.0.0.0` or your Tailscale IP in its configuration (usually `influxdb.conf` or environment variables).

---

## 3. Environment Variables (VM side)

When running the Docker Compose stack on the GCP VM, your `.env` files should point to your **Local PC's Tailscale IP**.

**Example `infra/envs/shared.env`**:
```env
# Tailscale IP of your Local PC
DATABASE_URL=postgresql+asyncpg://danielmtz:password@100.x.y.z:5432/tradedb
```

**Example `infra/envs/execution.env`**:
```env
# Tailscale IP of your Local PC
INFLUX_URL=http://100.x.y.z:8086
```

---

## 4. Verification

From the GCP VM, verify connectivity before starting the services:

```bash
# Test PostgreSQL Port
nc -zv 100.x.y.z 5432

# Test InfluxDB Port
nc -zv 100.x.y.z 8086
```

Once connectivity is confirmed, launch the stack using pre-built images from GHCR:
```bash
# Pull the pre-built images first (very fast on e2-micro)
docker compose -f infra/docker/server/docker-compose.yml pull

# Start the services
docker compose -f infra/docker/server/docker-compose.yml up -d
```

> [!NOTE]
> **GitHub Container Registry (GHCR)**: Your images are automatically built and stored by GitHub Actions. This prevents your GCP VM from running out of memory during local builds.
