"""Tempo-limite e retentativa - item 4 do edital."""
import pytest
import requests

from servicos.comum.retentativa import com_retentativa, e_transitoria


class _Resposta:
    def __init__(self, codigo):
        self.status_code = codigo


def _erro_http(codigo):
    return requests.HTTPError(response=_Resposta(codigo))


def test_falha_transitoria_e_repetida_e_pode_dar_certo():
    chamadas = {"n": 0}

    def instavel():
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise requests.Timeout("estourou o tempo-limite")
        return "ok"

    assert com_retentativa(instavel, tentativas=3, dormir=lambda _s: None) == "ok"
    assert chamadas["n"] == 3


def test_erro_permanente_nao_e_repetido():
    chamadas = {"n": 0}

    def chave_invalida():
        chamadas["n"] += 1
        raise _erro_http(401)

    with pytest.raises(requests.HTTPError):
        com_retentativa(chave_invalida, tentativas=3, dormir=lambda _s: None)
    # Repetir o mesmo pedido errado so gasta tempo e quota.
    assert chamadas["n"] == 1


def test_tentativas_esgotadas_propagam_a_falha():
    def sempre_falha():
        raise requests.ConnectionError("rede fora")

    with pytest.raises(requests.ConnectionError):
        com_retentativa(sempre_falha, tentativas=3, dormir=lambda _s: None)


def test_espera_e_progressiva():
    esperas = []

    def sempre_falha():
        raise requests.Timeout("lento")

    with pytest.raises(requests.Timeout):
        com_retentativa(sempre_falha, tentativas=3, espera_inicial=0.5,
                        dormir=esperas.append)
    assert esperas == [0.5, 1.0]


def test_classificacao_de_falhas():
    assert e_transitoria(requests.Timeout())
    assert e_transitoria(requests.ConnectionError())
    assert e_transitoria(_erro_http(503))
    assert e_transitoria(_erro_http(429))
    assert not e_transitoria(_erro_http(400))
    assert not e_transitoria(ValueError("erro de programacao"))
