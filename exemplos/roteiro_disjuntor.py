"""
Roteiro do checklist de entrega: ver o disjuntor abrir de verdade.

Como usar:
  1. deixe os quatro processos de pe e confirme que uma pergunta funciona;
  2. DERRUBE o servico de recuperacao (Ctrl+C no terminal dele,
     ou: docker compose stop recuperacao);
  3. rode este script.

O esperado: as 3 primeiras perguntas falham com 503 'recuperacao_indisponivel'
(cada uma paga o tempo-limite); a partir da 4a o motivo muda para
'disjuntor_recuperacao_aberto' e a resposta volta na hora, SEM tentar. E isso
que o disjuntor compra: pressa em falhar em vez de lentidao acumulada.
"""
import os
import time

import requests

URL_GERACAO = os.getenv("URL_GERACAO", "http://127.0.0.1:8003")
TENTATIVAS = 5


def estado_dos_disjuntores() -> str:
    saude = requests.get(f"{URL_GERACAO}/saude", timeout=10).json()["disjuntores"]
    return (f"recuperacao={saude['recuperacao']['estado']}"
            f"({saude['recuperacao']['falhas']} falhas) "
            f"llm={saude['llm']['estado']}({saude['llm']['falhas']} falhas)")


def main() -> None:
    print(f"antes:  {estado_dos_disjuntores()}\n")
    for tentativa in range(1, TENTATIVAS + 1):
        inicio = time.perf_counter()
        try:
            resposta = requests.post(f"{URL_GERACAO}/perguntar",
                                     json={"pergunta": "o que diz o teorema CAP?"},
                                     timeout=60)
            motivo = resposta.json().get("motivo", "-")
            codigo = resposta.status_code
        except requests.RequestException as erro:
            motivo, codigo = f"sem resposta: {erro}", "---"
        duracao = time.perf_counter() - inicio
        print(f"{tentativa}. HTTP {codigo} motivo={motivo} em {duracao:.2f}s")
        print(f"   {estado_dos_disjuntores()}")

    print("\nAgora suba a recuperacao de novo e espere a janela de 20s:")
    print("o circuito vai para 'meio', deixa passar UMA chamada de teste e fecha.")


if __name__ == "__main__":
    main()
