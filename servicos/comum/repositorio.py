"""
Persistencia do indice - TAREFA 1.

O indice do kit vivia numa lista em memoria e sumia ao reiniciar. Aqui ele mora
em disco, em dois arquivos:

  dados/indice.json         -> {versao, atualizado_em, itens:[{texto, origem, vetor}]}
  dados/vetorizador.joblib  -> o Vetorizador TF-IDF ja ajustado

Os dois precisam andar juntos: um vetor so faz sentido no vocabulario que o
produziu. Por isso sao gravados na mesma operacao.

Gravacao ATOMICA: escreve num arquivo temporario no mesmo diretorio e troca com
os.replace(). Um worker morto no meio da escrita nao deixa indice truncado -
quem le encontra a versao anterior, inteira.
"""
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

import joblib

from servicos.comum.embeddings import Vetorizador

CAMINHO_DADOS = os.getenv("CAMINHO_DADOS", "dados")
VERSAO_VAZIA = "vazio"


def calcular_versao(itens: list) -> str:
    """SHA-1 do corpus. Mesma lista de documentos -> mesma versao.

    Serve de chave de cache na recuperacao e de prova de que dois servicos
    estao falando do MESMO indice.
    """
    if not itens:
        return VERSAO_VAZIA
    digest = hashlib.sha1()
    for item in itens:
        digest.update(item["origem"].encode("utf-8"))
        digest.update(b"\x00")
        digest.update(item["texto"].encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()[:12]


@dataclass
class Indice:
    versao: str = VERSAO_VAZIA
    atualizado_em: str | None = None
    itens: list = field(default_factory=list)
    vetorizador: Vetorizador | None = None

    @property
    def vazio(self) -> bool:
        return not self.itens

    @property
    def total(self) -> int:
        return len(self.itens)


def _gravar_atomico(caminho: str, gravar) -> None:
    diretorio = os.path.dirname(os.path.abspath(caminho))
    os.makedirs(diretorio, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(dir=diretorio, suffix=".tmp")
    os.close(descritor)
    try:
        gravar(temporario)
        os.replace(temporario, caminho)
    except BaseException:
        if os.path.exists(temporario):
            os.unlink(temporario)
        raise


class Repositorio:
    """Dono dos arquivos do indice. O worker escreve, a ingestao le."""

    def __init__(self, diretorio: str | None = None):
        self.diretorio = diretorio or CAMINHO_DADOS
        self.arquivo_indice = os.path.join(self.diretorio, "indice.json")
        self.arquivo_vetorizador = os.path.join(self.diretorio, "vetorizador.joblib")
        self._indice = Indice()
        self._assinatura = None

    def _assinatura_disco(self):
        try:
            estado = os.stat(self.arquivo_indice)
        except FileNotFoundError:
            return None
        return (estado.st_mtime_ns, estado.st_size)

    def carregar(self) -> Indice:
        """Le os dois arquivos do disco. Indice vazio se ainda nao existirem."""
        assinatura = self._assinatura_disco()
        if assinatura is None:
            self._indice = Indice()
            self._assinatura = None
            return self._indice
        with open(self.arquivo_indice, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        vetorizador = None
        if os.path.exists(self.arquivo_vetorizador):
            vetorizador = joblib.load(self.arquivo_vetorizador)
        self._indice = Indice(
            versao=dados.get("versao", VERSAO_VAZIA),
            atualizado_em=dados.get("atualizado_em"),
            itens=dados.get("itens", []),
            vetorizador=vetorizador,
        )
        self._assinatura = assinatura
        return self._indice

    def recarregar_se_mudou(self) -> Indice:
        """Como um processo leitor descobre a escrita do outro.

        A ingestao nao e quem grava o indice - o worker e. Comparar a assinatura
        do arquivo (mtime + tamanho) a cada requisicao e barato e evita servir
        indice velho depois de uma indexacao.
        """
        if self._assinatura_disco() != self._assinatura:
            return self.carregar()
        return self._indice

    def salvar(self, itens: list, vetorizador: Vetorizador) -> Indice:
        """Grava corpus e vetorizador juntos, de forma atomica."""
        indice = Indice(
            versao=calcular_versao(itens),
            atualizado_em=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            itens=itens,
            vetorizador=vetorizador,
        )
        _gravar_atomico(self.arquivo_vetorizador,
                        lambda destino: joblib.dump(vetorizador, destino))
        _gravar_atomico(self.arquivo_indice, lambda destino: _gravar_json(destino, indice))
        self._indice = indice
        self._assinatura = self._assinatura_disco()
        return indice


def _gravar_json(destino: str, indice: Indice) -> None:
    with open(destino, "w", encoding="utf-8") as arquivo:
        json.dump({"versao": indice.versao,
                   "atualizado_em": indice.atualizado_em,
                   "itens": indice.itens}, arquivo, ensure_ascii=False)
