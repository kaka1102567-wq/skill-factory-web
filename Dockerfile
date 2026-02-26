FROM node:20-slim AS deps
WORKDIR /app
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV BUILD_PHASE=1
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
RUN apt-get update && apt-get install -y python3 python3-pip tesseract-ocr tesseract-ocr-vie && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /app/data/builds /app/data/uploads /app/data/logs /app/data/cache
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
COPY --from=builder /app/pipeline ./pipeline
RUN pip install --no-cache-dir --break-system-packages -r /app/pipeline/requirements.txt && \
    pip install --no-cache-dir --break-system-packages "google-cloud-vision>=3.7.0"
COPY --from=deps /app/node_modules/better-sqlite3 ./node_modules/better-sqlite3
COPY --from=deps /app/node_modules/bindings ./node_modules/bindings
COPY --from=deps /app/node_modules/file-uri-to-path ./node_modules/file-uri-to-path
COPY --from=deps /app/node_modules/prebuild-install ./node_modules/prebuild-install
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
EXPOSE 3000
CMD ["node", "server.js"]
