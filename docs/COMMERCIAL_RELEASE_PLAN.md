# RN DocumentAI — publicação comercial

## Critérios de publicação

- cadastro público sem código de convite;
- ausência de linguagem beta, fundador ou acesso restrito nas páginas públicas;
- planos Gratuito, Pro e Ultra disponíveis;
- preços de R$ 19,90/mês e R$ 49,90/mês;
- checkout recorrente via Asaas em produção;
- Webhook autenticado e idempotente;
- Termos de Uso e Aviso de Privacidade comerciais;
- armazenamento privado em Cloudflare R2;
- aplicação e banco de dados no Render;
- monitoramento e manutenção operacional executados pelo n8n.

## Gate operacional

O lançamento comercial somente deve ser ativado quando:

1. o deploy da branch `main` estiver `live`;
2. `/health/` responder `{"status":"ok"}`;
3. `/cadastro/` estiver público e sem convite;
4. `/precos/` exibir Pro e Ultra com os valores corretos;
5. `/assinatura/` existir e exigir autenticação;
6. o Webhook do Asaas estiver ativo e não interrompido;
7. `ASAAS_ENABLED=true` estiver aplicado no Render;
8. o comando `python manage.py asaas_check` concluir com sucesso.

## Operação

O n8n é responsável por configurar as variáveis comerciais, remover configurações antigas de convite, criar ou atualizar o Webhook, disparar deploys, executar os gates, ativar a cobrança e realizar rollback automático quando necessário.

Nenhuma automação operacional deve criar cobranças artificiais, clientes fictícios, estornos, transferências ou saques.
