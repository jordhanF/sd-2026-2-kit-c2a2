"""O disjuntor de referencia do kit, no ciclo completo de estados."""
import pytest

from servicos.comum.circuit_breaker import CircuitBreaker, CircuitoAberto


def _falha():
    raise RuntimeError("dependencia fora do ar")


def test_fechado_deixa_passar():
    disjuntor = CircuitBreaker(limite_falhas=2, espera_segundos=1)
    assert disjuntor.chamar(lambda: "ok") == "ok"
    assert disjuntor.estado == "fechado"


def test_abre_no_limite_de_falhas_e_passa_a_recusar_na_hora():
    disjuntor = CircuitBreaker(limite_falhas=2, espera_segundos=60)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            disjuntor.chamar(_falha)
    assert disjuntor.estado == "aberto"

    chamadas = {"n": 0}

    def contar():
        chamadas["n"] += 1

    with pytest.raises(CircuitoAberto):
        disjuntor.chamar(contar)
    # O valor do disjuntor esta aqui: nao tentou. Nao paga o tempo-limite.
    assert chamadas["n"] == 0


def test_depois_da_espera_deixa_passar_uma_chamada_de_teste_e_fecha():
    disjuntor = CircuitBreaker(limite_falhas=1, espera_segundos=0)
    with pytest.raises(RuntimeError):
        disjuntor.chamar(_falha)
    assert disjuntor.estado == "aberto"
    assert disjuntor.chamar(lambda: "voltou") == "voltou"
    assert disjuntor.estado == "fechado"


def test_falha_na_chamada_de_teste_reabre_o_circuito():
    disjuntor = CircuitBreaker(limite_falhas=1, espera_segundos=0)
    with pytest.raises(RuntimeError):
        disjuntor.chamar(_falha)
    with pytest.raises(RuntimeError):
        disjuntor.chamar(_falha)
    assert disjuntor.estado == "aberto"


def test_sucesso_zera_o_contador_de_falhas():
    disjuntor = CircuitBreaker(limite_falhas=3, espera_segundos=60)
    with pytest.raises(RuntimeError):
        disjuntor.chamar(_falha)
    disjuntor.chamar(lambda: "ok")
    assert disjuntor.falhas == 0 and disjuntor.estado == "fechado"
