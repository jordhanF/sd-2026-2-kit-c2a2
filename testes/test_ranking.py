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


def test_top_k_limita_a_quantidade():
    itens, vetorizador = _indexar()
    vetor = vetorizador.vetorizar("sistema distribuido")
    assert len(buscar(vetor, itens, top_k=2, pergunta="sistema distribuido")) == 2
    assert len(buscar(vetor, itens, top_k=1, pergunta="sistema distribuido")) == 1


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

    Com corpus pequeno a janela cobre tudo e a falta da ordenacao passa
    despercebida. Com 12 documentos e top_k=1 (janela de 2), pular a ordenacao
    por cosseno faz o documento certo nem chegar a ser avaliado.
    """
    corpus = [{"texto": f"documento de enchimento numero {n} sobre assunto generico",
               "origem": f"ruido{n}"} for n in range(11)]
    corpus.append({"texto": "O teorema CAP escolhe entre consistencia e disponibilidade.",
                   "origem": "cap"})
    itens, vetorizador = reindexar(corpus)

    pergunta = "teorema CAP, consistencia ou disponibilidade?"
    resultados = buscar(vetorizador.vetorizar(pergunta), itens, top_k=1, pergunta=pergunta)
    assert [r["origem"] for r in resultados] == ["cap"]
