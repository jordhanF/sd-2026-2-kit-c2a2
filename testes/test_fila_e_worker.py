"""Mensageria - TAREFA 4: fila, trava, retentativa e descarte."""
import pytest

from servicos.comum.fila import Fila, TravaOcupada
from servicos.comum.indexador import reindexar
from servicos.comum.repositorio import Repositorio
from servicos.worker import indexador
from testes.duplos import RedisFalso

LOTE = [{"texto": "teorema cap e particao de rede", "origem": "cap"}]


def _fila():
    return Fila(cliente=RedisFalso())


def test_publicar_enfileira_e_registra_status_na_fila():
    fila = _fila()
    identificador = fila.publicar(LOTE)
    assert fila.obter_status(identificador)["status"] == "na_fila"
    assert fila.tamanhos()["fila"] == 1


def test_consumir_entrega_a_tarefa_publicada():
    fila = _fila()
    identificador = fila.publicar(LOTE)
    tarefa = fila.consumir(timeout=0)
    assert tarefa["id"] == identificador
    assert tarefa["documentos"] == LOTE
    assert fila.consumir(timeout=0) is None, "a mesma tarefa foi entregue duas vezes"


def test_trava_impede_dois_escritores_ao_mesmo_tempo():
    fila = _fila()
    with fila.trava("indice"):
        with pytest.raises(TravaOcupada):
            with fila.trava("indice"):
                pass
    # liberada no fim do bloco
    with fila.trava("indice"):
        pass


def test_worker_indexa_e_persiste(tmp_path):
    fila = _fila()
    repositorio = Repositorio(str(tmp_path))
    fila.publicar(LOTE)
    resultado = indexador.processar(fila.consumir(timeout=0), repositorio, fila)
    assert resultado["total"] == 1
    assert Repositorio(str(tmp_path)).carregar().total == 1


def test_falha_volta_para_a_fila_com_uma_tentativa_a_mais(monkeypatch):
    monkeypatch.setattr(indexador.time, "sleep", lambda _s: None)
    fila = _fila()
    fila.publicar(LOTE)
    tarefa = fila.consumir(timeout=0)
    indexador._tratar_falha(tarefa, fila, RuntimeError("erro de mentira"))
    devolvida = fila.consumir(timeout=0)
    assert devolvida["tentativas"] == 1
    assert fila.obter_status(devolvida["id"])["status"] == "retentando"


def test_tentativas_esgotadas_vao_para_o_descarte_com_estado_terminal(monkeypatch):
    monkeypatch.setattr(indexador.time, "sleep", lambda _s: None)
    fila = _fila()
    fila.publicar(LOTE)
    tarefa = fila.consumir(timeout=0)
    tarefa["tentativas"] = indexador.MAX_TENTATIVAS - 1
    indexador._tratar_falha(tarefa, fila, RuntimeError("erro de mentira"))

    assert fila.tamanhos() == {"fila": 0, "descarte": 1}
    # Falha tem estado TERMINAL: sem isto o cliente consultaria para sempre.
    estado = fila.obter_status(tarefa["id"])
    assert estado["status"] == "erro" and "erro de mentira" in estado["erro"]


def test_republicar_nao_gasta_tentativa():
    fila = _fila()
    fila.publicar(LOTE)
    tarefa = fila.consumir(timeout=0)
    fila.republicar(tarefa)
    assert fila.consumir(timeout=0)["tentativas"] == 0


def test_gatilho_de_falha_simulada(monkeypatch):
    monkeypatch.setattr(indexador, "SIMULAR_FALHA_EM", "explode")
    with pytest.raises(RuntimeError):
        indexador._conferir_gatilho_de_falha([{"texto": "isso vai explode aqui",
                                               "origem": "x"}])
    indexador._conferir_gatilho_de_falha([{"texto": "texto normal", "origem": "x"}])


def test_indice_do_worker_fica_comparavel_ao_vetorizador_salvo(tmp_path):
    """Vetor e vocabulario tem de sair da MESMA operacao de escrita."""
    fila = _fila()
    repositorio = Repositorio(str(tmp_path))
    fila.publicar(LOTE)
    indexador.processar(fila.consumir(timeout=0), repositorio, fila)

    indice = Repositorio(str(tmp_path)).carregar()
    vetor_pergunta = indice.vetorizador.vetorizar("teorema cap")
    assert len(vetor_pergunta) == len(indice.itens[0]["vetor"])
    esperado, _ = reindexar(LOTE)
    assert len(esperado[0]["vetor"]) == len(vetor_pergunta)
