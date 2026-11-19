# RN DocumentAI

Plataforma comercial Django da RN Content Lab para professores do ensino superior gerarem Planos de Ensino personalizados em DOCX a partir de dados e fontes institucionais.

## Problema, público e resultado

**Problema.** Montar um Plano de Ensino exige combinar dados da instituição, do curso e da disciplina em um documento DOCX no padrão institucional, uma tarefa repetitiva a cada período.

**Para quem.** Professores do ensino superior que precisam produzir Planos de Ensino personalizados a partir de dados e fontes institucionais.

**O que entrega.** Cadastro de instituição, curso e disciplina; envio privado de fontes em PDF e DOCX; geração estruturada pela OpenAI Responses API; DOCX com download protegido; histórico de documentos; planos Gratuito, Pro e Ultra com créditos e assinatura recorrente via Asaas, ativada por webhook autenticado e idempotente.

**Tecnologias.** Python, Django, PostgreSQL, SQL, OpenAI API, Cloudflare R2, Render, Asaas, n8n, GitHub Actions.

**Qualidade e evidências.** 61 funções de teste automatizadas; dois workflows de GitHub Actions; comandos de validação (`check`, `makemigrations --check`, `test`) descritos abaixo.

## Recursos

- cadastro público por e-mail, sem código de convite;
- cinco créditos gratuitos concedidos uma única vez;
- planos Gratuito, Pro e Ultra;
- assinatura mensal recorrente via Asaas;
- ativação automática por Webhook autenticado e idempotente;
- cadastro de instituição, curso e disciplina;
- upload privado de fontes PDF e DOCX;
- geração estruturada pela OpenAI Responses API;
- criação e download protegido de DOCX;
- logomarca institucional;
- histórico de documentos;
- armazenamento privado no Cloudflare R2;
- deploy automático no Render com PostgreSQL;
- rotinas operacionais e monitoramento pelo n8n.

## Planos

- Gratuito: 5 créditos totais;
- Pro: R$ 19,90/mês e 40 créditos mensais;
- Ultra: R$ 49,90/mês e 120 créditos mensais.

## Desenvolvimento local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py bootstrap_plans
python manage.py createsuperuser
python manage.py runserver
```

## Validação

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py check
python manage.py test
```

## Produção

A configuração de produção usa:

- Render para aplicação e PostgreSQL;
- Cloudflare R2 para arquivos privados;
- OpenAI para geração;
- Asaas para cobrança recorrente;
- n8n para lançamento, monitoramento e manutenção.

O deploy exige as variáveis descritas em `.env.example` e `render.yaml`. O endpoint de saúde é `/health/`. O Webhook do Asaas é `/api/billing/asaas/webhook/`.

Nunca envie arquivos `.env`, senhas, tokens, chaves, URLs internas de banco ou credenciais para o GitHub.
