"""Montagem do indice: deduplicacao e revetorizacao do corpus."""
import pytest

from servicos.comum.indexador import acrescentar, normalizar_documentos, reindexar


def test_acrescentar_nao_duplica_o_mesmo_documento():
    existentes = [{"texto": "a bola e azul", "origem": "x"}]
    corpus = acrescentar(existentes, [{"texto": "a bola e azul", "origem": "x"},
                                      {"texto": "a bola e verde", "origem": "x"}])
    assert len(corpus) == 2


def test_mesmo_texto_de_origem_diferente_e_outro_documento():
    corpus = acrescentar([{"texto": "igual", "origem": "a"}],
                         [{"texto": "igual", "origem": "b"}])
    assert len(corpus) == 2


def test_documento_sem_texto_util_e_descartado():
    assert normalizar_documentos([{"texto": "   ", "origem": "x"},
                                  {"texto": "ok", "origem": "y"}]) == \
        [{"texto": "ok", "origem": "y"}]


def test_reindexar_vetoriza_todo_o_corpus_no_mesmo_espaco():
    itens, _ = reindexar([{"texto": "consenso raft", "origem": "a"},
                          {"texto": "teorema cap", "origem": "b"}])
    assert len(itens) == 2
    assert len({len(i["vetor"]) for i in itens}) == 1, "vetores em dimensoes diferentes"


def test_reindexar_sem_documentos_falha_alto():
    with pytest.raises(ValueError):
        reindexar([])
