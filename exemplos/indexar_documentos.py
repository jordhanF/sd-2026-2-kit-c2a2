"""
Carga da base de teste: manda documentos/*.txt para a ingestao e acompanha a
tarefa na fila ate ela ficar pronta.

Uso: python exemplos/indexar_documentos.py [pasta]
"""
import os
import sys
import time

import requests

URL_INGESTAO = os.getenv("URL_INGESTAO", "http://127.0.0.1:8001")


def carregar(pasta: str) -> list:
    documentos = []
    for nome in sorted(os.listdir(pasta)):
        if nome.endswith(".txt"):
            with open(os.path.join(pasta, nome), encoding="utf-8") as arquivo:
                documentos.append({"texto": arquivo.read().strip(), "origem": nome})
    return documentos


def main() -> int:
    pasta = sys.argv[1] if len(sys.argv) > 1 else "documentos"
    documentos = carregar(pasta)
    if not documentos:
        print(f"nenhum .txt em {pasta}")
        return 1

    resposta = requests.post(f"{URL_INGESTAO}/indexar", json=documentos, timeout=10)
    print(f"POST /indexar -> {resposta.status_code} {resposta.json()}")
    resposta.raise_for_status()
    identificador = resposta.json()["id"]

    # 202 significa "aceitei, ainda nao terminei": o estado vem da consulta.
    for _ in range(40):
        estado = requests.get(f"{URL_INGESTAO}/tarefa/{identificador}", timeout=10).json()
        print(f"  tarefa {identificador}: {estado['status']}")
        if estado["status"] in ("pronto", "erro"):
            return 0 if estado["status"] == "pronto" else 1
        time.sleep(0.5)
    print("tempo esgotado esperando a indexacao - o worker esta de pe?")
    return 1


if __name__ == "__main__":
    sys.exit(main())
