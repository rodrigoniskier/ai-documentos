# RN Video Factory

Fábrica automatizada para produzir vídeos profissionais de demonstração de processos inteligentes. O fluxo atual usa o aplicativo público de gestão de questões e executa, em uma única operação:

1. roteiro cinematográfico de aproximadamente dois minutos pela OpenAI API;
2. locução em português brasileiro com `gpt-4o-mini-tts`;
3. geração e reutilização de cenas humanas ilustrativas com `gpt-image-1-mini`;
4. gravação real da aplicação com Playwright, cursor destacado e preenchimento demonstrativo sem envio;
5. composição horizontal 1920 × 1080 com introdução, tela dividida, demonstração, contraste final e CTA;
6. trilha musical original gerada localmente, sem dependência de catálogo externo;
7. legendas, transições, identidade visual e mixagem automática com redução da música durante a voz;
8. geração de miniatura, título, descrição, hashtags e tags;
9. disponibilização de todos os arquivos em painel protegido;
10. abertura direta do YouTube Studio para publicação manual assistida.

Não utiliza Google Cloud, OAuth nem YouTube Data API.

## Integridade da demonstração

A aplicação exibida padroniza a submissão e a gestão de questões. Ela não é apresentada como geradora automática de questões ou provas. A apresentadora é identificada no vídeo como virtual e as cenas humanas são informadas como ilustrativas. A navegação e o preenchimento da aplicação são reais, mas nenhuma questão é enviada.

## Implantação

O projeto está preparado como subdiretório de um monorepo. No Render, use o Blueprint `rn-video-factory/render.yaml` ou crie um Web Service Docker com:

- **Root Directory:** `rn-video-factory`
- **Dockerfile:** `./Dockerfile`
- **Plano recomendado:** Standard, devido ao Chromium, geração visual e renderização de vídeo
- **Disco persistente:** `/data`, 10 GB

## Configuração obrigatória

No Render, a única credencial externa obrigatória é:

- `OPENAI_API_KEY`

O `ADMIN_TOKEN` é gerado automaticamente pelo Blueprint e protege o painel, as rotas de geração e os downloads.

As imagens cinematográficas são geradas apenas quando o pacote visual ainda não existe e ficam reutilizadas no disco persistente, reduzindo custo e mantendo consistência visual.

## Uso do painel

1. Abra a URL do serviço.
2. Copie o `ADMIN_TOKEN` no painel Environment do Render.
3. Cole o token na tela do RN Video Factory e clique em **Acessar painel**.
4. Aguarde a produção diária ou clique em **Gerar novo vídeo agora**.
5. Baixe o vídeo MP4, a miniatura JPG e o texto completo de publicação.
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
- nenhuma questão é enviada ao sistema demonstrado;
- não existe acesso ao canal do YouTube nem armazenamento de credenciais do Google.
