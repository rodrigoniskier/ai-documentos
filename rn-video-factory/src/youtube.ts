import fsSync from 'node:fs';
import fs from 'node:fs/promises';

import {google} from 'googleapis';

import {config, tokenFile} from './config.js';
import type {VideoPlan} from './types.js';

export function oauthClient() {
  if (!config.googleClientId || !config.googleClientSecret) throw new Error('Credenciais OAuth do Google não configuradas.');
  const redirectUri = config.googleRedirectUri || `${config.publicBaseUrl}/youtube/callback`;
  return new google.auth.OAuth2(config.googleClientId, config.googleClientSecret, redirectUri);
}

export async function loadYoutubeToken(): Promise<Record<string, unknown> | null> {
  try {
    return JSON.parse(await fs.readFile(tokenFile, 'utf8')) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function saveYoutubeToken(token: Record<string, unknown>): Promise<void> {
  await fs.writeFile(tokenFile, JSON.stringify(token, null, 2), {mode: 0o600});
}

export async function uploadToYoutube(videoPath: string, plan: VideoPlan): Promise<{id: string; url: string}> {
  const token = await loadYoutubeToken();
  if (!token) throw new Error('YouTube ainda não foi conectado.');
  const auth = oauthClient();
  auth.setCredentials(token);
  auth.on('tokens', async (tokens) => saveYoutubeToken({...token, ...tokens}));

  const youtube = google.youtube({version: 'v3', auth});
  const response = await youtube.videos.insert({
    part: ['snippet', 'status'],
    requestBody: {
      snippet: {
        title: plan.title,
        description: plan.description,
        tags: plan.tags,
        categoryId: config.youtubeCategoryId,
        defaultLanguage: 'pt-BR',
      },
      status: {
        privacyStatus: config.youtubePrivacyStatus,
        selfDeclaredMadeForKids: false,
      },
    },
    media: {body: fsSync.createReadStream(videoPath)},
  });
  const id = response.data.id;
  if (!id) throw new Error('O YouTube não retornou o identificador do vídeo.');
  return {id, url: `https://youtu.be/${id}`};
}
