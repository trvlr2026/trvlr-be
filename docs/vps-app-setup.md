# VPS App Setup (Ubuntu 24.04)

Deploy the FastAPI app on the Contabo VPS, accessible from the internet.

**Prerequisites:** PostgreSQL + PostGIS already set up (see `vps-db-setup.md`).

## 1. Install Python 3.12 + Dependencies

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip git nginx
```

## 2. Clone the Repo

```bash
cd /opt
git clone git@github.com:YOUR_USERNAME/trvlr-be.git
cd trvlr-be
```

## 3. Create Virtual Environment and Install Packages

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Create .env File

```bash
cat > /opt/trvlr-be/.env << 'EOF'
DATABASE_URL=postgresql://trvlr_admin:your_password@localhost:5432/trvlr_db
AUTH_ENABLED=false
JWT_SECRET=change-this-to-a-strong-random-string
GOOGLE_CLIENT_ID=
EOF
```

## 5. Test the App Runs

```bash
cd /opt/trvlr-be
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Hit `http://YOUR_VPS_IP:8000/health` from your browser. If it returns `{"status":"ok"}`, you're good. Stop it with `Ctrl+C`.

## 6. Create a Systemd Service (runs app on boot)

```bash
sudo cat > /etc/systemd/system/trvlr-be.service << 'EOF'
[Unit]
Description=trvlr-be FastAPI App
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/trvlr-be
ExecStart=/opt/trvlr-be/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
Environment=PATH=/opt/trvlr-be/.venv/bin:/usr/bin

[Install]
WantedBy=multi-user.target
EOF
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable trvlr-be
sudo systemctl start trvlr-be
```

Check it's running:

```bash
sudo systemctl status trvlr-be
```

## 7. Set Up Nginx as Reverse Proxy

```bash
sudo cat > /etc/nginx/sites-available/trvlr-be << 'EOF'
server {
    listen 80;
    server_name YOUR_VPS_IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

```bash
sudo ln -s /etc/nginx/sites-available/trvlr-be /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

## 8. Open Firewall Ports

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

## 9. Verify

From your Mac or browser:

```bash
curl http://YOUR_VPS_IP/health
```

Should return `{"status":"ok"}`.

## 10. (Optional) Add SSL with Let's Encrypt

If you have a domain pointing to your VPS IP:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

This auto-configures HTTPS. Certificates renew automatically.

---

## Useful Commands

```bash
# View app logs
sudo journalctl -u trvlr-be -f

# Restart app after code changes
cd /opt/trvlr-be && git pull && sudo systemctl restart trvlr-be

# Restart nginx
sudo systemctl restart nginx

# Check app status
sudo systemctl status trvlr-be
```

## Deploying Updates

```bash
cd /opt/trvlr-be
git pull
.venv/bin/pip install -r requirements.txt  # if dependencies changed
sudo systemctl restart trvlr-be
```
