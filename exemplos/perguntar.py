"""
Cliente do fluxo completo: pergunta e mostra a resposta com as fontes citadas.

Uso: python exemplos/perguntar.py "o que diz o teorema CAP?"
"""
import os
import sys

import requests

URL_GERACAO = os.getenv("URL_GERACAO", "http://127.0.0.1:8003")


def main() -> int:
    pergunta = " ".join(sys.argv[1:]) or "o que diz o teorema CAP?"
    resposta = requests.post(f"{URL_GERACAO}/perguntar",
                             json={"pergunta": pergunta, "top_k": 3}, timeout=60)
    corpo = resposta.json()

    print(f"HTTP {resposta.status_code}\n")
    if resposta.status_code == 503:
        # Degradacao com elegancia: sem a redacao do LLM, mas com os trechos.
        print(f"INDISPONIVEL ({corpo.get('motivo')}): {corpo.get('detail')}")
        for trecho in corpo.get("trechos", []):
            print(f"  - [{trecho['origem']}] {trecho['texto']}")
        return 1

    print(f"PERGUNTA: {corpo['pergunta']}\n")
    print(f"RESPOSTA:\n{corpo['resposta']}\n")
    print("FONTES:")
    for fonte in corpo["fontes"]:
        print(f"  - {fonte['origem']} (relevancia {fonte['score']:.4f})")
    print(f"\nindice versao {corpo['versao_indice']} | modelo {corpo['modelo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
