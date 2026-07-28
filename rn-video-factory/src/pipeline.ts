import fs from 'node:fs/promises';
import path from 'node:path';

import {captureDemo} from './capture.js';
import {jobsDir} from './config.js';
import {generatePlan, generateSpeech} from './openai.js';
import {renderVideo} from './render.js';
import type {GenerationResult} from './types.js';
import {uploadToYoutube} from './youtube.js';

export async function runPipeline({publish = true}: {publish?: boolean} = {}): Promise<GenerationResult> {
  await fs.mkdir(jobsDir, {recursive: true});
  const id = new Date().toISOString().replace(/[:.]/g, '-');
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

  console.log(`[${id}] Renderizando vídeo...`);
  const videoPath = await renderVideo(jobDir, plan, shots, audioPath);
  const result: GenerationResult = {id, videoPath, plan};

  if (publish) {
    console.log(`[${id}] Publicando no YouTube...`);
    const uploaded = await uploadToYoutube(videoPath, plan);
    result.youtubeVideoId = uploaded.id;
    result.youtubeUrl = uploaded.url;
  }

  await fs.writeFile(path.join(jobDir, 'result.json'), JSON.stringify(result, null, 2));
  console.log(`[${id}] Concluído: ${result.youtubeUrl || videoPath}`);
  return result;
}
