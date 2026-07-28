# RN Video Factory

Fábrica automatizada para produzir vídeos verticais de demonstração de processos inteligentes. O primeiro fluxo usa o aplicativo público de gestão de questões e executa, em uma única operação:

1. planejamento do roteiro com a OpenAI API;
2. narração em português brasileiro com `gpt-4o-mini-tts` e voz `marin`;
3. captura automática das telas com Playwright;
4. montagem vertical 1080 × 1920 com FFmpeg;
5. exportação MP4 com legendas e identidade visual;
6. publicação no canal autorizado pela YouTube Data API.

## Implantação

O projeto está preparado como subdiretório de um monorepo. No Render, use o Blueprint `rn-video-factory/render.yaml` ou crie um Web Service Docker com:

- **Root Directory:** `rn-video-factory`
- **Dockerfile:** `rn-video-factory/Dockerfile`
- **Plano recomendado:** Standard, devido ao Chromium e à renderização de vídeo
- **Disco persistente:** `/data`, 10 GB

## Configuração obrigatória

No Render, informe apenas:

- `PUBLIC_BASE_URL`: URL pública do novo serviço;
- `OPENAI_API_KEY`;
- `GOOGLE_CLIENT_ID`;
- `GOOGLE_CLIENT_SECRET`;
- `GOOGLE_REDIRECT_URI`: `https://SEU-SERVICO.onrender.com/youtube/callback`.

O `ADMIN_TOKEN` pode ser gerado automaticamente pelo Blueprint.

## Primeira publicação

1. Abra a URL do serviço.
2. Clique em **Conectar YouTube** e autorize o canal uma única vez.
3. Insira o `ADMIN_TOKEN` e clique em **Gerar e publicar agora**.

O projeto OAuth do Google precisa ter a YouTube Data API v3 ativada. Projetos de API ainda não auditados pelo Google podem ter uploads forçados para privado, mesmo quando `YOUTUBE_PRIVACY_STATUS=public`.

## Produção diária

Após a primeira publicação, altere:

```env
DAILY_ENABLED=true
DAILY_HOUR=8
DAILY_MINUTE=0
TZ=America/Recife
```

O próprio serviço agenda a próxima produção e mantém o token do YouTube no disco persistente.

## Segurança

- credenciais ficam somente nas variáveis de ambiente do Render;
- o token OAuth é armazenado em `/data/youtube-token.json` com permissão restrita;
- a rota de produção exige `ADMIN_TOKEN`;
- nenhuma questão é enviada ao sistema demonstrado; a automação apenas navega até o formulário.
