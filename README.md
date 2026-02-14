# Skill Factory Web

Bien raw data thanh production-ready AI skills qua giao dien web.

## Quick Start

### Prerequisites
- Node.js 20+
- Python 3.11+
- PM2 (auto-installed by deploy script)

### Deploy

```bash
# 1. Clone/upload project
cd /opt/skill-factory-web

# 2. Create .env.local
cp .env.example .env.local
# Edit: set FACTORY_PASSWORD, API keys

# 3. Deploy
chmod +x deploy.sh
./deploy.sh

# 4. Access
# http://YOUR_IP:3000
```

### Nginx (Optional — for domain + SSL)

```nginx
server {
    listen 80;
    server_name factory.xs10k.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;

        # CRITICAL for SSE streaming:
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

Then: `sudo certbot --nginx -d factory.xs10k.com`

## Usage Guide (for Team)

### Tao Build Moi
1. Login bang mat khau team
2. Click **"New Build"**
3. Chon template (FB Ads / Google Ads / Blockchain / Custom)
4. Dat ten, chon quality tier
5. Upload transcripts hoac paste URLs
6. Review > **"Bat dau Build"**

### Theo Doi Build
- Dashboard: xem tat ca builds + stats
- Click vao build card > Live View:
  - Phase stepper (P0>P5)
  - Real-time logs
  - Quality scores per phase
- Build xong > Quality Report + Download .zip

### Tips
- **Quality tier**: Draft (~5 phut, $2-3) vs Standard (~15 phut, $5-10) vs Premium (~30 phut, $15-25)
- **Conflict review**: Neu build tam dung > vao review, chon Keep A/B/Merge/Discard cho tung conflict
- **Retry**: Build fail > click Retry > tao build moi voi cung config

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Login khong duoc | Check FACTORY_PASSWORD trong .env.local |
| Build stuck | Check `pm2 logs skill-factory`, verify Python path |
| SSE khong hoat dong | Nginx: them `proxy_buffering off;` |
| Database locked | Restart: `pm2 restart skill-factory` |
| Disk full | Settings > Cleanup Now, hoac giam auto_cleanup_days |

## Architecture

```
Browser <-> Next.js (API + SSE) <-> Python CLI (subprocess)
                |
            SQLite (data/skill-factory.db)
```

## Commands

```bash
pm2 status              # Check process status
pm2 logs skill-factory  # View logs
pm2 restart skill-factory  # Restart
pm2 stop skill-factory  # Stop
```
