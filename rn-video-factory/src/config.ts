import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
export const projectRoot = path.resolve(__dirname, '..');

const privacy = process.env.YOUTUBE_PRIVACY_STATUS || '';

export const config = {
  port: Number(process.env.PORT || 10000),
  publicBaseUrl: (process.env.PUBLIC_BASE_URL || `http://localhost:${process.env.PORT || 10000}`).replace(/\/$/, ''),
  adminToken: process.env.ADMIN_TOKEN || '',
  openaiApiKey: process.env.OPENAI_API_KEY || '',
  openaiTextModel: process.env.OPENAI_TEXT_MODEL || 'gpt-5.4-mini',
  openaiTtsModel: process.env.OPENAI_TTS_MODEL || 'gpt-4o-mini-tts',
  openaiTtsVoice: process.env.OPENAI_TTS_VOICE || 'marin',
  demoUrl: process.env.DEMO_URL || 'https://rodrigoniskier.pythonanywhere.com/app/submeter/',
  productName: process.env.DEMO_PRODUCT_NAME || 'Gestão Inteligente de Questões',
  cta: process.env.DEMO_CTA || 'Descubra como o trabalho da sua instituição pode ficar mais inteligente.',
  chromeExecutable: process.env.CHROME_EXECUTABLE || '/usr/bin/chromium',
  dataDir: process.env.DATA_DIR || path.join(projectRoot, 'output'),
  googleClientId: process.env.GOOGLE_CLIENT_ID || '',
  googleClientSecret: process.env.GOOGLE_CLIENT_SECRET || '',
  googleRedirectUri: process.env.GOOGLE_REDIRECT_URI || '',
  youtubePrivacyStatus: (['public', 'private', 'unlisted'].includes(privacy) ? privacy : 'public') as 'public' | 'private' | 'unlisted',
  youtubeCategoryId: process.env.YOUTUBE_CATEGORY_ID || '27',
  dailyEnabled: String(process.env.DAILY_ENABLED || 'false').toLowerCase() === 'true',
  dailyHour: Number(process.env.DAILY_HOUR || 8),
  dailyMinute: Number(process.env.DAILY_MINUTE || 0),
};

export const tokenFile = path.join(config.dataDir, 'youtube-token.json');
export const stateFile = path.join(config.dataDir, 'oauth-state.json');
export const jobsDir = path.join(config.dataDir, 'jobs');
