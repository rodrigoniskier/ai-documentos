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
- **Dockerfile:** `./Dockerfile`
- **Plano recomendado:** Standard, devido ao Chromium e à renderização de vídeo
- **Disco persistente:** `/data`, 10 GB

## Configuração inicial

No fluxo de criação pelo Blueprint, informe somente:

- `OPENAI_API_KEY`.

O `ADMIN_TOKEN` é gerado automaticamente. A URL pública e o endereço de retorno do YouTube são derivados automaticamente do hostname fornecido pelo Render.

Depois que o serviço estiver no ar, adicione em **Environment**:

- `GOOGLE_CLIENT_ID`;
- `GOOGLE_CLIENT_SECRET`.

O endereço autorizado no Google será:

```text
https://SEU-SERVICO.onrender.com/youtube/callback
```

`PUBLIC_BASE_URL` e `GOOGLE_REDIRECT_URI` continuam aceitas como sobrescritas opcionais, mas não são necessárias no deploy padrão do Render.

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
