# Uma imagem para os quatro processos.
#
# Ingestao, worker, recuperacao e geracao compartilham a mesma base e as mesmas
# dependencias: so o COMMAND muda (ver docker-compose.yml). Quatro Dockerfiles
# identicos seriam quatro lugares para esquecer de atualizar - e quatro camadas
# de dependencia para baixar em vez de uma.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CAMINHO_DADOS=/app/dados

WORKDIR /app

# As dependencias vem antes do codigo: mexer no codigo nao invalida a camada
# do pip install.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY servicos ./servicos
COPY documentos ./documentos
COPY exemplos ./exemplos

RUN mkdir -p /app/dados

EXPOSE 8001 8002 8003

# Sobrescrito por cada servico no compose.
CMD ["uvicorn", "servicos.ingestao.app:app", "--host", "0.0.0.0", "--port", "8001"]
