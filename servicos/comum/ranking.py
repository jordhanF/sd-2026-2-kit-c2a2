"""
Busca por similaridade e reordenacao - TAREFA 2 (parte pura).

O servico de recuperacao cuida do transporte (buscar o indice, pedir o vetor da
pergunta). Toda a decisao de RELEVANCIA mora aqui, em funcoes puras que se testam
sem subir servidor nenhum.
"""
import unicodedata

from servicos.comum.embeddings import similaridade

PESO_COBERTURA = 0.3

# Cosseno zero significa que o trecho nao compartilha NENHUM termo com a
# pergunta. Trecho assim nao embasa resposta: entra no prompt como ruido e
# aparece na citacao de fontes com relevancia 0,0000, o que e pior que nao
# aparecer - sugere fundamentacao que nao existe.
SCORE_MINIMO = 0.0


def normalizar(texto: str) -> set:
    """Palavras em minuscula e sem acento.

    Sem a remocao de acento, "consistencia" e "consistência" seriam termos
    diferentes e a cobertura daria zero justamente nas perguntas bem escritas.
    """
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return {palavra for palavra in
            "".join(c if c.isalnum() else " " for c in sem_acento).split()
            if len(palavra) > 2}


def cobertura(pergunta: str, texto: str) -> float:
    """Fracao dos termos da pergunta que aparecem no trecho (0 a 1)."""
    termos = normalizar(pergunta)
    if not termos:
        return 0.0
    return len(termos & normalizar(texto)) / len(termos)


def buscar(vetor_pergunta: list, itens: list, top_k: int = 3,
           pergunta: str = "", janela: int = 2) -> list:
    """Compara a pergunta com cada item e devolve os top_k mais parecidos.

    Duas etapas, de proposito:
      1. cosseno contra TODO o indice -> top_k * janela candidatos,
         descartando quem nao tem termo nenhum em comum com a pergunta
      2. reordenacao dos candidatos pela cobertura dos termos da pergunta

    O cosseno sozinho premia trechos curtos que repetem um termo raro; a cobertura
    desempata a favor de quem responde mais da pergunta. Reordenar apenas a janela
    (e nao o indice todo) mantem o custo do passo 2 constante.
    """
    if top_k < 1 or not itens:
        return []
    pontuados = []
    for item in itens:
        pontuados.append({
            "texto": item["texto"],
            "origem": item["origem"],
            "score": round(similaridade(vetor_pergunta, item["vetor"]), 6),
        })
    pontuados.sort(key=lambda r: r["score"], reverse=True)
    relevantes = [p for p in pontuados if p["score"] > SCORE_MINIMO]
    candidatos = relevantes[:max(top_k * janela, top_k)]
    return reordenar(pergunta, candidatos)[:top_k]


def reordenar(pergunta: str, candidatos: list) -> list:
    """Reranking (extensao opcional): cosseno + cobertura dos termos."""
    for candidato in candidatos:
        candidato["cobertura"] = round(cobertura(pergunta, candidato["texto"]), 4)
        candidato["score_final"] = round(
            (1 - PESO_COBERTURA) * candidato["score"]
            + PESO_COBERTURA * candidato["cobertura"], 6)
    return sorted(candidatos, key=lambda r: (r["score_final"], r["score"]), reverse=True)
