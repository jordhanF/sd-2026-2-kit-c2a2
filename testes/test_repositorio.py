"""Persistencia do indice - TAREFA 1: sobreviver ao reinicio."""
import json
import os

from servicos.comum.indexador import reindexar
from servicos.comum.repositorio import Repositorio, calcular_versao

CORPUS = [{"texto": "teorema cap e particao", "origem": "cap"},
          {"texto": "consenso raft e lider", "origem": "raft"}]


def test_indice_sobrevive_a_um_processo_novo(tmp_path):
    itens, vetorizador = reindexar(CORPUS)
    Repositorio(str(tmp_path)).salvar(itens, vetorizador)

    # Outro Repositorio = outro processo subindo depois do reinicio.
    recarregado = Repositorio(str(tmp_path)).carregar()
    assert recarregado.total == 2
    assert not recarregado.vazio
    # O vetorizador volta junto: vetor sem o vocabulario que o produziu e lixo.
    assert recarregado.vetorizador is not None
    assert len(recarregado.vetorizador.vetorizar("teorema cap")) == len(itens[0]["vetor"])


def test_diretorio_vazio_devolve_indice_vazio(tmp_path):
    indice = Repositorio(str(tmp_path)).carregar()
    assert indice.vazio and indice.versao == "vazio" and indice.total == 0


def test_versao_e_estavel_para_o_mesmo_corpus_e_muda_com_documento_novo():
    assert calcular_versao(CORPUS) == calcular_versao(list(CORPUS))
    outro = CORPUS + [{"texto": "falha parcial", "origem": "sd"}]
    assert calcular_versao(outro) != calcular_versao(CORPUS)


def test_leitor_percebe_a_escrita_do_outro_processo(tmp_path):
    leitor = Repositorio(str(tmp_path))
    assert leitor.recarregar_se_mudou().vazio

    escritor = Repositorio(str(tmp_path))
    itens, vetorizador = reindexar(CORPUS)
    escritor.salvar(itens, vetorizador)

    # O leitor nao foi avisado por ninguem: ele compara a assinatura do arquivo.
    assert leitor.recarregar_se_mudou().total == 2


def test_gravacao_nao_deixa_arquivo_temporario_para_tras(tmp_path):
    itens, vetorizador = reindexar(CORPUS)
    Repositorio(str(tmp_path)).salvar(itens, vetorizador)
    assert not [n for n in os.listdir(tmp_path) if n.endswith(".tmp")]
    assert sorted(os.listdir(tmp_path)) == ["indice.json", "vetorizador.joblib"]


def test_arquivo_gravado_e_json_legivel_com_versao(tmp_path):
    itens, vetorizador = reindexar(CORPUS)
    indice = Repositorio(str(tmp_path)).salvar(itens, vetorizador)
    with open(tmp_path / "indice.json", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    assert dados["versao"] == indice.versao
    assert dados["atualizado_em"]
    assert len(dados["itens"]) == 2
