import 'dotenv/config';

import crypto from 'node:crypto';
import fs from 'node:fs/promises';

import express from 'express';

import {config, jobsDir, stateFile} from './config.js';
import {runPipeline} from './pipeline.js';
import type {GenerationResult} from './types.js';
import {loadYoutubeToken, oauthClient, saveYoutubeToken} from './youtube.js';

let currentJob: Promise<GenerationResult> | null = null;

function requireAdmin(req: express.Request, res: express.Response, next: express.NextFunction) {
  if (!config.adminToken) return next();
  const token = String(req.query.token || req.headers['x-admin-token'] || req.body?.token || '');
  const received = crypto.createHash('sha256').update(token).digest();
  const expected = crypto.createHash('sha256').update(config.adminToken).digest();
  if (crypto.timingSafeEqual(received, expected)) return next();
  res.status(401).send('Token administrativo inválido.');
}

function dashboardHtml(youtubeConnected: boolean): string {
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RN Video Factory</title><style>body{font-family:Arial,sans-serif;background:#071c3b;color:#fff;margin:0;min-height:100vh;display:grid;place-items:center}.card{width:min(760px,88vw);background:#fff;color:#071c3b;padding:42px;border-radius:24px;box-shadow:0 20px 60px #0008}h1{margin:0 0 8px;font-size:42px}.tag{display:inline-block;background:#ffd21f;padding:8px 14px;border-radius:999px;font-weight:800}.status{margin:24px 0;padding:18px;border-radius:14px;background:#eef4ff}.actions{display:flex;gap:12px;flex-wrap:wrap}button{border:0;border-radius:12px;padding:14px 18px;font-weight:800;cursor:pointer}.primary{background:#0b4ea2;color:#fff}.secondary{background:#ffd21f;color:#071c3b}input{padding:14px;border:1px solid #bbc7da;border-radius:10px;width:min(360px,90%)}small{display:block;margin-top:24px;color:#556}</style></head><body><main class="card"><span class="tag">PRODUÇÃO AUTOMÁTICA</span><h1>RN Video Factory</h1><p>Roteiro, voz OpenAI, captura da aplicação, montagem e publicação no YouTube.</p><div class="status">YouTube: <strong>${youtubeConnected ? 'conectado' : 'aguardando autorização'}</strong></div><div class="actions"><form method="get" action="/youtube/connect"><input name="token" type="password" placeholder="Token administrativo" required><button class="secondary" type="submit">Conectar YouTube</button></form><form method="post" action="/generate"><input name="token" type="password" placeholder="Token administrativo" required><button class="primary" type="submit">Gerar e publicar agora</button></form></div><small>A rotina diária permanece desativada até DAILY_ENABLED=true.</small></main></body></html>`;
}

function scheduleNextDailyRun(): void {
  if (!config.dailyEnabled) return;
  const now = new Date();
  const next = new Date(now);
  next.setHours(config.dailyHour, config.dailyMinute, 0, 0);
  if (next <= now) next.setDate(next.getDate() + 1);
  console.log(`Próxima produção diária: ${next.toString()}`);
  setTimeout(async () => {
    try {
      if (!currentJob) {
        currentJob = runPipeline({publish: true});
        await currentJob;
      }
    } catch (error) {
      console.error('Produção diária falhou:', error);
    } finally {
      currentJob = null;
      scheduleNextDailyRun();
    }
  }, next.getTime() - now.getTime());
}

async function startServer(): Promise<void> {
  await fs.mkdir(config.dataDir, {recursive: true});
  await fs.mkdir(jobsDir, {recursive: true});
  const app = express();
  app.use(express.urlencoded({extended: false}));
  app.use(express.json());

  app.get('/health', (_req, res) => res.json({ok: true, name: 'RN Video Factory'}));
  app.get('/', async (_req, res) => res.send(dashboardHtml(Boolean(await loadYoutubeToken()))));
  app.get('/youtube/connect', requireAdmin, async (_req, res, next) => {
    try {
      const state = crypto.randomBytes(24).toString('hex');
      await fs.writeFile(stateFile, JSON.stringify({state, createdAt: Date.now()}), {mode: 0o600});
      res.redirect(oauthClient().generateAuthUrl({
        access_type: 'offline',
        prompt: 'consent',
        scope: ['https://www.googleapis.com/auth/youtube.upload'],
        state,
      }));
    } catch (error) { next(error); }
  });
  app.get('/youtube/callback', async (req, res, next) => {
    try {
      const code = String(req.query.code || '');
      const state = String(req.query.state || '');
      const stored = JSON.parse(await fs.readFile(stateFile, 'utf8')) as {state: string; createdAt: number};
      if (!code || state !== stored.state || Date.now() - stored.createdAt > 15 * 60 * 1000) throw new Error('Autorização OAuth inválida ou expirada.');
      const {tokens} = await oauthClient().getToken(code);
      await saveYoutubeToken(tokens as Record<string, unknown>);
      res.send('<h1>YouTube conectado.</h1><p>Volte ao painel e clique em “Gerar e publicar agora”.</p>');
    } catch (error) { next(error); }
  });
  app.post('/generate', requireAdmin, async (_req, res, next) => {
    try {
      if (currentJob) return res.status(409).send('Já existe uma produção em andamento.');
      currentJob = runPipeline({publish: true});
      const result = await currentJob;
      res.send(`<h1>Vídeo publicado.</h1><p><a href="${result.youtubeUrl}">${result.youtubeUrl}</a></p>`);
    } catch (error) { next(error); }
    finally { currentJob = null; }
  });
  app.post('/generate-only', requireAdmin, async (_req, res, next) => {
    try {
      if (currentJob) return res.status(409).send('Já existe uma produção em andamento.');
      currentJob = runPipeline({publish: false});
      res.json(await currentJob);
    } catch (error) { next(error); }
    finally { currentJob = null; }
  });
  app.use((error: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
    console.error(error);
    res.status(500).send(`Falha na operação: ${error instanceof Error ? error.message : 'erro desconhecido'}`);
  });

  app.listen(config.port, '0.0.0.0', () => console.log(`RN Video Factory em http://0.0.0.0:${config.port}`));
  scheduleNextDailyRun();
}

if (process.argv.includes('--generate')) {
  runPipeline({publish: process.argv.includes('--publish')})
    .then((result) => console.log(JSON.stringify(result, null, 2)))
    .catch((error) => { console.error(error); process.exitCode = 1; });
} else {
  startServer().catch((error) => { console.error(error); process.exitCode = 1; });
}
