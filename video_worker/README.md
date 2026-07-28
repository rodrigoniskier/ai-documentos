# RN Content Lab Video Renderer

Serviço isolado para capturar uma demonstração real e compor o vídeo final da
RN DocumentAI. O worker abre a aplicação em Chromium, prepara uma conta
exclusivamente sintética fora da gravação, registra o fluxo seguro em 1080p,
recebe a locução, acrescenta abertura, encerramento, legendas e thumbnail e
disponibiliza os artefatos para arquivamento no R2 e publicação no YouTube.

Os estados de captura, renderização e publicação são gravados atomicamente no
diretório do job. Com um Persistent Disk no Render, uma reinicialização retoma
automaticamente jobs que ainda possuem todos os insumos necessários.

## Implantação no Render

- Runtime: Docker
- Root Directory: `video_worker`
- Health Check Path: `/health`
- Persistent Disk:
  - mount path: `/var/data`
- Environment:
  - `VIDEO_RENDER_TOKEN`: segredo exclusivo, longo e aleatório;
  - `VIDEO_JOB_ROOT=/var/data/rn-video-jobs`;
  - `VIDEO_JOB_TTL_SECONDS=259200`;
  - `VIDEO_COMPLETED_JOB_TTL_SECONDS=7200`;
  - `VIDEO_STATUS_HEARTBEAT_SECONDS=15`;
  - `VIDEO_RENDER_CONCURRENCY=1`;
  - `VIDEO_MAX_SCREEN_MB=350`;
  - `VIDEO_MAX_AUDIO_MB=50`;
  - `VIDEO_CAPTURE_TARGET_URL=https://rn-document-platform.onrender.com/`;
  - `VIDEO_CAPTURE_ALLOWED_HOSTS=rn-document-platform.onrender.com`;
  - `VIDEO_CAPTURE_GENERATION_TIMEOUT_SECONDS=360`;
  - `VIDEO_CAPTURE_NORMALIZE_TIMEOUT_SECONDS=600`;
  - `VIDEO_RENDER_FFMPEG_TIMEOUT_SECONDS=600`.

O endpoint `/health` informa se o diretório está gravável, se está fora de
`/tmp`, o espaço livre e a quantidade de jobs ativos. Um status `degraded`
impede considerar o serviço pronto para uma produção definitiva.

## Captura

### `POST /capture`

Autenticação: `Authorization: Bearer <VIDEO_RENDER_TOKEN>`.

Corpo JSON:

- `job_id`: identificador idempotente da produção;
- `target_url`: opcional; precisa corresponder ao host autorizado.

A chamada retorna imediatamente. Consulte o `status_url` até `status=ready`.
O estado e o `target_url` são persistidos para permitir retomada depois de um
restart.

### Estado e download

- `GET /jobs/{job_id}/capture/status`
- `GET /jobs/{job_id}/capture`

## Renderização

### `POST /render`

Corpo `multipart/form-data`:

- `screen_video`: captura manual MP4/WebM; ou
- `capture_job_id`: job de captura automatizada pronta;
- `voiceover`: locução MP3/WAV;
- `script`: roteiro completo usado nas legendas;
- `title`: título da abertura e thumbnail;
- `subtitle`: subtítulo da abertura;
- `cta`: chamada final;
- `job_id`: identificador idempotente;
- `async_mode`: opcional, `false` por padrão.

Com `async_mode=false`, a resposta continua compatível com o workflow legado:
aguarda o job e devolve os artefatos prontos. A renderização é executada em uma
task protegida; se a conexão HTTP cair, o job continua.

Com `async_mode=true`, a chamada devolve `queued`/`processing` imediatamente.
Consulte:

- `GET /jobs/{job_id}/render/status`
- `GET /jobs/{job_id}/video`
- `GET /jobs/{job_id}/thumbnail`

O worker grava um fingerprint SHA-256 das entradas. Reutilizar o mesmo
`job_id` com locução, captura, roteiro ou metadados diferentes retorna `409`,
evitando que um vídeo antigo seja confundido com a produção atual.

## Confirmação e limpeza

Depois de arquivar MP4 e thumbnail no R2 e confirmar o vídeo público no
YouTube, registre:

`POST /jobs/{job_id}/publication`

```json
{
  "video_id": "abcdefghijk",
  "youtube_url": "https://www.youtube.com/watch?v=abcdefghijk",
  "r2_video_key": "videos/final.mp4",
  "r2_thumbnail_key": "videos/final.jpg",
  "r2_verified": true,
  "public_confirmed": true
}
```

Somente depois dessa confirmação o endpoint abaixo aceita a exclusão:

- `DELETE /jobs/{job_id}`

Jobs prontos e ainda não confirmados nunca são removidos automaticamente.
Jobs concluídos podem ser removidos após
`VIDEO_COMPLETED_JOB_TTL_SECONDS`. Jobs vazios ou definitivamente falhos usam
`VIDEO_JOB_TTL_SECONDS`.

Todos os endpoints de jobs exigem o mesmo Bearer token.
