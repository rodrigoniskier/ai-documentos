# Asaas — operação comercial da RN DocumentAI

## Estado da integração

A RN DocumentAI possui:

- Checkout recorrente hospedado pelo Asaas;
- planos Pro (R$ 19,90/mês) e Ultra (R$ 49,90/mês);
- página `/assinatura/`;
- retornos de sucesso, cancelamento e expiração;
- Webhook autenticado em `/api/billing/asaas/webhook/`;
- idempotência pelo ID do evento;
- ativação automática do plano;
- concessão mensal idempotente de créditos;
- tratamento de atraso, recusa, estorno, cancelamento e expiração;
- cancelamento da recorrência pelo usuário;
- expiração automática do acesso ao fim do período pago;
- administração e auditoria no Django Admin.

## Variáveis comerciais

```text
PUBLIC_BASE_URL=https://rn-document-platform.onrender.com
ASAAS_ENABLED=false
ASAAS_API_KEY=<segredo de produção>
ASAAS_BASE_URL=https://api.asaas.com/v3
ASAAS_WEBHOOK_TOKEN=<segredo exclusivo com 32 a 255 caracteres>
ASAAS_CHECKOUT_EXPIRATION_MINUTES=60
ASAAS_HTTP_TIMEOUT=60
ASAAS_BILLING_TYPES=CREDIT_CARD
ASAAS_WEBHOOK_NAME=RN DocumentAI — Asaas Produção
ASAAS_WEBHOOK_EMAIL=rncontentlab@gmail.com
```

A API Key e o token do Webhook são segredos diferentes. Nenhum deles deve ser salvo no GitHub, em logs ou em e-mails.

## Lançamento automatizado

O workflow `06 — Lançamento comercial RN DocumentAI` no n8n:

1. valida os acessos ao Render e ao Asaas;
2. mantém `ASAAS_ENABLED=false` durante a preparação;
3. configura as variáveis comerciais;
4. remove configurações antigas de convite;
5. publica o código da branch `main`;
6. valida cadastro público, preços, assinatura e saúde;
7. cria ou atualiza o Webhook de produção;
8. ativa `ASAAS_ENABLED=true`;
9. publica o deploy comercial;
10. executa `asaas_check`;
11. realiza rollback automático quando um gate falha.

## Eventos monitorados

- `CHECKOUT_CREATED`;
- `CHECKOUT_CANCELED`;
- `CHECKOUT_EXPIRED`;
- `CHECKOUT_PAID`;
- `PAYMENT_CREATED`;
- `PAYMENT_UPDATED`;
- `PAYMENT_CONFIRMED`;
- `PAYMENT_RECEIVED`;
- `PAYMENT_OVERDUE`;
- `PAYMENT_CREDIT_CARD_CAPTURE_REFUSED`;
- `PAYMENT_REFUNDED`;
- `PAYMENT_PARTIALLY_REFUNDED`;
- `PAYMENT_DELETED`.

## Comandos operacionais

```bash
python manage.py asaas_check
python manage.py configure_asaas_webhook
python manage.py expire_billing_subscriptions
```

`configure_asaas_webhook` é idempotente: atualiza a configuração existente quando encontra o mesmo nome ou URL.

## Monitoramento e manutenção

- o workflow `07 — Monitoramento comercial RN DocumentAI` verifica a aplicação e o Webhook a cada hora;
- o workflow `08 — Manutenção diária de assinaturas RN DocumentAI` executa a expiração de assinaturas encerradas;
- alertas são enviados somente em falha ou recuperação automática;
- nenhuma automação cria cobranças, clientes, transferências, saques ou estornos.

## Segurança

- nunca registrar a API Key ou o token do Webhook;
- nunca confirmar pagamento por URL de retorno;
- considerar somente Webhooks autenticados;
- manter o endpoint HTTPS;
- rotacionar segredos após suspeita de exposição;
- manter processamento idempotente;
- não armazenar dados completos de cartão;
- manter `ASAAS_ENABLED=false` sempre que um gate comercial falhar.
