"""
Servico 2 - RECUPERACAO: dada uma pergunta, acha os trechos mais relevantes.

TAREFA 2. Responsabilidade unica: COMPARAR e ORDENAR. Nao indexa, nao guarda
arquivo, nao conhece o LLM.

Dois pedidos a ingestao por pergunta:
  POST /vetorizar      -> o vetor da pergunta no espaco vetorial oficial
  GET  /indice         -> o corpus com os vetores (so quando a versao muda)

A decisao de relevancia mora em servicos/comum/ranking.py, em funcoes puras.

Rodar: uvicorn servicos.recuperacao.app:app --port 8002
"""
import os

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from servicos.comum import ambiente  # noqa: F401  carrega o .env primeiro
from servicos.comum import log
from servicos.comum.ranking import buscar as ranquear

logger = log.configurar("recuperacao")
app = FastAPI(title="Recuperacao - C2.A2", description="Busca por similaridade.")
log.registrar_requisicoes(app, logger)

URL_INGESTAO = os.getenv("URL_INGESTAO", "http://127.0.0.1:8001")
TIMEOUT = float(os.getenv("TIMEOUT_INGESTAO", "10"))

# Cache do indice, invalidado por versao. Trafegar todos os vetores a cada
# pergunta seria desperdicio: a sonda /indice/versao custa alguns bytes.
_cache = {"versao": None, "itens": []}


class Consulta(BaseModel):
    pergunta: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=20)


def _versao_remota() -> str:
    resposta = requests.get(f"{URL_INGESTAO}/indice/versao", timeout=TIMEOUT)
    resposta.raise_for_status()
    return resposta.json()["versao"]


def _obter_itens() -> tuple:
    """Devolve (versao, itens), rebaixando o indice so quando ele mudou."""
    versao = _versao_remota()
    if versao != _cache["versao"]:
        resposta = requests.get(f"{URL_INGESTAO}/indice", timeout=TIMEOUT)
        resposta.raise_for_status()
        dados = resposta.json()
        _cache["versao"], _cache["itens"] = dados["versao"], dados["itens"]
        logger.info("indice rebaixado: versao %s com %d item(ns)",
                    dados["versao"], len(dados["itens"]))
    return _cache["versao"], _cache["itens"]


def _vetorizar(pergunta: str):
    """Pede o vetor a quem e dono do espaco vetorial. 409 = indice vazio."""
    resposta = requests.post(f"{URL_INGESTAO}/vetorizar",
                             json={"texto": pergunta}, timeout=TIMEOUT)
    if resposta.status_code == 409:
        return None
    resposta.raise_for_status()
    return resposta.json()["vetor"]


@app.post("/buscar")
def buscar(consulta: Consulta):
    """Devolve os top_k trechos mais parecidos com a pergunta."""
    try:
        vetor = _vetorizar(consulta.pergunta)
        versao, itens = _obter_itens()
    except requests.RequestException as erro:
        # Falha de uma dependencia e 503, nao 500: o problema nao esta aqui.
        logger.error("ingestao indisponivel: %s", erro)
        raise HTTPException(503, detail=f"servico de ingestao indisponivel: {erro}")

    if vetor is None or not itens:
        # Indice vazio NAO e falha: e resposta vazia. Devolver 503 aqui faria o
        # disjuntor da geracao abrir por um sistema que esta saudavel e so nao
        # tem documentos ainda.
        logger.info("busca com indice vazio")
        return {"versao": versao if itens else "vazio", "resultados": [],
                "aviso": "indice vazio: nenhum documento indexado"}

    resultados = ranquear(vetor, itens, top_k=consulta.top_k, pergunta=consulta.pergunta)
    logger.info("busca '%s': %d resultado(s), melhor score %.4f",
                consulta.pergunta[:40], len(resultados),
                resultados[0]["score_final"] if resultados else 0.0)
    return {"versao": versao, "resultados": resultados}


@app.get("/saude")
def saude():
    try:
        versao, itens = _obter_itens()
        return {"status": "ok", "ingestao": "ok", "versao": versao, "itens": len(itens)}
    except requests.RequestException as erro:
        # De pe, mas degradado: diz exatamente qual dependencia esta fora.
        return {"status": "degradado", "ingestao": f"indisponivel: {erro}",
                "versao": _cache["versao"], "itens": len(_cache["itens"])}
