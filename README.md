# Skill Factory Web

Convert raw data (transcripts, PDFs, URLs, repos) into production-ready AI Skill packages via web UI and Python pipeline.

**Version:** 2.12.1 | **Status:** Active (v2-upgrade branch in progress)

## Quick Start

### Prerequisites
- Node.js 20+
- Python 3.11+
- Claude API key (free or paid account)
- PM2 (auto-installed by deploy script)

### Deploy

```bash
# 1. Clone/upload project
cd /opt/skill-factory-web

# 2. Create .env.local
cp .env.example .env.local
# Edit: set FACTORY_PASSWORD, ANTHROPIC_API_KEY, etc.

# 3. Deploy with PM2
chmod +x deploy.sh
./deploy.sh

# 4. Access UI
# http://YOUR_IP:3000
# Password: see FACTORY_PASSWORD in .env.local (default: skillfactory2025)
```

## Architecture Overview

**Layers:**
- **Frontend:** React 19 (Next.js 16 App Router) — dashboard, build wizard, monitoring
- **Backend:** Node.js API routes — CRUD operations, build queue, SSE streaming
- **Database:** SQLite (WAL mode) — builds, logs, templates, settings, baselines
- **Pipeline:** Python 3 — 6-phase processor (P0 Baseline → P1 Audit → P2 Extract → P3 Dedup → P4 Verify → P5 Architect)
- **Deploy:** PM2 or Docker

```
Browser ←→ Next.js API + SSE ←→ Build Queue ←→ Python Pipeline + Claude API
                ↓
           SQLite DB
```

## Core Features

| Feature | Status |
|---------|--------|
| Build Wizard (4-step template-based creation) | ✅ Complete |
| Real-time SSE build monitoring | ✅ Complete |
| 6-phase Python pipeline (P0-P5) | ✅ Complete |
| Quality scoring (per-phase metrics) | ✅ Complete |
| Conflict resolution review UI | ✅ Complete |
| Template catalog + baselines | ✅ Complete |
| Download skill packages (.zip) | ✅ Complete |
| Single-password auth | ✅ Complete |
| Telegram notifications (optional) | ✅ Complete |
| v2-upgrade (10 patches: P5 rewrite, P6, UI enhancements) | 🚀 In Progress |

## Usage (End User)

### Create New Build
1. **Login** with team password
2. **New Build** → select template (FB Ads, Google Ads, Blockchain, Custom)
3. **Configure** → name, domain, quality tier (Draft/Standard/Premium)
4. **Upload sources** → transcripts, PDFs, URLs, or repo links
5. **Review** → check config YAML
6. **Start** → watch real-time progress

### Monitor Build
- **Dashboard:** all builds + stats (completed, avg quality, cost)
- **Live View:** phase stepper + logs + quality scores + cost tracking
- **Conflicts:** during P3 (dedup), review and resolve
- **Download:** after P5, get package.zip (SKILL.md + knowledge files + refs)

### Quality Tiers
- **Draft:** ~5 min, $2-3 → quick prototype
- **Standard:** ~15 min, $5-10 → production-ready
- **Premium:** ~30 min, $15-25 → exhaustive coverage

## Nginx Setup (Optional — for domain + SSL)

```nginx
server {
    listen 80;
    server_name factory.example.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;

        # CRITICAL for SSE:
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

Enable HTTPS:
```bash
sudo certbot --nginx -d factory.example.com
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Login fails | Verify `FACTORY_PASSWORD` in `.env.local` |
| Build stuck/timeout | Check `pm2 logs skill-factory`, restart: `pm2 restart skill-factory` |
| SSE not streaming | Nginx: add `proxy_buffering off;` and `proxy_read_timeout 86400s;` |
| Database locked | Restart process: `pm2 restart skill-factory` |
| Disk full | Settings → Cleanup Now, or adjust `auto_cleanup_days` |
| Python subprocess error | Verify `python_path` setting, check `/data/builds/{id}/pipeline.log` |

## Commands

```bash
pm2 status                    # Process status
pm2 logs skill-factory        # View logs
pm2 restart skill-factory     # Restart
pm2 stop skill-factory        # Stop
pm2 start ecosystem.config.js # Start fresh

# Manual Python CLI (advanced)
cd pipeline
python cli.py build --config build.yaml --output-dir ./output/
```

## Documentation

- **[Project Overview & PDR](./docs/project-overview-pdr.md)** — vision, features, requirements
- **[System Architecture](./docs/system-architecture.md)** — detailed design, data flow, schemas
- **[Codebase Summary](./docs/codebase-summary.md)** — directory structure, file inventory
- **[Code Standards](./docs/code-standards.md)** — patterns, conventions, guidelines
- **[Development Roadmap](./docs/project-roadmap.md)** — phases, milestones, v2-upgrade plan
- **[Project Context](./docs/PROJECT-CONTEXT.md)** — Vietnamese context (legacy reference)

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Next.js 16.1.6, TypeScript 5, Tailwind CSS 4, shadcn/ui |
| Backend | Node.js 20, better-sqlite3, SSE, cookie auth |
| Pipeline | Python 3.11+, anthropic SDK, skill-seekers |
| AI Model | Claude Sonnet (primary), Claude Haiku (fallback) |
| Deploy | PM2, Docker, Nginx |
