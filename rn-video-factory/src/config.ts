import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
export const projectRoot = path.resolve(__dirname, '..');

export const config = {
  port: Number(process.env.PORT || 10000),
  adminToken: process.env.ADMIN_TOKEN || '',
  openaiApiKey: process.env.OPENAI_API_KEY || '',
  openaiTextModel: process.env.OPENAI_TEXT_MODEL || 'gpt-5.4-mini',
  openaiTtsModel: process.env.OPENAI_TTS_MODEL || 'gpt-4o-mini-tts',
  openaiTtsVoice: process.env.OPENAI_TTS_VOICE || 'marin',
  demoUrl: process.env.DEMO_URL || 'https://rodrigoniskier.pythonanywhere.com/app/submeter/',
  productName: process.env.DEMO_PRODUCT_NAME || 'Gestão Inteligente de Questões',
  cta: process.env.DEMO_CTA || 'Descubra como o trabalho da sua instituição pode ficar mais inteligente.',
  channelName: process.env.YOUTUBE_CHANNEL_NAME || 'AI LAB Rodrigo Niskier',
  youtubeStudioUrl: process.env.YOUTUBE_STUDIO_URL || 'https://studio.youtube.com',
  chromeExecutable: process.env.CHROME_EXECUTABLE || '/usr/bin/chromium',
  dataDir: process.env.DATA_DIR || path.join(projectRoot, 'output'),
  dailyEnabled: String(process.env.MANUAL_ASSISTED_DAILY_ENABLED || 'true').toLowerCase() === 'true',
  dailyHour: Number(process.env.DAILY_HOUR || 8),
  dailyMinute: Number(process.env.DAILY_MINUTE || 0),
  jobRetentionCount: Math.max(5, Number(process.env.JOB_RETENTION_COUNT || 30)),
};

export const jobsDir = path.join(config.dataDir, 'jobs');
