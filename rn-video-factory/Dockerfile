FROM node:22-bookworm-slim

ENV NODE_ENV=production \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    CHROME_EXECUTABLE=/usr/bin/chromium \
    DATA_DIR=/data \
    TZ=America/Recife

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       chromium \
       ffmpeg \
       ca-certificates \
       fonts-liberation \
       fonts-dejavu-core \
       fonts-noto-core \
       fonts-noto-color-emoji \
       dumb-init \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev=false

COPY tsconfig.json ./
COPY src ./src
COPY start-now.sh ./start-now.sh
RUN npm run build \
    && npm prune --omit=dev \
    && chmod +x /app/start-now.sh

RUN mkdir -p /data /app/output && chown -R node:node /data /app/output /app
USER node

EXPOSE 10000
ENTRYPOINT ["dumb-init", "--"]
CMD ["/app/start-now.sh"]
