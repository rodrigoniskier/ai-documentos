import os

# O SDK da OpenAI lê estas variáveis automaticamente. Valores antigos ou ligados
# a outra organização provocam o erro invalid_organization mesmo com uma chave
# válida. O AjudAI Docente usa a chave do projeto sem forçar esses cabeçalhos.
os.environ.pop("OPENAI_ORG_ID", None)
os.environ.pop("OPENAI_PROJECT_ID", None)
