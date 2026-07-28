import fs from 'node:fs/promises';
import OpenAI from 'openai';

import {config} from './config.js';
import type {VideoPlan} from './types.js';

const openai = new OpenAI({apiKey: config.openaiApiKey});

export const fallbackPlan: VideoPlan = {
  hook: 'Quanto tempo um professor perde preenchendo, formatando e organizando questões?',
  narration: 'Quanto tempo um professor perde preenchendo, formatando e organizando questões? Neste sistema, o docente seleciona o período, escolhe o componente curricular e define o tipo de questão em poucos passos. O fluxo padroniza o envio, reduz retrabalho e facilita a gestão do banco de questões. Isto é apenas uma demonstração do que processos inteligentes podem fazer por uma instituição. Descubra como o trabalho da sua instituição pode ficar mais inteligente.',
  title: 'Como tornar a gestão de questões mais inteligente',
  description: 'Uma demonstração prática de como processos acadêmicos podem ser simplificados com ferramentas personalizadas.\n\nConheça possibilidades de implementação inteligente para escolas e faculdades.',
  tags: ['inteligência artificial', 'educação', 'gestão acadêmica', 'automação', 'professores'],
  cta: config.cta,
  scenes: [
    {caption: 'Quanto tempo se perde com tarefas repetitivas?', shot: 'inicio'},
    {caption: 'Selecione o período em poucos segundos.', shot: 'periodo'},
    {caption: 'Organize as questões por componente curricular.', shot: 'componente'},
    {caption: 'Padronize cada tipo de questão.', shot: 'tipo'},
    {caption: 'Menos retrabalho. Mais inteligência institucional.', shot: 'formulario'},
  ],
};

function safeJsonObject(text: string): unknown {
  const trimmed = text.trim().replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
  return JSON.parse(trimmed);
}

function normalizePlan(value: unknown): VideoPlan {
  if (!value || typeof value !== 'object') return fallbackPlan;
  const raw = value as Record<string, unknown>;
  const allowedShots = new Set(['inicio', 'periodo', 'componente', 'tipo', 'formulario']);
  const scenes = Array.isArray(raw.scenes)
    ? raw.scenes
        .filter((scene): scene is Record<string, unknown> => Boolean(scene && typeof scene === 'object'))
        .map((scene) => ({
          caption: String(scene.caption || '').slice(0, 110),
          shot: String(scene.shot || 'inicio') as VideoPlan['scenes'][number]['shot'],
        }))
        .filter((scene) => scene.caption.length > 0 && allowedShots.has(scene.shot))
        .slice(0, 5)
    : [];

  return {
    hook: String(raw.hook || fallbackPlan.hook).slice(0, 180),
    narration: String(raw.narration || fallbackPlan.narration).slice(0, 3900),
    title: String(raw.title || fallbackPlan.title).slice(0, 95),
    description: String(raw.description || fallbackPlan.description).slice(0, 4500),
    tags: Array.isArray(raw.tags) ? raw.tags.map(String).map((tag) => tag.slice(0, 30)).slice(0, 12) : fallbackPlan.tags,
    cta: String(raw.cta || config.cta).slice(0, 180),
    scenes: scenes.length >= 3 ? scenes : fallbackPlan.scenes,
  };
}

export async function generatePlan(): Promise<VideoPlan> {
  if (!config.openaiApiKey) throw new Error('OPENAI_API_KEY não configurada.');
  const prompt = `Crie o plano final de um vídeo vertical de 35 a 45 segundos, em português brasileiro, para divulgar serviços de implementação de processos inteligentes em pequenas escolas e faculdades.

Produto demonstrado: ${config.productName}
Página real: ${config.demoUrl}
Fluxo visível: selecionar período, selecionar componente curricular, escolher tipo de questão e avançar ao formulário.
Objetivo: mostrar uma dor real, demonstrar a solução sem exageros e terminar com convite para diagnóstico institucional.
Tom: profissional, claro, humano e comercial, sem jargão técnico.

Retorne SOMENTE JSON válido com esta estrutura:
{"hook":"frase curta","narration":"texto contínuo com 85 a 105 palavras","title":"título para YouTube com até 95 caracteres","description":"descrição curta com chamada para ação","tags":["até 12 tags"],"cta":"${config.cta}","scenes":[{"caption":"texto curto","shot":"inicio"},{"caption":"texto curto","shot":"periodo"},{"caption":"texto curto","shot":"componente"},{"caption":"texto curto","shot":"tipo"},{"caption":"texto curto","shot":"formulario"}]}`;

  try {
    const response = await openai.responses.create({
      model: config.openaiTextModel,
      input: prompt,
      max_output_tokens: 1200,
    });
    return normalizePlan(safeJsonObject(response.output_text));
  } catch (error) {
    console.error('Falha ao gerar plano dinâmico; usando plano editorial final embutido.', error);
    return fallbackPlan;
  }
}

export async function generateSpeech(plan: VideoPlan, destination: string): Promise<void> {
  const response = await openai.audio.speech.create({
    model: config.openaiTtsModel,
    voice: config.openaiTtsVoice as 'marin',
    input: plan.narration,
    instructions: 'Fale em português brasileiro, com voz profissional, segura, natural e acolhedora. Ritmo dinâmico de vídeo curto, sem soar apressado.',
    response_format: 'mp3',
    speed: 1.04,
  });
  await fs.writeFile(destination, Buffer.from(await response.arrayBuffer()));
}
