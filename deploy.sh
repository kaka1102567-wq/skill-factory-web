#!/bin/bash
set -e

echo "🏭 Deploying Skill Factory Web..."
echo "=================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. Check prerequisites
echo -e "${YELLOW}[1/6] Checking prerequisites...${NC}"
command -v node >/dev/null 2>&1 || { echo "❌ Node.js not found. Install Node.js 20+"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python3 not found"; exit 1; }
command -v pm2 >/dev/null 2>&1 || { echo "Installing PM2..."; npm install -g pm2; }

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 20 ]; then
  echo "❌ Node.js 20+ required. Current: $(node -v)"
  exit 1
fi
echo -e "${GREEN}✅ Prerequisites OK${NC}"

# 2. Install dependencies
echo -e "${YELLOW}[2/6] Installing dependencies...${NC}"
npm ci --production=false
echo -e "${GREEN}✅ Dependencies installed${NC}"

# 3. Build Next.js
echo -e "${YELLOW}[3/6] Building Next.js...${NC}"
npm run build
echo -e "${GREEN}✅ Build complete${NC}"

# 4. Setup Python pipeline (if requirements.txt exists)
if [ -f "pipeline/requirements.txt" ]; then
  echo -e "${YELLOW}[4/6] Installing Python dependencies...${NC}"
  pip3 install -r pipeline/requirements.txt --break-system-packages 2>/dev/null || pip3 install -r pipeline/requirements.txt
  echo -e "${GREEN}✅ Python dependencies installed${NC}"
else
  echo -e "${YELLOW}[4/6] No Python requirements.txt found, skipping${NC}"
fi

# 5. Ensure data directories
echo -e "${YELLOW}[5/6] Setting up data directories...${NC}"
mkdir -p data/builds data/uploads data/logs
echo -e "${GREEN}✅ Data directories ready${NC}"

# 6. Start/restart with PM2
echo -e "${YELLOW}[6/6] Starting with PM2...${NC}"
pm2 stop skill-factory 2>/dev/null || true
pm2 delete skill-factory 2>/dev/null || true
pm2 start ecosystem.config.js
pm2 save

echo ""
echo -e "${GREEN}✅ Skill Factory deployed successfully!${NC}"
echo "=================================="
echo "🌐 Access: http://$(hostname -I | awk '{print $1}'):3000"
echo "📊 PM2 status: pm2 status"
echo "📝 Logs: pm2 logs skill-factory"
echo "🔄 Restart: pm2 restart skill-factory"
