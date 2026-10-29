"""
Verificacao de ponta a ponta - TAREFA 5.

Confere a saude dos tres servicos, indexa a base de teste, faz tres perguntas e
exige resposta fundamentada em cada uma. Sai com codigo != 0 se algo quebrar,
para servir de teste de fumaca depois de um 'docker compose up'.

Uso: python exemplos/fluxo_completo.py
"""
import os
import subprocess
import sys
import time

import requests

URLS = {
    "ingestao": os.getenv("URL_INGESTAO", "http://localhost:8001"),
    "recuperacao": os.getenv("URL_RECUPERACAO", "http://localhost:8002"),
    "geracao": os.getenv("URL_GERACAO", "http://localhost:8003"),
}

PERGUNTAS = [
    ("o que diz o teorema CAP?", "teorema_cap.txt"),
    ("como o Raft confirma uma operacao?", "consenso_raft.txt"),
    ("qual o principal desafio de um sistema distribuido?", "sistemas_distribuidos.txt"),
]


def esperar_saude(tentativas: int = 30) -> None:
    for nome, url in URLS.items():
        for tentativa in range(tentativas):
            try:
                resposta = requests.get(f"{url}/saude", timeout=5)
                resposta.raise_for_status()
                print(f"[ok] {nome:12} {resposta.json()}")
                break
            except requests.RequestException as erro:
                if tentativa == tentativas - 1:
                    raise SystemExit(f"[falhou] {nome} nao respondeu: {erro}")
                time.sleep(1)


def main() -> int:
    print("1. saude dos servicos")
    esperar_saude()

    print("\n2. indexacao pela fila")
    carga = subprocess.run([sys.executable, "exemplos/indexar_documentos.py"], check=False)
    if carga.returncode != 0:
        return carga.returncode

    print("\n3. perguntas")
    falhas = 0
    for pergunta, fonte_esperada in PERGUNTAS:
        resposta = requests.post(f"{URLS['geracao']}/perguntar",
                                 json={"pergunta": pergunta}, timeout=60)
        if resposta.status_code != 200:
            print(f"[falhou] {pergunta} -> HTTP {resposta.status_code} {resposta.text[:120]}")
            falhas += 1
            continue
        corpo = resposta.json()
        fontes = [f["origem"] for f in corpo["fontes"]]
        certo = fontes and fontes[0] == fonte_esperada
        print(f"[{'ok' if certo else 'ATENCAO'}] {pergunta}")
        print(f"     fontes: {fontes}")
        print(f"     resposta: {corpo['resposta'][:140].replace(chr(10), ' ')}...")
        if not certo:
            falhas += 1

    print(f"\n{'FLUXO COMPLETO OK' if not falhas else f'{falhas} verificacao(oes) falharam'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
