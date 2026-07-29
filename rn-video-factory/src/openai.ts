import fs from 'node:fs/promises';
import OpenAI from 'openai';

import {config} from './config.js';
import type {VideoPlan} from './types.js';

const openai = new OpenAI({apiKey: config.openaiApiKey});

export const fallbackPlan: VideoPlan = {
  hook: 'Quanto do seu fim de semana ainda é consumido por tarefas acadêmicas mecânicas?',
  narration: 'Professor, quanto do seu fim de semana ainda é consumido preenchendo, formatando e organizando questões? O método tradicional espalha informações entre arquivos, mensagens, planilhas e pilhas de papel. Além do tempo perdido, cada formato diferente aumenta o retrabalho e dificulta a gestão do banco de questões. Agora veja uma alternativa mais inteligente. Nesta aplicação, o professor começa selecionando o período e o componente curricular. Em seguida, escolhe o tipo de questão e avança para um formulário padronizado. Cada etapa aparece na ordem correta, com os campos necessários para registrar o conteúdo acadêmico de maneira clara e consistente. Durante a demonstração, perceba que o sistema não substitui a autoria nem o julgamento do professor. Ele organiza o processo, reduz erros de preenchimento e elimina boa parte do trabalho mecânico que não agrega valor ao ensino. Ao final, a questão fica estruturada para revisão e gestão institucional, sem depender de documentos dispersos ou conferências manuais. O resultado é mais previsibilidade, mais padronização e menos desgaste. Quando processos repetitivos são automatizados, o professor recupera tempo para estudar, orientar estudantes e aperfeiçoar a aprendizagem. Sua instituição também pode transformar rotinas como esta. Solicite um diagnóstico dos processos acadêmicos e descubra onde a tecnologia pode gerar resultados concretos.',
  title: 'Como reduzir o retrabalho na gestão de questões acadêmicas',
  description: 'Uma demonstração prática de como a submissão e a gestão de questões podem ser padronizadas, reduzindo tarefas mecânicas e retrabalho institucional.\n\nA apresentadora exibida é virtual e as cenas humanas são ilustrativas. A demonstração da aplicação é real.\n\nSolicite um diagnóstico dos processos da sua instituição.',
  tags: ['inteligência artificial', 'educação', 'gestão acadêmica', 'automação', 'professores', 'banco de questões', 'processos inteligentes'],
  cta: config.cta,
  closing: 'Mais padronização. Menos retrabalho. Mais tempo para ensinar.',
  presenterLine: 'Veja como o fluxo acadêmico pode ser organizado em poucos passos.',
  scenes: [
    {caption: 'Selecione o período acadêmico.', shot: 'periodo'},
    {caption: 'Escolha o componente curricular.', shot: 'componente'},
    {caption: 'Defina o tipo de questão.', shot: 'tipo'},
    {caption: 'Preencha um formulário estruturado.', shot: 'formulario'},
    {caption: 'A autoria permanece com o professor; o trabalho mecânico fica com o sistema.', shot: 'formulario'},
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
          caption: String(scene.caption || '').slice(0, 150),
          shot: String(scene.shot || 'inicio') as VideoPlan['scenes'][number]['shot'],
        }))
        .filter((scene) => scene.caption.length > 0 && allowedShots.has(scene.shot))
        .slice(0, 6)
    : [];

  return {
    hook: String(raw.hook || fallbackPlan.hook).slice(0, 180),
    narration: String(raw.narration || fallbackPlan.narration).slice(0, 3900),
    title: String(raw.title || fallbackPlan.title).slice(0, 95),
    description: String(raw.description || fallbackPlan.description).slice(0, 4500),
    tags: Array.isArray(raw.tags) ? raw.tags.map(String).map((tag) => tag.slice(0, 35)).slice(0, 12) : fallbackPlan.tags,
    cta: String(raw.cta || config.cta).slice(0, 180),
    closing: String(raw.closing || fallbackPlan.closing).slice(0, 180),
    presenterLine: String(raw.presenterLine || fallbackPlan.presenterLine).slice(0, 180),
    scenes: scenes.length >= 4 ? scenes : fallbackPlan.scenes,
  };
}

export async function generatePlan(): Promise<VideoPlan> {
  if (!config.openaiApiKey) throw new Error('OPENAI_API_KEY não configurada.');
  const prompt = `Crie o roteiro final de um vídeo profissional horizontal 16:9, com aproximadamente 1 minuto e 45 segundos a 2 minutos, em português brasileiro, para o canal ${config.channelName}.

Produto demonstrado: ${config.productName}
Página real: ${config.demoUrl}
Fluxo que realmente existe: selecionar período, selecionar componente curricular, escolher o tipo de questão, avançar e preencher um formulário estruturado.

IMPORTANTE: esta aplicação não gera questões por inteligência artificial e não monta a prova instantaneamente. Ela padroniza a submissão, organiza as informações e facilita a gestão institucional. Não atribua funcionalidades inexistentes.

Estrutura narrativa:
1. dor do método tradicional, com empatia pelo professor;
2. transição para a solução e apresentação virtual claramente identificada;
3. demonstração prática do fluxo real;
4. contraste com o tempo recuperado;
5. chamada comercial para diagnóstico institucional.

Tom: cinematográfico, profissional, claro, humano e comercial. Evite exageros, depoimentos falsos, promessas absolutas e jargão técnico. A narração deve ter entre 190 e 230 palavras.

Retorne SOMENTE JSON válido com esta estrutura:
{"hook":"frase curta","narration":"texto contínuo de 190 a 230 palavras","title":"título para YouTube com até 95 caracteres","description":"descrição curta; informe que a apresentadora é virtual e as cenas humanas são ilustrativas","tags":["até 12 tags"],"cta":"${config.cta}","closing":"frase de contraste final","presenterLine":"frase curta de apresentação da solução","scenes":[{"caption":"texto curto","shot":"periodo"},{"caption":"texto curto","shot":"componente"},{"caption":"texto curto","shot":"tipo"},{"caption":"texto curto","shot":"formulario"},{"caption":"texto curto","shot":"formulario"}]}`;

  try {
    const response = await openai.responses.create({
      model: config.openaiTextModel,
      input: prompt,
      max_output_tokens: 1800,
    });
    return normalizePlan(safeJsonObject(response.output_text));
  } catch (error) {
    console.error('Falha ao gerar roteiro dinâmico; usando roteiro profissional embutido.', error);
    return fallbackPlan;
  }
}

export async function generateSpeech(plan: VideoPlan, destination: string): Promise<void> {
  const response = await openai.audio.speech.create({
    model: config.openaiTtsModel,
    voice: config.openaiTtsVoice as 'marin',
    input: plan.narration,
    instructions: 'Fale em português brasileiro, com voz feminina profissional, segura, calorosa e persuasiva. Use pausas naturais, ênfase moderada nas perguntas e ritmo de documentário tecnológico, sem soar apressada ou artificial.',
    response_format: 'mp3',
    speed: 0.97,
  });
  await fs.writeFile(destination, Buffer.from(await response.arrayBuffer()));
}
