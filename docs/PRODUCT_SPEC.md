# RN DocumentAI — Especificação comercial

## Visão

Plataforma SaaS para professores do ensino superior criarem documentos acadêmicos personalizados, editáveis e rastreáveis a partir dos dados, modelos e fontes da própria instituição.

## Público-alvo

- professores do ensino superior;
- coordenadores de curso;
- pequenas e médias instituições educacionais.

## Proposta de valor

Cadastre instituição, disciplina e fontes uma vez. Gere documentos coerentes com a realidade institucional, com supervisão docente e exportação em DOCX.

## Produto disponível

Geração de Plano de Ensino em DOCX com:

- identificação institucional;
- ementa;
- objetivos;
- competências e habilidades;
- conteúdo programático;
- metodologia;
- avaliação;
- recursos;
- bibliografia;
- observações;
- código único e procedência;
- logomarca e identidade visual básica.

## Planos

### Gratuito

- R$ 0;
- 5 créditos totais, concedidos uma única vez;
- 1 instituição;
- 1 disciplina;
- 3 fontes;
- limite diário de 4 créditos;
- marca visual no documento.

### Pro

- R$ 19,90/mês;
- 40 créditos mensais;
- 2 instituições;
- 10 disciplinas;
- 30 fontes;
- limite diário de 12 créditos;
- sem marca visual.

### Ultra

- R$ 49,90/mês;
- 120 créditos mensais;
- 5 instituições;
- 30 disciplinas;
- 100 fontes;
- limite diário de 30 créditos;
- sem marca visual.

## Créditos

- Plano de Ensino: 2 créditos;
- reserva antes da geração;
- estorno automático em erro técnico;
- regeneração solicitada pelo usuário consome novos créditos;
- saldo nunca pode ficar negativo;
- lançamentos imutáveis e idempotentes.

## Cobrança

- Checkout recorrente hospedado pelo Asaas;
- planos mensais Pro e Ultra;
- ativação somente após Webhook autenticado;
- concessão mensal idempotente de créditos;
- tratamento de atraso, recusa, estorno e cancelamento;
- cancelamento pelo usuário com acesso até o fim do período pago;
- nenhum dado completo de cartão armazenado pela aplicação.

## Arquitetura

- Django;
- PostgreSQL;
- Bootstrap 5;
- OpenAI Responses API com saída estruturada;
- Cloudflare R2 para arquivos privados;
- Render para produção;
- Asaas para cobrança recorrente;
- n8n para lançamento, monitoramento, alertas e manutenção.

## Isolamento e segurança

- todo objeto de negócio pertence a um usuário;
- consultas filtradas pelo proprietário;
- downloads exigem autenticação e autorização;
- arquivos privados com URLs temporárias quando aplicável;
- validação de extensão e tamanho;
- proibição de dados pessoais ou sensíveis de alunos;
- testes nunca usam APIs financeiras reais;
- segredos somente em variáveis de ambiente;
- HTTPS, cookies seguros, HSTS e proteção CSRF em produção;
- Webhook financeiro autenticado e idempotente.

## Uploads

- PDF e DOCX para fontes;
- PNG/JPG para logomarca;
- limite inicial de 5 MB por arquivo.

## Geração por IA

- OpenAI como provedor inicial;
- chamadas somente no backend;
- `store=false` quando suportado;
- sem busca na web durante a geração;
- JSON Schema estrito;
- registro de tokens;
- revisão humana obrigatória.

## Privacidade e conformidade

- Termos de Uso e Aviso de Privacidade comerciais;
- coleta mínima;
- arquivos privados;
- exclusão e retenção mediante solicitação e obrigações aplicáveis;
- contato: rncontentlab@gmail.com;
- proibição expressa de dados pessoais ou sensíveis de alunos e pacientes.

## Implantação

- repositório privado no GitHub;
- deploy automático da branch `main` no Render;
- PostgreSQL gerenciado;
- Cloudflare R2;
- endpoint `/health/`;
- migrações e bootstrap de planos no build;
- ativação comercial orquestrada pelo n8n;
- rollback automático da cobrança quando um gate de lançamento falhar.

## Expansões futuras

- cronograma;
- plano de aula;
- avaliações;
- apostilas;
- templates DOCX avançados;
- fila e workers;
- plano institucional;
- plano parceiro ou consultor.
