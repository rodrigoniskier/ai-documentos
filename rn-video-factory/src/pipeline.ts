import fs from 'node:fs/promises';
import path from 'node:path';

import {captureDemo} from './capture.js';
import {config, jobsDir} from './config.js';
import {generatePlan, generateSpeech} from './openai.js';
import {renderThumbnail, renderVideo} from './render.js';
import type {GenerationResult, VideoPlan} from './types.js';

function publicationText(plan: VideoPlan): string {
  const hashtags = plan.tags
    .map((tag) => `#${tag.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9]+/g, '')}`)
    .filter((tag) => tag.length > 1)
    .join(' ');
  return [
    `CANAL: ${config.channelName}`,
    '',
    'TÍTULO',
    plan.title,
    '',
    'DESCRIÇÃO',
    plan.description,
    '',
    'HASHTAGS',
    hashtags,
    '',
    'TAGS DO YOUTUBE',
    plan.tags.join(', '),
    '',
    'PUBLICAÇÃO MANUAL ASSISTIDA',
    '1. Baixe o vídeo e a miniatura no painel.',
    '2. Abra o YouTube Studio.',
    '3. Envie o vídeo, cole o título e a descrição e aplique a miniatura.',
    '4. Revise a visibilidade e publique ou agende.',
  ].join('\n');
}

async function cleanupOldJobs(): Promise<void> {
  const entries = await fs.readdir(jobsDir, {withFileTypes: true});
  const directories = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort().reverse();
  for (const oldId of directories.slice(config.jobRetentionCount)) {
    await fs.rm(path.join(jobsDir, oldId), {recursive: true, force: true});
  }
}

export async function runPipeline(): Promise<GenerationResult> {
  await fs.mkdir(jobsDir, {recursive: true});
  const createdAt = new Date().toISOString();
  const id = createdAt.replace(/[:.]/g, '-');
  const jobDir = path.join(jobsDir, id);
  await fs.mkdir(jobDir, {recursive: true});

  console.log(`[${id}] Gerando plano editorial...`);
  const plan = await generatePlan();
  await fs.writeFile(path.join(jobDir, 'plan.json'), JSON.stringify(plan, null, 2));

  console.log(`[${id}] Gerando narração...`);
  const audioPath = path.join(jobDir, 'audio.mp3');
  await generateSpeech(plan, audioPath);

  console.log(`[${id}] Capturando demonstração...`);
  const shots = await captureDemo(jobDir);

  console.log(`[${id}] Renderizando vídeo e miniatura...`);
  const videoPath = await renderVideo(jobDir, plan, shots, audioPath);
  const thumbnailPath = await renderThumbnail(jobDir, plan, shots);
  const publicationTextPath = path.join(jobDir, 'publicacao.txt');
  await fs.writeFile(publicationTextPath, publicationText(plan));

  const result: GenerationResult = {
    id,
    createdAt,
    videoPath,
    thumbnailPath,
    publicationTextPath,
    plan,
  };
  await fs.writeFile(path.join(jobDir, 'result.json'), JSON.stringify(result, null, 2));
  await cleanupOldJobs();
  console.log(`[${id}] Pacote de publicação concluído: ${videoPath}`);
  return result;
}
