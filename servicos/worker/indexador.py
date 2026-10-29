"""
Worker de indexacao - TAREFA 4 (mensageria).

Consome a fila 'indexacao' e faz o trabalho caro FORA do caminho da requisicao:
reajusta o vocabulario TF-IDF, revetoriza o corpus inteiro e persiste.

Politica aqui, mecanismo na fila: este arquivo decide QUANTAS vezes tentar e
QUANTO esperar; servicos/comum/fila.py sabe apenas COMO devolver ou descartar.

Rodar: python -m servicos.worker.indexador
Teste de falha: SIMULAR_FALHA_EM=explode python -m servicos.worker.indexador
"""
import os
import time

from servicos.comum import ambiente  # noqa: F401  carrega o .env primeiro
from servicos.comum import log
from servicos.comum.fila import MAX_TENTATIVAS, Fila, TravaOcupada
from servicos.comum.indexador import acrescentar, reindexar
from servicos.comum.repositorio import Repositorio

logger = log.configurar("worker")

ESPERA_BASE = float(os.getenv("ESPERA_RETENTATIVA", "1"))
SIMULAR_FALHA_EM = os.getenv("SIMULAR_FALHA_EM", "")


def _conferir_gatilho_de_falha(documentos: list) -> None:
    """Gatilho de teste: permite exercitar retentativa e descarte sem quebrar nada."""
    if SIMULAR_FALHA_EM and any(SIMULAR_FALHA_EM in d["texto"] for d in documentos):
        raise RuntimeError(f"falha simulada (gatilho '{SIMULAR_FALHA_EM}')")


def processar(tarefa: dict, repositorio: Repositorio, fila: Fila) -> dict:
    """Indexa um lote. Levanta excecao se falhar - quem decide retentar e o laco."""
    documentos = tarefa["documentos"]
    _conferir_gatilho_de_falha(documentos)
    with fila.trava("indice"):
        atual = repositorio.carregar()
        corpus = acrescentar(atual.itens, documentos)
        itens, vetorizador = reindexar(corpus)
        novo = repositorio.salvar(itens, vetorizador)
    return {"versao": novo.versao, "total": novo.total}


def _tratar_falha(tarefa: dict, fila: Fila, erro: BaseException) -> None:
    """Retentativa com espera progressiva; esgotada, vai para o descarte."""
    tentativas = tarefa.get("tentativas", 0) + 1
    if tentativas >= MAX_TENTATIVAS:
        logger.error("tarefa %s descartada apos %d tentativas: %s",
                     tarefa["id"], tentativas, erro)
        tarefa["tentativas"] = tentativas
        fila.descartar(tarefa, str(erro))
        return
    espera = ESPERA_BASE * (2 ** (tentativas - 1))
    logger.warning("tarefa %s falhou (%s); %da tentativa em %.1fs",
                   tarefa["id"], erro, tentativas + 1, espera)
    time.sleep(espera)
    fila.devolver(tarefa)


def principal() -> None:
    repositorio = Repositorio()
    fila = Fila()
    logger.info("worker de indexacao de pe (dados em %s)",
                os.path.abspath(repositorio.diretorio))
    while True:
        try:
            tarefa = fila.consumir(timeout=5)
        except Exception as erro:
            logger.error("nao consegui ler a fila (%s); nova tentativa em 3s", erro)
            time.sleep(3)
            continue
        if tarefa is None:
            continue
        logger.info("tarefa %s recebida (%d documento(s), tentativa %d)",
                    tarefa["id"], len(tarefa["documentos"]), tarefa.get("tentativas", 0) + 1)
        fila.definir_status(tarefa["id"], status="processando")
        inicio = time.perf_counter()
        try:
            resultado = processar(tarefa, repositorio, fila)
        except TravaOcupada:
            # Outro worker esta reescrevendo o indice. Nao e falha da tarefa:
            # devolve para o fim da fila sem gastar tentativa.
            logger.info("indice travado por outro worker; tarefa %s devolvida", tarefa["id"])
            time.sleep(0.5)
            fila.republicar(tarefa)
        except Exception as erro:
            _tratar_falha(tarefa, fila, erro)
        else:
            duracao = time.perf_counter() - inicio
            logger.info("tarefa %s pronta em %.2fs: indice versao %s com %d documento(s)",
                        tarefa["id"], duracao, resultado["versao"], resultado["total"])
            fila.definir_status(tarefa["id"], status="pronto", duracao_s=round(duracao, 3),
                                **resultado)


if __name__ == "__main__":
    try:
        principal()
    except KeyboardInterrupt:
        logger.info("worker encerrado")
