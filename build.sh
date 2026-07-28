#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"

echo "==> Validando arquivos obrigatórios"
test -f requirements.txt || {
  echo "ERRO: requirements.txt não encontrado na raiz do repositório."
  exit 1
}
test -f manage.py || {
  echo "ERRO: manage.py não encontrado na raiz do repositório."
  exit 1
}

echo "==> Atualizando pip"
python -m pip install --upgrade pip

echo "==> Instalando dependências"
python -m pip install -r requirements.txt

echo "==> Verificando configuração Django"
python manage.py check

echo "==> Verificando migrações versionadas"
python manage.py makemigrations --check --dry-run

echo "==> Aplicando migrações"
python manage.py migrate --noinput

echo "==> Coletando arquivos estáticos"
python manage.py collectstatic --noinput

echo "==> Inicializando planos comerciais"
python manage.py bootstrap_plans

echo "==> Build concluído com sucesso"
