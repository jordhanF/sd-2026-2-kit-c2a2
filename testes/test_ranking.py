"""Busca por similaridade e reranking - TAREFA 2."""
from servicos.comum.indexador import reindexar
from servicos.comum.ranking import buscar, cobertura, normalizar

CORPUS = [
    {"texto": "O teorema CAP trata de consistencia e disponibilidade sob particao.",
     "origem": "cap"},
    {"texto": "Raft e um algoritmo de consenso com eleicao de lider e log replicado.",
     "origem": "raft"},
    {"texto": "Um sistema distribuido sofre com falha parcial: uma parte falha e o resto segue.",
     "origem": "sd"},
]


def _indexar():
    itens, vetorizador = reindexar(CORPUS)
    return itens, vetorizador


def test_busca_traz_o_documento_certo_em_primeiro():
    itens, vetorizador = _indexar()
    vetor = vetorizador.vetorizar("o que diz o teorema CAP?")
    resultados = buscar(vetor, itens, top_k=3, pergunta="o que diz o teorema CAP?")
    assert resultados[0]["origem"] == "cap"


def test_pergunta_sobre_consenso_traz_raft():
    itens, vetorizador = _indexar()
    pergunta = "como funciona a eleicao de lider no consenso?"
    resultados = buscar(vetorizador.vetorizar(pergunta), itens, top_k=1, pergunta=pergunta)
    assert [r["origem"] for r in resultados] == ["raft"]


def test_top_k_e_um_teto_nao_uma_cota():
    """top_k limita quantos voltam; nao obriga a completar com irrelevantes."""
    itens, vetorizador = _indexar()
    pergunta = "sistema distribuido, consenso e consistencia"
    vetor = vetorizador.vetorizar(pergunta)
    assert len(buscar(vetor, itens, top_k=3, pergunta=pergunta)) == 3
    assert len(buscar(vetor, itens, top_k=2, pergunta=pergunta)) == 2
    assert len(buscar(vetor, itens, top_k=1, pergunta=pergunta)) == 1

    # Pergunta que toca um documento so: top_k=3 devolve UM.
    estreita = "falha parcial"
    assert len(buscar(vetorizador.vetorizar(estreita), itens, top_k=3,
                      pergunta=estreita)) == 1


def test_resultados_vem_ordenados_por_score_final():
    itens, vetorizador = _indexar()
    pergunta = "particao de rede e consistencia"
    resultados = buscar(vetorizador.vetorizar(pergunta), itens, top_k=3, pergunta=pergunta)
    scores = [r["score_final"] for r in resultados]
    assert scores == sorted(scores, reverse=True)


def test_indice_vazio_devolve_lista_vazia():
    assert buscar([0.1, 0.2], [], top_k=3) == []


def test_cobertura_ignora_acento_e_caixa():
    # Sem dobrar o acento, "consistencia" e "consistência" seriam termos
    # diferentes e a cobertura daria zero na pergunta bem escrita.
    assert cobertura("consistência", "trata de consistencia") == 1.0
    assert normalizar("CAP, Particao!") == {"cap", "particao"}


def test_cobertura_sem_termos_uteis_nao_estoura():
    assert cobertura("de a o", "qualquer texto") == 0.0


def test_corpus_maior_que_a_janela_ainda_traz_o_melhor_documento():
    """A ordenacao previa e o que escolhe os CANDIDATOS do reranking.

    O enchimento aqui compartilha UM termo com a pergunta de proposito: assim ele
    sobrevive ao corte de relevancia zero e a unica coisa que o mantem fora dos
    candidatos e a ordenacao por cosseno. Com corpus pequeno (ou enchimento sem
    termo em comum) a falta da ordenacao passaria despercebida.
    """
    corpus = [{"texto": f"Nota {n}: a palavra consistencia aparece aqui de passagem, "
                        f"sem tratar do assunto, apenas para encher o indice.",
               "origem": f"ruido{n}"} for n in range(11)]
    corpus.append({"texto": "O teorema CAP escolhe entre consistencia e disponibilidade "
                            "diante de uma particao de rede.", "origem": "cap"})
    itens, vetorizador = reindexar(corpus)

    pergunta = "teorema CAP: consistencia ou disponibilidade na particao?"
    resultados = buscar(vetorizador.vetorizar(pergunta), itens, top_k=1, pergunta=pergunta)
    assert [r["origem"] for r in resultados] == ["cap"]


def test_trecho_sem_termo_em_comum_nao_e_citado_como_fonte():
    """Relevancia zero nao e fonte.

    Pedir top_k=3 num corpus de 3 nao pode devolver os 3 a qualquer custo: um
    trecho com cosseno zero nao embasa nada e, citado, sugere uma fundamentacao
    que nao existe.
    """
    corpus = [{"texto": "O teorema CAP escolhe entre consistencia e disponibilidade.",
               "origem": "cap"},
              {"texto": "Receita de bolo: farinha, ovos e manteiga no forno.",
               "origem": "bolo"}]
    itens, vetorizador = reindexar(corpus)
    pergunta = "o que diz o teorema CAP?"
    resultados = buscar(vetorizador.vetorizar(pergunta), itens, top_k=3, pergunta=pergunta)

    assert [r["origem"] for r in resultados] == ["cap"]
    assert all(r["score"] > 0 for r in resultados)
