import fs from 'node:fs/promises';
import path from 'node:path';

import OpenAI from 'openai';

import {config, professionalAssetsDir} from './config.js';
import type {VisualAssets} from './types.js';

const openai = new OpenAI({apiKey: config.openaiApiKey});

const prompts: Record<keyof VisualAssets, string> = {
  painDesk: 'Fotografia cinematográfica horizontal 16:9 de uma professora universitária fictícia trabalhando tarde da noite, cercada por livros, provas impressas, marcadores e anotações. Iluminação dramática de luminária de mesa, expressão de cansaço e alta carga cognitiva, ambiente acadêmico brasileiro contemporâneo, realista, elegante, sem logotipos, sem texto legível, sem marcas.',
  painHands: 'Close cinematográfico horizontal 16:9 de mãos de uma professora fictícia elaborando questões de múltipla escolha em papel e computador, livros abertos, rascunhos, canetas e muitas folhas sobre a mesa. Luz noturna quente, sensação de trabalho manual repetitivo, realista, sofisticado, sem logotipos e sem texto legível.',
  presenter: 'Retrato cinematográfico horizontal 16:9 de uma professora universitária fictícia em home office moderno e bem iluminado, livros e planta ao fundo, roupa profissional discreta, olhando diretamente para a câmera e gesticulando de forma natural como em um tutorial. Composição limpa, acolhedora e tecnológica, espaço visual equilibrado, sem logotipos, sem texto.',
  relief: 'Fotografia cinematográfica horizontal 16:9 de uma professora universitária fictícia fechando o notebook com tranquilidade durante a tarde, café ao lado, luz natural, sensação de alívio e tempo recuperado, ambiente acadêmico moderno com campus ao fundo, realista, otimista, sem logotipos e sem texto.',
  ctaBackground: 'Fundo abstrato horizontal 16:9 premium para vídeo de tecnologia educacional, azul-marinho profundo, detalhes luminosos amarelos e azuis, linhas sutis de dados e movimento, elegante, moderno, alto contraste, centro livre para inserir logotipo e chamada, sem texto e sem marcas.',
};

async function usable(filePath: string): Promise<boolean> {
  try {
    return (await fs.stat(filePath)).size > 10_000;
  } catch {
    return false;
  }
}

async function generateImage(prompt: string, destination: string): Promise<void> {
  const response = await (openai.images.generate as any)({
    model: config.openaiImageModel,
    prompt,
    size: '1536x1024',
    quality: 'medium',
    output_format: 'jpeg',
    n: 1,
  });
  const base64 = response?.data?.[0]?.b64_json;
  if (!base64) throw new Error('A API de imagens não retornou conteúdo em base64.');
  await fs.writeFile(destination, Buffer.from(base64, 'base64'));
}

export async function ensureVisualAssets(fallbackSource: string): Promise<VisualAssets> {
  await fs.mkdir(professionalAssetsDir, {recursive: true});
  const assets = {
    painDesk: path.join(professionalAssetsDir, 'pain-desk.jpg'),
    painHands: path.join(professionalAssetsDir, 'pain-hands.jpg'),
    presenter: path.join(professionalAssetsDir, 'presenter.jpg'),
    relief: path.join(professionalAssetsDir, 'relief.jpg'),
    ctaBackground: path.join(professionalAssetsDir, 'cta-background.jpg'),
  } satisfies VisualAssets;

  for (const key of Object.keys(assets) as Array<keyof VisualAssets>) {
    const destination = assets[key];
    if (await usable(destination)) continue;
    try {
      if (!config.visualAssetsEnabled || !config.openaiApiKey) throw new Error('Geração visual desativada.');
      console.log(`Gerando ativo visual profissional: ${key}`);
      await generateImage(prompts[key], destination);
    } catch (error) {
      console.error(`Falha ao gerar ${key}; usando captura real como alternativa.`, error);
      await fs.copyFile(fallbackSource, destination);
    }
  }

  return assets;
}
