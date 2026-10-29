"""
Avaliacao automatica da resposta - extensao opcional do edital.

Criterio simples e explicavel, sem segundo modelo no caminho: medir o quanto a
resposta esta ANCORADA no contexto recuperado.

  fundamentacao          -> fracao dos termos da resposta que aparecem no contexto.
                            Baixa = o gerador falou de coisas que ninguem recuperou,
                            que e o sintoma classico de alucinacao em RAG.
  cobertura_da_pergunta  -> fracao dos termos da pergunta que o contexto cobre.
                            Baixa = o problema esta na RECUPERACAO, nao no gerador:
                            nao adianta culpar o LLM por material que nao chegou.

Separar as duas e o ponto. Uma resposta ruim tem causas diferentes, e cada numero
aponta para um servico diferente do sistema.

HONESTIDADE SOBRE O QUE ISTO MEDE: e sobreposicao de palavras, nao compreensao.
Resposta que contradiz o contexto usando as mesmas palavras passa batido. Flexao
tambem nao e tratada: "escolher" no contexto e "escolhe" na resposta contam como
termos diferentes, entao uma resposta boa e parafraseada fica em torno de 0,85 em
vez de 1,00 - e por isso o limite de "fundamentada" e 0,5, e nao algo perto de 1. E no
MODO SIMULADO a fundamentacao e alta por construcao - a resposta e montada a
partir do proprio contexto. O numero so comeca a dizer algo quando ha um LLM de
verdade escrevendo. E alarme de fumaca barato, nao juiz.
"""
from servicos.comum.ranking import normalizar

LIMITE_FUNDAMENTACAO = 0.5
LIMITE_COBERTURA = 0.4


def _fracao(parte: set, total: set) -> float:
    if not total:
        return 0.0
    return round(len(parte & total) / len(total), 4)


def avaliar(pergunta: str, resposta: str, contexto: list) -> dict:
    """Devolve as duas medidas e um veredito legivel."""
    termos_contexto = normalizar(" ".join(contexto))
    termos_resposta = normalizar(resposta)
    termos_pergunta = normalizar(pergunta)

    fundamentacao = _fracao(termos_contexto, termos_resposta)
    cobertura = _fracao(termos_contexto, termos_pergunta)

    if not termos_contexto:
        veredito = "sem contexto"
    elif cobertura < LIMITE_COBERTURA:
        # A recuperacao nao trouxe material sobre o que foi perguntado: a culpa
        # nao e do gerador.
        veredito = "contexto fraco para a pergunta"
    elif fundamentacao < LIMITE_FUNDAMENTACAO:
        veredito = "pouco respaldo no contexto"
    else:
        veredito = "fundamentada"

    return {"fundamentacao": fundamentacao,
            "cobertura_da_pergunta": cobertura,
            "veredito": veredito,
            "termos_da_resposta": len(termos_resposta)}
