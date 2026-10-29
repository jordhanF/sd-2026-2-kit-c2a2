"""
Log padronizado dos quatro processos.

Um formato so para ingestao, worker, recuperacao e geracao: ler os quatro
terminais lado a lado fica possivel. O id de correlacao (X-Request-Id)
atravessa os servicos e permite seguir UMA pergunta do /perguntar ate o
/vetorizar da ingestao.
"""
import logging
import os
import sys
import uuid

CABECALHO_CORRELACAO = "X-Request-Id"


def configurar(nome: str) -> logging.Logger:
    """Devolve um logger com formato unico. Idempotente."""
    logger = logging.getLogger(nome)
    if logger.handlers:
        return logger
    saida = logging.StreamHandler(sys.stdout)
    saida.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(saida)
    logger.setLevel(os.getenv("LOG_NIVEL", "INFO").upper())
    logger.propagate = False
    return logger


def registrar_requisicoes(app, logger: logging.Logger) -> None:
    """Loga cada requisicao e propaga o id de correlacao na resposta."""

    @app.middleware("http")
    async def _middleware(request, proximo):
        correlacao = request.headers.get(CABECALHO_CORRELACAO) or uuid.uuid4().hex[:8]
        resposta = await proximo(request)
        resposta.headers[CABECALHO_CORRELACAO] = correlacao
        logger.info("%s %s -> %s (req=%s)", request.method, request.url.path,
                    resposta.status_code, correlacao)
        return resposta
