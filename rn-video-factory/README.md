# RN Video Factory

Fábrica automatizada para produzir vídeos verticais de demonstração de processos inteligentes. O primeiro fluxo usa o aplicativo público de gestão de questões e executa, em uma única operação:

1. planejamento do roteiro com a OpenAI API;
2. narração em português brasileiro com `gpt-4o-mini-tts` e voz `marin`;
3. captura automática das telas com Playwright;
4. montagem vertical 1080 × 1920 com FFmpeg;
5. geração de miniatura horizontal;
6. criação de título, descrição, hashtags e tags;
7. disponibilização de todos os arquivos em um painel protegido;
8. abertura direta do YouTube Studio para publicação manual assistida.

Não utiliza Google Cloud, OAuth nem YouTube Data API.

## Implantação

O projeto está preparado como subdiretório de um monorepo. No Render, use o Blueprint `rn-video-factory/render.yaml` ou crie um Web Service Docker com:

- **Root Directory:** `rn-video-factory`
- **Dockerfile:** `./Dockerfile`
- **Plano recomendado:** Standard, devido ao Chromium e à renderização de vídeo
- **Disco persistente:** `/data`, 10 GB

## Configuração obrigatória

No Render, a única credencial externa obrigatória é:

- `OPENAI_API_KEY`

O `ADMIN_TOKEN` é gerado automaticamente pelo Blueprint e protege o painel, as rotas de geração e os downloads.

## Uso do painel

1. Abra a URL do serviço.
2. Copie o `ADMIN_TOKEN` no painel Environment do Render.
3. Cole o token na tela do RN Video Factory e clique em **Acessar painel**.
4. Aguarde a produção diária ou clique em **Gerar novo vídeo agora**.
5. Baixe:
   - vídeo MP4;
   - miniatura JPG;
   - texto completo de publicação.
6. Use os botões de cópia para título, descrição e tags.
7. Clique em **Abrir YouTube Studio** e publique no canal `AI LAB Rodrigo Niskier`.

## Produção diária

A rotina fica ativada por padrão para 08h00 no fuso `America/Recife`:

```env
MANUAL_ASSISTED_DAILY_ENABLED=true
DAILY_HOUR=8
DAILY_MINUTE=0
TZ=America/Recife
```

A produção permanece no disco persistente. Por padrão, os 30 pacotes mais recentes são mantidos e os mais antigos são removidos automaticamente.

## Segurança

- credenciais ficam somente nas variáveis de ambiente do Render;
- o painel administrativo e todos os downloads exigem `ADMIN_TOKEN`;
- os arquivos permanecem no disco persistente privado do serviço;
- nenhuma questão é enviada ao sistema demonstrado; a automação apenas navega até o formulário;
- não existe acesso ao canal do YouTube nem armazenamento de credenciais do Google.
