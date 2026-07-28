# Próxima etapa — Cobrança e ativação automática com Asaas

## Objetivo
Permitir que o professor escolha Pro ou Ultra, conclua o pagamento em uma página hospedada pelo Asaas e tenha o plano ativado automaticamente, sem intervenção manual no Django Admin.

## Provedor escolhido
Asaas.

A primeira versão utilizará o Asaas Checkout para reduzir a exposição da plataforma a dados de pagamento. A aplicação criará o checkout no backend, redirecionará o usuário para a página hospedada e aguardará eventos autenticados de Webhook antes de alterar a assinatura local.

## Escopo inicial
- checkout mensal para Pro e Ultra;
- cartão de crédito recorrente no primeiro ciclo de homologação;
- avaliação de Pix recorrente no Sandbox antes de habilitar em produção;
- webhook autenticado pelo header `asaas-access-token`;
- ativação, renovação, atraso, cancelamento, estorno e expiração;
- concessão mensal de créditos somente após confirmação financeira;
- histórico de eventos de cobrança;
- página `/assinatura/` com plano atual e status;
- nenhuma chave de pagamento no frontend ou no GitHub.

## Preços fundadores
- Pro: R$ 19,90/mês;
- Ultra: R$ 49,90/mês.

## Ambientes
### Sandbox
- base URL: `https://api-sandbox.asaas.com/v3`;
- chave exclusiva do Sandbox;
- nenhum valor real movimentado;
- `ASAAS_ENABLED=false` até o webhook estar configurado.

### Produção
- base URL: `https://api.asaas.com/v3`;
- chave exclusiva de produção;
- ativação somente após homologação completa no Sandbox.

## Variáveis de ambiente
- `ASAAS_ENABLED`;
- `ASAAS_API_KEY`;
- `ASAAS_BASE_URL`;
- `ASAAS_WEBHOOK_TOKEN`;
- `ASAAS_CHECKOUT_EXPIRATION_MINUTES`.

A API Key é enviada no header `access_token`. O token do webhook é um segredo distinto, com no mínimo 32 caracteres, recebido no header `asaas-access-token`.

## Fluxo planejado
1. usuário escolhe Pro ou Ultra;
2. backend cria uma intenção interna de checkout com referência única;
3. backend chama `POST /v3/checkouts` com `chargeTypes=["RECURRENT"]`;
4. usuário é redirecionado para a página hospedada pelo Asaas;
5. callback devolve o usuário à página de assinatura, sem ativar o plano;
6. Webhook autenticado confirma o evento financeiro;
7. evento é registrado de forma idempotente;
8. assinatura local é ativada ou atualizada;
9. créditos mensais são concedidos uma única vez por período.

## Eventos de cobrança prioritários
- `PAYMENT_CREATED`;
- `PAYMENT_CONFIRMED`;
- `PAYMENT_RECEIVED`;
- `PAYMENT_OVERDUE`;
- `PAYMENT_CREDIT_CARD_CAPTURE_REFUSED`;
- `PAYMENT_REFUNDED`;
- `PAYMENT_DELETED`.

O Asaas trata assinaturas por meio das cobranças geradas. A correlação será feita pelos campos de assinatura, checkout e referência externa presentes nos eventos de pagamento.

## Modelos previstos
- `BillingCustomer`;
- `BillingCheckout`;
- `BillingSubscription`;
- `BillingEvent`;
- campos de período vigente e próxima renovação;
- referência externa do cliente, checkout, cobrança e assinatura.

## Regras críticas
- o Webhook é a fonte de verdade para ativação;
- callbacks do navegador nunca ativam o plano;
- cada evento externo possui chave idempotente única;
- créditos mensais não podem ser concedidos duas vezes no mesmo período;
- falhas de pagamento não apagam histórico nem documentos;
- cancelamento mantém acesso até o fim do período já pago quando aplicável;
- logs nunca armazenam número completo de cartão, CVV ou segredos;
- testes usam eventos simulados e nunca fazem cobrança real;
- o endpoint deve responder rapidamente com HTTP 2xx após validar e registrar o evento.

## Sequência de implementação
1. configurar credenciais do Sandbox;
2. criar modelos e migrações de cobrança;
3. criar cliente HTTP do Asaas no backend;
4. criar serviço de checkout recorrente;
5. criar endpoint de Webhook com validação do token;
6. implementar transições de estado da assinatura;
7. conceder créditos mensais de forma idempotente;
8. criar página de assinatura e retornos do checkout;
9. cobrir sucesso, duplicação, falha, atraso, estorno e renovação;
10. configurar o Webhook no Asaas Sandbox;
11. realizar pagamento simulado;
12. trocar para produção somente após homologação.
