"""
Servico 3 - GERACAO: monta o prompt com o contexto e chama o LLM.

TAREFA 3 e item 4 do edital: a chamada ao LLM protegida por DISJUNTOR,
TEMPO-LIMITE e RETENTATIVA.

Dois disjuntores, nao um:
  disjuntor_recuperacao -> protege a chamada HTTP ao servico de recuperacao
  disjuntor_llm         -> protege a chamada ao LLM (que e a dependencia lenta
                           e instavel de verdade)

Um disjuntor so no LLM nao atenderia o checklist do kit ("derrube o servico de
recuperacao: o disjuntor abre como esperado?"). Falhas diferentes precisam de
contadores diferentes: o LLM fora do ar nao deve abrir o circuito da recuperacao.

Rodar: uvicorn servicos.geracao.app:app --port 8003
"""
import os

import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from servicos.comum import ambiente  # noqa: F401  carrega o .env primeiro
from servicos.comum import log
from servicos.comum.circuit_breaker import CircuitBreaker, CircuitoAberto
from servicos.comum.llm import API_KEY, MODELO, gerar
from servicos.comum.retentativa import com_retentativa

logger = log.configurar("geracao")
app = FastAPI(title="Geracao - C2.A2", description="RAG: contexto + LLM.")
log.registrar_requisicoes(app, logger)

URL_RECUPERACAO = os.getenv("URL_RECUPERACAO", "http://127.0.0.1:8002")
TIMEOUT = float(os.getenv("TIMEOUT_RECUPERACAO", "10"))
TENTATIVAS_LLM = int(os.getenv("TENTATIVAS_LLM", "3"))

disjuntor_recuperacao = CircuitBreaker(limite_falhas=3, espera_segundos=20)
disjuntor_llm = CircuitBreaker(limite_falhas=3, espera_segundos=20)


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=20)


def _buscar_contexto(pergunta: str, top_k: int) -> dict:
    resposta = requests.post(f"{URL_RECUPERACAO}/buscar",
                             json={"pergunta": pergunta, "top_k": top_k},
                             timeout=TIMEOUT)
    resposta.raise_for_status()
    return resposta.json()


def _fontes(resultados: list) -> list:
    """Extensao opcional: citar quais documentos embasaram a resposta.

    Um mesmo documento pode render dois trechos; aqui fica o melhor score de cada
    origem, para a citacao nao repetir a mesma fonte.
    """
    melhores = {}
    for item in resultados:
        origem = item["origem"]
        if origem not in melhores or item["score_final"] > melhores[origem]["score"]:
            melhores[origem] = {"origem": origem,
                                "score": item["score_final"],
                                "similaridade": item["score"]}
    return sorted(melhores.values(), key=lambda f: f["score"], reverse=True)


def _indisponivel(motivo: str, detalhe: str, resultados: list | None = None):
    """503 que DEGRADA com elegancia em vez de apenas quebrar.

    O edital pede que o sistema degrade com elegancia quando o LLM falhar. O
    status continua 503 (o servico nao entregou o que promete), mas o corpo leva
    os trechos recuperados e as fontes: o cliente fica sem a redacao do LLM, nao
    sem informacao.
    """
    corpo = {"detail": detalhe, "motivo": motivo, "degradado": True}
    if resultados:
        corpo["trechos"] = [{"texto": r["texto"], "origem": r["origem"]} for r in resultados]
        corpo["fontes"] = _fontes(resultados)
    return JSONResponse(status_code=503, content=corpo)


@app.post("/perguntar")
def perguntar(p: Pergunta):
    """Fluxo completo (TAREFA 5): pergunta entra, resposta fundamentada sai."""
    try:
        dados = disjuntor_recuperacao.chamar(_buscar_contexto, p.pergunta, p.top_k)
    except CircuitoAberto:
        logger.warning("disjuntor da recuperacao ABERTO: recusando na hora")
        return _indisponivel("disjuntor_recuperacao_aberto",
                             "contexto indisponivel: disjuntor da recuperacao esta aberto, "
                             "a chamada foi recusada sem tentar")
    except requests.RequestException as erro:
        logger.error("falha ao consultar a recuperacao: %s", erro)
        return _indisponivel("recuperacao_indisponivel",
                             f"falha ao consultar o servico de recuperacao: {erro}")

    resultados = dados.get("resultados", [])
    contexto = [item["texto"] for item in resultados]

    if not contexto:
        # Sem documentos nao ha o que fundamentar - e nao se chama o LLM para
        # inventar. Isto e resposta valida (200), nao falha.
        return {"pergunta": p.pergunta, "resposta":
                "Nao encontrei nada nos documentos indexados para fundamentar uma resposta.",
                "fontes": [], "contexto": [], "versao_indice": dados.get("versao"),
                "modelo": MODELO}

    try:
        # Retentativa POR DENTRO do disjuntor: uma sequencia esgotada conta como
        # UMA falha. Se cada tentativa contasse, o circuito abriria no primeiro
        # soluco de rede.
        resposta = disjuntor_llm.chamar(com_retentativa, gerar, p.pergunta, contexto,
                                        tentativas=TENTATIVAS_LLM)
    except CircuitoAberto:
        logger.warning("disjuntor do LLM ABERTO: recusando na hora")
        return _indisponivel("disjuntor_llm_aberto",
                             "gerador indisponivel: disjuntor do LLM esta aberto, "
                             "a chamada foi recusada sem tentar", resultados)
    except Exception as erro:
        logger.error("falha ao gerar a resposta: %s", erro)
        return _indisponivel("llm_indisponivel",
                             f"falha ao gerar a resposta: {erro}", resultados)

    return {"pergunta": p.pergunta, "resposta": resposta,
            "fontes": _fontes(resultados), "contexto": contexto,
            "versao_indice": dados.get("versao"), "modelo": MODELO}


@app.get("/saude")
def saude():
    return {"status": "ok",
            "disjuntores": {
                "recuperacao": {"estado": disjuntor_recuperacao.estado,
                                "falhas": disjuntor_recuperacao.falhas},
                "llm": {"estado": disjuntor_llm.estado,
                        "falhas": disjuntor_llm.falhas}},
            "modelo": MODELO,
            "modo_simulado": not bool(API_KEY)}
