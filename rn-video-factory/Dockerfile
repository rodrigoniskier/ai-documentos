FROM node:22-bookworm-slim

ENV NODE_ENV=production \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
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
RUN npm install --omit=dev=false \
    && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0 npx playwright-core install ffmpeg \
    && chmod -R a+rX /ms-playwright \
    && test -x "$(find /ms-playwright -path '*/ffmpeg-*/ffmpeg-linux' -type f | head -n 1)"

COPY tsconfig.json ./
COPY src ./src
COPY start-now.sh ./start-now.sh
RUN npm run build \
    && node --input-type=module -e "import {chromium} from 'playwright-core'; import fs from 'node:fs/promises'; const b=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']}); const c=await b.newContext({recordVideo:{dir:'/tmp/pw-video',size:{width:320,height:240}}}); const p=await c.newPage(); await p.setContent('<h1>RN Video Factory</h1>'); await p.waitForTimeout(150); await p.close(); await c.close(); await b.close(); await fs.rm('/tmp/pw-video',{recursive:true,force:true});" \
    && npm prune --omit=dev \
    && chmod +x /app/start-now.sh

RUN mkdir -p /data /app/output && chown -R node:node /data /app/output /app /ms-playwright
USER node

EXPOSE 10000
ENTRYPOINT ["dumb-init", "--"]
CMD ["/app/start-now.sh"]
