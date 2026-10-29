"""
Servico 1 - INGESTAO: recebe documentos, publica na fila e serve o indice.

Responsabilidade unica: ser o DONO do indice e do espaco vetorial. Quem aceita o
documento nao e quem o indexa - o POST devolve 202 e um worker faz o trabalho
caro (ver servicos/worker/indexador.py).

Rodar: uvicorn servicos.ingestao.app:app --port 8001
"""
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from servicos.comum import ambiente  # noqa: F401  carrega o .env primeiro
from servicos.comum import log
from servicos.comum.fila import Fila
from servicos.comum.indexador import normalizar_documentos
from servicos.comum.repositorio import Repositorio

logger = log.configurar("ingestao")
app = FastAPI(title="Ingestao - C2.A2",
              description="Dono do indice e do espaco vetorial.")
log.registrar_requisicoes(app, logger)

repositorio = Repositorio()
fila = Fila()


class Documento(BaseModel):
    texto: str
    origem: str = "desconhecida"


class Texto(BaseModel):
    texto: str = Field(min_length=1)


@app.post("/indexar", status_code=202)
def indexar(docs: list[Documento]):
    """Aceita o lote, publica na fila e devolve um comprovante (202).

    202 Accepted, nao 200: "aceitei, ainda nao terminei". E o que permite ao
    cliente nao ficar preso esperando a revetorizacao do corpus inteiro.
    """
    documentos = normalizar_documentos(docs)
    if not documentos:
        raise HTTPException(400, detail="nenhum documento com texto util no lote")
    try:
        identificador = fila.publicar(documentos)
    except Exception as erro:
        logger.error("fila indisponivel: %s", erro)
        raise HTTPException(503, detail=f"fila de indexacao indisponivel: {erro}")
    logger.info("tarefa %s publicada com %d documento(s)", identificador, len(documentos))
    return {"id": identificador, "status": "na_fila", "documentos": len(documentos),
            "consulte": f"/tarefa/{identificador}"}


@app.get("/tarefa/{identificador}")
def tarefa(identificador: str):
    """Estados: na_fila -> processando -> pronto, ou retentando -> erro."""
    try:
        estado = fila.obter_status(identificador)
    except Exception as erro:
        raise HTTPException(503, detail=f"fila de indexacao indisponivel: {erro}")
    if estado is None:
        raise HTTPException(404, detail="tarefa desconhecida ou expirada")
    return estado


@app.get("/indice")
def indice():
    """Consumido pelo servico de recuperacao."""
    atual = repositorio.recarregar_se_mudou()
    return {"versao": atual.versao, "total": atual.total,
            "atualizado_em": atual.atualizado_em, "itens": atual.itens}


@app.get("/indice/versao")
def versao_indice():
    """Sonda barata: a recuperacao so rebaixa o indice quando a versao muda."""
    atual = repositorio.recarregar_se_mudou()
    return {"versao": atual.versao, "total": atual.total}


@app.post("/vetorizar")
def vetorizar(entrada: Texto):
    """Devolve o vetor do texto no espaco vetorial OFICIAL.

    A recuperacao poderia reconstruir o vetorizador localmente, mas ai existiriam
    duas copias do vocabulario - duas fontes de verdade. No dia em que
    divergissem, a comparacao daria errado SEM erro nenhum. Quem e dono do
    espaco vetorial vetoriza.
    """
    atual = repositorio.recarregar_se_mudou()
    if atual.vazio or atual.vetorizador is None:
        raise HTTPException(409, detail="indice vazio: indexe documentos antes de perguntar")
    return {"vetor": atual.vetorizador.vetorizar(entrada.texto), "versao": atual.versao}


@app.get("/saude")
def saude():
    atual = repositorio.recarregar_se_mudou()
    try:
        filas = fila.tamanhos()
    except Exception:
        filas = None
    return {"status": "ok", "documentos": atual.total, "versao": atual.versao,
            "atualizado_em": atual.atualizado_em,
            "fila": filas, "redis": filas is not None,
            "dados": os.path.abspath(repositorio.diretorio)}
