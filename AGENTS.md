# RN Document Platform — Regras de engenharia

## Arquitetura definitiva
- Django como framework web principal.
- PostgreSQL como banco de dados de produção.
- Bootstrap 5 como camada visual padrão.
- OpenAI API usada somente no servidor.
- Cloudflare R2 para arquivos privados.
- Render como hospedagem de produção.
- n8n apenas para automações operacionais, nunca para regras centrais do produto.

## Segurança
- Nunca versionar segredos, chaves ou credenciais.
- Usar variáveis de ambiente para toda configuração sensível.
- Aplicar autorização por objeto e isolamento rigoroso entre usuários.
- Retornar 404 quando um usuário tentar acessar objeto de terceiro.
- Manter uploads e documentos gerados privados.
- Validar extensão, MIME e tamanho dos arquivos.
- Nunca chamar a OpenAI real em testes automatizados.

## Django
- Criar Custom User antes da primeira migração.
- Regras de negócio devem ficar em serviços, modelos e formulários, não apenas no frontend.
- Créditos devem usar transações de banco e select_for_update quando houver concorrência.
- Toda mudança de modelo deve incluir migração.

## Qualidade
- pytest e pytest-django para testes.
- Ruff para lint e formatação.
- Cada funcionalidade deve cobrir caminho principal, permissões e falhas relevantes.
- Mensagens ao usuário em português brasileiro.
- Código claro, modular e com type hints quando úteis.

## Escopo da primeira beta comercial
- cadastro e autenticação;
- cinco créditos gratuitos concedidos uma única vez;
- cadastro de instituição, curso e disciplina;
- upload seguro de fontes;
- geração assistida de Plano de Ensino;
- exportação DOCX;
- download protegido;
- histórico de uso;
- apresentação dos planos Gratuito, Pro e Premium;
- captação de interessados nos planos pagos.
