import 'dotenv/config';

import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';

import express from 'express';

import {config, jobsDir} from './config.js';
import {runPipeline} from './pipeline.js';
import type {GenerationResult} from './types.js';

let currentJob: Promise<GenerationResult> | null = null;
let lastError = '';

function requireAdmin(req: express.Request, res: express.Response, next: express.NextFunction) {
  if (!config.adminToken) return next();
  const token = String(req.query.token || req.headers['x-admin-token'] || req.body?.token || '');
  const received = crypto.createHash('sha256').update(token).digest();
  const expected = crypto.createHash('sha256').update(config.adminToken).digest();
  if (crypto.timingSafeEqual(received, expected)) return next();
  res.status(401).send('Token administrativo inválido.');
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    return (await fs.stat(filePath)).isFile();
  } catch {
    return false;
  }
}

async function readLatestResult(): Promise<GenerationResult | null> {
  let entries: string[] = [];
  try {
    entries = (await fs.readdir(jobsDir, {withFileTypes: true}))
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort()
      .reverse();
  } catch {
    return null;
  }

  for (const id of entries) {
    const jobDir = path.join(jobsDir, id);
    try {
      const raw = JSON.parse(await fs.readFile(path.join(jobDir, 'result.json'), 'utf8')) as Partial<GenerationResult>;
      const videoPath = path.join(jobDir, 'video-final.mp4');
      if (!raw.plan || !(await fileExists(videoPath))) continue;
      return {
        id,
        createdAt: String(raw.createdAt || id),
        videoPath,
        thumbnailPath: path.join(jobDir, 'thumbnail.jpg'),
        publicationTextPath: path.join(jobDir, 'publicacao.txt'),
        plan: raw.plan,
      };
    } catch {
      continue;
    }
  }
  return null;
}

function publicResult(result: GenerationResult | null) {
  if (!result) return null;
  return {
    id: result.id,
    createdAt: result.createdAt,
    plan: result.plan,
    files: {
      video: 'video-final.mp4',
      thumbnail: 'thumbnail.jpg',
      publicationText: 'publicacao.txt',
      plan: 'plan.json',
    },
  };
}

function startProduction(origin: string): boolean {
  if (currentJob) return false;
  lastError = '';
  console.log(`Produção iniciada por ${origin}.`);
  currentJob = runPipeline();
  currentJob
    .then((result) => console.log(`Produção ${result.id} concluída e pronta para publicação manual.`))
    .catch((error: unknown) => {
      lastError = error instanceof Error ? error.message : 'Erro desconhecido';
      console.error('Produção falhou:', error);
    })
    .finally(() => {
      currentJob = null;
    });
  return true;
}

function dashboardHtml(): string {
  const channel = config.channelName.replace(/[&<>"']/g, (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character] || character));
  return `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>RN Video Factory</title>
  <style>
    :root{color-scheme:light;--navy:#071c3b;--blue:#0b4ea2;--yellow:#ffd21f;--paper:#fff;--muted:#5d6b7e;--line:#d9e2ef}
    *{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#eef3fa;color:var(--navy);margin:0;min-height:100vh}.top{background:var(--navy);color:#fff;padding:28px 5vw}.top h1{margin:5px 0;font-size:clamp(30px,5vw,48px)}.tag{display:inline-block;background:var(--yellow);color:var(--navy);padding:7px 12px;border-radius:999px;font-weight:800}.wrap{width:min(1180px,92vw);margin:24px auto 60px;display:grid;gap:20px}.card{background:var(--paper);border-radius:20px;padding:24px;box-shadow:0 10px 35px #17375e18}.login{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.login input{min-width:280px}.status{padding:14px;border-radius:12px;background:#edf4ff;margin:14px 0}.error{background:#fff0f0;color:#8a1010}.grid{display:grid;grid-template-columns:1.1fr .9fr;gap:20px}@media(max-width:850px){.grid{grid-template-columns:1fr}}input,textarea{font:inherit;padding:12px;border:1px solid var(--line);border-radius:10px;width:100%}textarea{min-height:92px;resize:vertical}button,.button{border:0;border-radius:11px;padding:13px 17px;font-weight:800;cursor:pointer;text-decoration:none;display:inline-block}.primary{background:var(--blue);color:#fff}.secondary{background:var(--yellow);color:var(--navy)}.quiet{background:#e8eef6;color:var(--navy)}button:disabled{opacity:.55;cursor:wait}.actions{display:flex;gap:9px;flex-wrap:wrap;margin:12px 0}.field{margin:14px 0}.field label{display:block;font-weight:800;margin-bottom:6px}video{width:min(100%,370px);max-height:620px;background:#000;border-radius:16px;display:block;margin:auto}.thumb{width:100%;border-radius:14px;border:1px solid var(--line)}.hidden{display:none}.small{color:var(--muted);font-size:14px}.ready{color:#126336;font-weight:800}.working{color:#8a5b00;font-weight:800}
  </style>
</head>
<body>
  <header class="top"><span class="tag">PUBLICAÇÃO MANUAL ASSISTIDA</span><h1>RN Video Factory</h1><p>Produção automática para o canal <strong>${channel}</strong>.</p></header>
  <main class="wrap">
    <section class="card">
      <h2>Acesso</h2>
      <div class="login"><input id="token" type="password" placeholder="Cole o ADMIN_TOKEN do Render"><button class="secondary" id="access">Acessar painel</button><button class="primary" id="generate" disabled>Gerar novo vídeo agora</button></div>
      <div id="status" class="status">Informe o token administrativo para carregar a produção.</div>
      <p class="small">A produção diária está ${config.dailyEnabled ? `ativada para ${String(config.dailyHour).padStart(2, '0')}:${String(config.dailyMinute).padStart(2, '0')}` : 'desativada'}.</p>
    </section>

    <section id="latest" class="grid hidden">
      <article class="card">
        <h2>Vídeo pronto</h2>
        <video id="video" controls playsinline></video>
        <div class="actions"><button class="primary" data-download="video-final.mp4">Baixar vídeo MP4</button><button class="quiet" data-download="thumbnail.jpg">Baixar miniatura</button><button class="quiet" data-download="publicacao.txt">Baixar texto completo</button></div>
        <a class="button secondary" href="${config.youtubeStudioUrl}" target="_blank" rel="noopener">Abrir YouTube Studio</a>
        <p id="created" class="small"></p>
      </article>

      <article class="card">
        <h2>Miniatura e publicação</h2>
        <img id="thumbnail" class="thumb" alt="Miniatura automática do vídeo">
        <div class="field"><label for="title">Título</label><textarea id="title" readonly></textarea><button class="quiet" data-copy="title">Copiar título</button></div>
        <div class="field"><label for="description">Descrição</label><textarea id="description" readonly></textarea><button class="quiet" data-copy="description">Copiar descrição</button></div>
        <div class="field"><label for="tags">Tags</label><textarea id="tags" readonly></textarea><button class="quiet" data-copy="tags">Copiar tags</button></div>
      </article>
    </section>
  </main>
<script>
  const tokenInput = document.getElementById('token');
  const accessButton = document.getElementById('access');
  const generateButton = document.getElementById('generate');
  const statusBox = document.getElementById('status');
  const latestSection = document.getElementById('latest');
  let latest = null;
  let loadedId = '';
  let videoUrl = '';
  let thumbnailUrl = '';

  tokenInput.value = sessionStorage.getItem('rn-video-token') || '';

  function currentToken() {
    return tokenInput.value.trim();
  }

  async function request(url, options) {
    const settings = options || {};
    settings.headers = Object.assign({}, settings.headers || {}, {'x-admin-token': currentToken()});
    const response = await fetch(url, settings);
    if (!response.ok) throw new Error(await response.text());
    return response;
  }

  function setStatus(message, kind) {
    statusBox.textContent = message;
    statusBox.className = 'status ' + (kind || '');
  }

  async function loadBlob(fileName) {
    const response = await request('/files/' + encodeURIComponent(latest.id) + '/' + encodeURIComponent(fileName));
    return response.blob();
  }

  async function loadPreviews() {
    if (!latest || loadedId === latest.id) return;
    loadedId = latest.id;
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    if (thumbnailUrl) URL.revokeObjectURL(thumbnailUrl);
    videoUrl = URL.createObjectURL(await loadBlob('video-final.mp4'));
    document.getElementById('video').src = videoUrl;
    try {
      thumbnailUrl = URL.createObjectURL(await loadBlob('thumbnail.jpg'));
      document.getElementById('thumbnail').src = thumbnailUrl;
    } catch {
      document.getElementById('thumbnail').removeAttribute('src');
    }
  }

  function renderLatest(data) {
    latest = data.latest;
    generateButton.disabled = Boolean(data.running);
    if (data.running) setStatus('Produção em andamento. O painel será atualizado automaticamente.', 'working');
    else if (data.lastError) setStatus('A última produção falhou: ' + data.lastError, 'error');
    else if (latest) setStatus('Vídeo pronto para publicação manual no YouTube.', 'ready');
    else setStatus('Nenhum vídeo foi produzido ainda. Clique em “Gerar novo vídeo agora”.');

    if (!latest) {
      latestSection.classList.add('hidden');
      return;
    }
    latestSection.classList.remove('hidden');
    document.getElementById('title').value = latest.plan.title;
    document.getElementById('description').value = latest.plan.description;
    document.getElementById('tags').value = latest.plan.tags.join(', ');
    document.getElementById('created').textContent = 'Gerado em: ' + new Date(latest.createdAt).toLocaleString('pt-BR');
    loadPreviews().catch(function(error){ setStatus('Falha ao carregar a prévia: ' + error.message, 'error'); });
  }

  async function refresh() {
    if (!currentToken()) return;
    sessionStorage.setItem('rn-video-token', currentToken());
    try {
      const response = await request('/api/status');
      renderLatest(await response.json());
    } catch (error) {
      generateButton.disabled = true;
      latestSection.classList.add('hidden');
      setStatus(error.message, 'error');
    }
  }

  accessButton.addEventListener('click', refresh);
  generateButton.addEventListener('click', async function(){
    generateButton.disabled = true;
    setStatus('Iniciando a produção automática...', 'working');
    try {
      await request('/generate', {method: 'POST'});
      await refresh();
    } catch (error) {
      setStatus(error.message, 'error');
    }
  });

  document.querySelectorAll('[data-copy]').forEach(function(button){
    button.addEventListener('click', async function(){
      const id = button.getAttribute('data-copy');
      const value = document.getElementById(id).value;
      await navigator.clipboard.writeText(value);
      const original = button.textContent;
      button.textContent = 'Copiado';
      setTimeout(function(){ button.textContent = original; }, 1200);
    });
  });

  document.querySelectorAll('[data-download]').forEach(function(button){
    button.addEventListener('click', async function(){
      const fileName = button.getAttribute('data-download');
      const blob = await loadBlob(fileName);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = latest.id + '-' + fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    });
  });

  setInterval(function(){ if (currentToken()) refresh(); }, 8000);
  if (currentToken()) refresh();
</script>
</body>
</html>`;
}

function scheduleNextDailyRun(): void {
  if (!config.dailyEnabled) return;
  const now = new Date();
  const next = new Date(now);
  next.setHours(config.dailyHour, config.dailyMinute, 0, 0);
  if (next <= now) next.setDate(next.getDate() + 1);
  console.log(`Próxima produção diária: ${next.toString()}`);
  setTimeout(() => {
    startProduction('agendamento diário');
    scheduleNextDailyRun();
  }, next.getTime() - now.getTime());
}

async function startServer(): Promise<void> {
  await fs.mkdir(config.dataDir, {recursive: true});
  await fs.mkdir(jobsDir, {recursive: true});
  const app = express();
  app.use(express.urlencoded({extended: false}));
  app.use(express.json());

  app.get('/health', (_req, res) => res.json({ok: true, name: 'RN Video Factory', mode: 'manual-assisted'}));
  app.get('/', (_req, res) => res.send(dashboardHtml()));
  app.get('/api/status', requireAdmin, async (_req, res) => {
    res.json({
      running: Boolean(currentJob),
      lastError,
      latest: publicResult(await readLatestResult()),
      channelName: config.channelName,
      youtubeStudioUrl: config.youtubeStudioUrl,
    });
  });
  app.post('/generate', requireAdmin, (_req, res) => {
    if (!startProduction('painel')) return res.status(409).send('Já existe uma produção em andamento.');
    res.status(202).json({started: true});
  });
  app.get('/files/:jobId/:fileName', requireAdmin, async (req, res, next) => {
    try {
      const jobId = String(req.params.jobId || '');
      const fileName = String(req.params.fileName || '');
      const allowed = new Set(['video-final.mp4', 'thumbnail.jpg', 'publicacao.txt', 'plan.json']);
      if (!/^[0-9TZ-]+$/.test(jobId) || !allowed.has(fileName)) return res.status(400).send('Arquivo inválido.');
      const directory = path.resolve(jobsDir, jobId);
      const fullPath = path.resolve(directory, fileName);
      if (path.dirname(fullPath) !== directory || !(await fileExists(fullPath))) return res.status(404).send('Arquivo não encontrado.');
      res.sendFile(fullPath);
    } catch (error) {
      next(error);
    }
  });
  app.use((error: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
    console.error(error);
    res.status(500).send(`Falha na operação: ${error instanceof Error ? error.message : 'erro desconhecido'}`);
  });

  app.listen(config.port, '0.0.0.0', () => console.log(`RN Video Factory em http://0.0.0.0:${config.port}`));
  scheduleNextDailyRun();
}

if (process.argv.includes('--generate')) {
  runPipeline()
    .then((result) => console.log(JSON.stringify(publicResult(result), null, 2)))
    .catch((error) => { console.error(error); process.exitCode = 1; });
} else {
  startServer().catch((error) => { console.error(error); process.exitCode = 1; });
}
