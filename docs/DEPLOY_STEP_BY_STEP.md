# DermAI: step-by-step deployment

Verified before packaging: backend tests pass (78, 4 skipped because PyTorch is optional), and the frontend builds. The Docker images themselves were not built in my environment, so Step 3 is your first real Docker test.

---
## Part A. Run it on your own computer (free, 15 minutes)

### Step 1. Install the tools
- Docker Desktop (Windows / macOS) or Docker Engine + Compose plugin (Linux). Check: `docker --version` and `docker compose version`.
- Nothing else is needed. Python and Node are only for development.

### Step 2. Get the project ready
1. Unzip `dermai-milestone4.zip` and open a terminal in the `dermai` folder.
2. **Copy your trained model.** From your machine copy `backend/models/` (it contains `v1.1-convnext_tiny/`, `active.json`, `segmentation.ts.pt`, `segmentation.json`) into the unzipped project's `backend/models/`. Models are not in the zip (git-ignored, large). Without them the app still runs but images stay "pending" and there are no predictions.
3. Create the settings file:
   - macOS / Linux: `cp .env.example .env`
   - Windows: `copy .env.example .env`
4. Open `.env`. For a local demo you can leave `ENVIRONMENT=development` and change nothing. Still set `SECRET_KEY` to any long random text.

### Step 3. Build and start
```bash
docker compose up --build
```
The first build takes 5-15 minutes (it downloads PyTorch). Wait until you see `DermAI 0.4.0 started` in the logs.

### Step 4. Check it works
- App: http://localhost:8080
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/health/ready should show `"status":"ok"` and your model version.
- Sign in as admin (Staff sign in on the entry page): `admin@dermai.local` / `ChangeMe!2026` (or what you put in `.env`).

### Step 5. Try the full flow (this is your demo script)
1. Sign up as a patient (tick research consent). 2. New case, upload a skin photo. 3. Open the analysis screen. 4. Download the PDF report. 5. Admin: Administration > Models shows the deployed model; `/api/metrics` (via http://localhost:8000/docs, Authorize) shows platform health.

### Step 6. Stop / restart
- Stop: `Ctrl+C`, or `docker compose down` (keeps your data).
- Start again later: `docker compose up -d`.
- Wipe everything: `docker compose down -v` (deletes the database and uploads).

---
## Part B. Share a public link for free (Cloudflare quick tunnel)
Good for letting an evaluator try it while your computer is on. HTTPS is included.
1. Keep `docker compose up` running.
2. Install `cloudflared` (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
3. Run: `cloudflared tunnel --url http://localhost:8080`
4. It prints a `https://something.trycloudflare.com` address. Share that.
5. Use only public or de-identified images. Stop the tunnel (Ctrl+C) when done.

---
## Part C. Put it on a cloud server (Azure for Students, or any VM)
You need a VM with **2 vCPU, 4 GB RAM or more**, Ubuntu 22.04/24.04, and 20 GB disk.

### Step 1. Create the VM
- Azure: portal > Virtual machines > Create. Image Ubuntu, size B2s (or B2as_v2), add SSH key, allow inbound ports **22, 80, 443**.
- AWS: EC2, t3.medium, Ubuntu, same ports. (Check your free credits first; it is not always free.)

### Step 2. Install Docker on the VM
```bash
ssh <user>@<vm-ip>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && exit      # log in again
```

### Step 3. Copy the project and the model
From your computer (not the VM):
```bash
scp dermai-milestone4.zip <user>@<vm-ip>:~
scp -r backend/models <user>@<vm-ip>:~/models
```
On the VM:
```bash
sudo apt-get install -y unzip && unzip dermai-milestone4.zip -d dermai && cd dermai
cp -r ~/models/* backend/models/
```

### Step 4. Configure for production
```bash
cp .env.example .env
openssl rand -hex 32          # copy the output into SECRET_KEY
nano .env
```
Set: `ENVIRONMENT=production`, `SECRET_KEY=<the random text>`, `POSTGRES_PASSWORD=<strong>`, `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_PASSWORD=<strong, not the default>`, `CORS_ORIGINS=["https://your-domain"]`. In production mode the API refuses to start with the defaults, and the logs tell you which setting is wrong.

### Step 5. Start
```bash
docker compose up -d --build
docker compose ps                    # all three should be "healthy" / running
docker compose logs -f backend       # Ctrl+C to leave the log view
curl -fs http://localhost:8080/api/health/ready
```

### Step 6. Make it reachable over HTTPS
Do not expose plain HTTP with patient images. The simplest way is Caddy on the same VM (automatic certificates). You need a domain name pointing to the VM's IP.
```bash
sudo apt-get install -y caddy
echo 'your-domain.example { reverse_proxy localhost:8080 }' | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy
```
Then open `https://your-domain.example`. In the VM's firewall, allow 80/443 only; do not open 8000 or 8080 publicly. In `docker-compose.yml` you can change `ports: ["8080:80"]` to `["127.0.0.1:8080:80"]` and `["8000:8000"]` to `["127.0.0.1:8000:8000"]`.
No domain? Use the Cloudflare tunnel from Part B on the VM instead.

### Step 7. Operate it
- Update: copy new files, then `docker compose up -d --build`.
- Backups: `docker run --rm -v dermai_pgdata:/d -v $PWD:/b alpine tar czf /b/pgdata.tgz -C /d .` and the same for `dermai_media`.
- Deploy a new model: copy it into `backend/models/<version>/`, then Administration > Models > Deploy, then "Re-analyse all".
- Monitoring: `docker compose logs backend`, `/api/health/ready`, admin `/api/metrics`, Administration > Audit log.

---
## Troubleshooting
| Symptom | Fix |
|---|---|
| Backend exits at start in production | Read `docker compose logs backend`; it names the setting (SECRET_KEY under 32 characters, or default admin password). |
| `frontend` waits forever | Backend is not healthy yet; wait 1-2 minutes, then check `docker compose logs backend`. |
| Uploads stay "pending" | No model found. Check `backend/models/active.json` and that the folder it names exists; `/api/health/ready` shows `model`. |
| "Too many failed sign-in attempts" | Lockout after 5 wrong passwords; wait 5 minutes (or restart the backend container). |
| Build is very slow or runs out of memory | Needs about 4 GB RAM. Build once with `--build`, then use `up -d`. |
| Port already in use | Change the left-hand number in `ports:` in `docker-compose.yml`. |
| Cannot sign in as admin | Admin is created only on first start with an empty database. Use the email and password in `.env`; if you changed them later, run `docker compose down -v` (wipes data) and start again. |
| Windows: `scp`/`cp` differences | Use PowerShell for `copy`, and WSL for the Linux commands. |
