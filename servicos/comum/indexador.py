"""
Montagem do indice - a parte caras da indexacao, isolada do transporte.

Funcoes puras: entram listas de documentos, saem listas de documentos. Nao sabem
o que e fila, HTTP nem arquivo - por isso dao para testar sem subir nada.

POR QUE ISTO VAI PARA UMA FILA (TAREFA 4): o TF-IDF tem vocabulario GLOBAL.
Indexar um documento novo muda o vocabulario e, com ele, o espaco vetorial -
todos os vetores anteriores deixam de ser comparaveis. A unica saida correta e
revetorizar o corpus inteiro a cada lote. O custo e proporcional ao tamanho do
indice, nao ao do lote, e por isso nao cabe dentro de uma requisicao HTTP.
"""
from servicos.comum.embeddings import Vetorizador


def normalizar_documentos(documentos) -> list:
    """Aceita dicts ou objetos com .texto/.origem e devolve dicts limpos."""
    saida = []
    for documento in documentos:
        if isinstance(documento, dict):
            texto, origem = documento.get("texto", ""), documento.get("origem", "desconhecida")
        else:
            texto, origem = documento.texto, documento.origem
        texto = (texto or "").strip()
        if texto:
            saida.append({"texto": texto, "origem": origem or "desconhecida"})
    return saida


def acrescentar(existentes: list, novos: list) -> list:
    """Junta os novos documentos ao corpus, sem repetir par (origem, texto).

    Indexar duas vezes o mesmo arquivo e um acidente comum (rodar o script de
    carga de novo). Sem esta guarda o mesmo trecho apareceria duplicado em toda
    resposta, inflando a sua propria relevancia.
    """
    corpus = [{"texto": i["texto"], "origem": i["origem"]} for i in existentes]
    vistos = {(i["origem"], i["texto"]) for i in corpus}
    for documento in normalizar_documentos(novos):
        chave = (documento["origem"], documento["texto"])
        if chave not in vistos:
            vistos.add(chave)
            corpus.append(documento)
    return corpus


def reindexar(itens: list) -> tuple[list, Vetorizador]:
    """Reajusta o vocabulario e revetoriza TODO o corpus."""
    if not itens:
        raise ValueError("nao ha documentos para indexar")
    vetorizador = Vetorizador()
    vetorizador.ajustar([item["texto"] for item in itens])
    indexados = []
    for item in itens:
        indexados.append({"texto": item["texto"], "origem": item["origem"],
                          "vetor": vetorizador.vetorizar(item["texto"])})
    return indexados, vetorizador
