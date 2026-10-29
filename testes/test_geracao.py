"""Disjuntores do servico de geracao - TAREFA 3 e item 4 do edital."""
import pytest
import requests
from fastapi.testclient import TestClient

from servicos.comum.circuit_breaker import CircuitBreaker
from servicos.geracao import app as geracao


def _estourar_tempo(*_args, **_kwargs):
    raise requests.Timeout("o LLM nao respondeu no tempo-limite")


@pytest.fixture
def cliente(monkeypatch):
    """Cada teste comeca com disjuntores limpos."""
    monkeypatch.setattr(geracao, "disjuntor_recuperacao",
                        CircuitBreaker(limite_falhas=3, espera_segundos=20))
    monkeypatch.setattr(geracao, "disjuntor_llm",
                        CircuitBreaker(limite_falhas=3, espera_segundos=20))
    return TestClient(geracao.app, raise_server_exceptions=False)


CONTEXTO = {"versao": "abc123", "resultados": [
    {"texto": "O teorema CAP trata de consistencia e disponibilidade.",
     "origem": "teorema_cap.txt", "score": 0.8, "score_final": 0.82, "cobertura": 0.9},
    {"texto": "Raft exige maioria para confirmar uma operacao.",
     "origem": "consenso_raft.txt", "score": 0.4, "score_final": 0.41, "cobertura": 0.3},
]}


def test_fluxo_completo_responde_com_fontes(cliente, monkeypatch):
    monkeypatch.setattr(geracao, "_buscar_contexto", lambda p, k: CONTEXTO)
    resposta = cliente.post("/perguntar", json={"pergunta": "o que diz o teorema CAP?"})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert "CAP" in corpo["resposta"]
    assert [f["origem"] for f in corpo["fontes"]] == ["teorema_cap.txt", "consenso_raft.txt"]
    assert corpo["versao_indice"] == "abc123"


def test_indice_vazio_nao_e_falha(cliente, monkeypatch):
    monkeypatch.setattr(geracao, "_buscar_contexto",
                        lambda p, k: {"versao": "vazio", "resultados": []})
    resposta = cliente.post("/perguntar", json={"pergunta": "qualquer coisa"})
    # 200: o sistema esta saudavel, so nao ha documentos. Um 503 aqui abriria o
    # disjuntor por causa de um sistema que esta de pe.
    assert resposta.status_code == 200
    assert resposta.json()["fontes"] == []
    assert geracao.disjuntor_recuperacao.estado == "fechado"


def test_recuperacao_fora_do_ar_responde_503_e_depois_abre_o_disjuntor(cliente, monkeypatch):
    def recusada(_pergunta, _top_k):
        raise requests.ConnectionError("conexao recusada")

    monkeypatch.setattr(geracao, "_buscar_contexto", recusada)
    for _ in range(3):
        assert cliente.post("/perguntar", json={"pergunta": "oi"}).status_code == 503

    assert geracao.disjuntor_recuperacao.estado == "aberto"
    corpo = cliente.post("/perguntar", json={"pergunta": "oi"}).json()
    assert corpo["motivo"] == "disjuntor_recuperacao_aberto"


def test_llm_fora_do_ar_abre_o_disjuntor_do_llm_e_degrada_com_trechos(cliente, monkeypatch):
    monkeypatch.setattr(geracao, "_buscar_contexto", lambda p, k: CONTEXTO)
    monkeypatch.setattr(geracao, "com_retentativa", _estourar_tempo)

    for _ in range(3):
        assert cliente.post("/perguntar", json={"pergunta": "oi"}).status_code == 503

    assert geracao.disjuntor_llm.estado == "aberto"
    corpo = cliente.post("/perguntar", json={"pergunta": "oi"}).json()
    assert corpo["motivo"] == "disjuntor_llm_aberto"
    # Degradar com elegancia: sem a redacao do LLM, mas com os trechos e as fontes.
    assert len(corpo["trechos"]) == 2
    assert corpo["fontes"][0]["origem"] == "teorema_cap.txt"


def test_falha_do_llm_nao_abre_o_disjuntor_da_recuperacao(cliente, monkeypatch):
    monkeypatch.setattr(geracao, "_buscar_contexto", lambda p, k: CONTEXTO)
    monkeypatch.setattr(geracao, "com_retentativa", _estourar_tempo)
    for _ in range(3):
        cliente.post("/perguntar", json={"pergunta": "oi"})
    # Contadores separados: o LLM fora do ar nao cega a recuperacao.
    assert geracao.disjuntor_llm.estado == "aberto"
    assert geracao.disjuntor_recuperacao.estado == "fechado"


def test_saude_expoe_os_dois_disjuntores(cliente):
    corpo = cliente.get("/saude").json()
    assert corpo["disjuntores"]["recuperacao"]["estado"] == "fechado"
    assert corpo["disjuntores"]["llm"]["estado"] == "fechado"


def test_pergunta_vazia_e_rejeitada(cliente):
    assert cliente.post("/perguntar", json={"pergunta": ""}).status_code == 422


def test_o_modulo_declara_DOIS_disjuntores_independentes():
    """Fiacao, nao comportamento.

    Os testes acima recebem disjuntores limpos da fixture e por isso nao
    percebem se o modulo apontar os dois nomes para o MESMO objeto. Aqui a
    verificacao e do modulo como ele sobe em producao.
    """
    assert geracao.disjuntor_llm is not geracao.disjuntor_recuperacao


def test_resposta_vem_com_avaliacao_automatica(cliente, monkeypatch):
    monkeypatch.setattr(geracao, "_buscar_contexto", lambda p, k: CONTEXTO)
    corpo = cliente.post("/perguntar",
                         json={"pergunta": "o que diz o teorema CAP?"}).json()
    avaliacao = corpo["avaliacao"]
    assert set(avaliacao) == {"fundamentacao", "cobertura_da_pergunta",
                              "veredito", "termos_da_resposta"}
    assert 0.0 <= avaliacao["fundamentacao"] <= 1.0
