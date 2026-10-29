"""
Fila de indexacao no Redis - TAREFA 4.

Mecanismo aqui, politica no worker: este modulo sabe COMO publicar, consumir,
devolver e descartar uma tarefa. QUANTAS vezes tentar e QUANTO esperar e decisao
do worker (servicos/worker/indexador.py).

Chaves usadas:
  indexacao       (lista)  fila de trabalho, consumida com BLPOP
  descarte        (lista)  dead-letter: tarefas que esgotaram as tentativas
  tarefa:<id>     (string) status da tarefa, com TTL
  trava:indice    (string) lock de escritor unico do indice
"""
import json
import os
import time
import uuid
from contextlib import contextmanager

import redis

URL_REDIS = os.getenv("REDIS_URL", "redis://localhost:6379/0")
FILA = os.getenv("FILA_INDEXACAO", "indexacao")
FILA_DESCARTE = os.getenv("FILA_DESCARTE", "descarte")
TTL_STATUS = int(os.getenv("TTL_STATUS_SEGUNDOS", "86400"))
MAX_TENTATIVAS = int(os.getenv("MAX_TENTATIVAS", "3"))


class TravaOcupada(Exception):
    """Outro processo detem a trava do indice."""


def conectar(url: str | None = None) -> redis.Redis:
    """Cliente Redis. Nao abre conexao aqui - so no primeiro comando.

    Isso e deliberado: a ingestao precisa SUBIR mesmo com o Redis fora do ar, e
    falhar com 503 apenas na rota que depende da fila.
    """
    return redis.Redis.from_url(url or URL_REDIS, decode_responses=True,
                               socket_connect_timeout=3, socket_timeout=5)


class Fila:

    def __init__(self, cliente: redis.Redis | None = None):
        self.redis = cliente or conectar()

    # ---------- producao ----------

    def publicar(self, documentos: list) -> str:
        """Enfileira um lote e devolve o id da tarefa."""
        identificador = uuid.uuid4().hex[:12]
        tarefa = {"id": identificador, "documentos": documentos, "tentativas": 0,
                  "criada_em": time.time()}
        self.definir_status(identificador, status="na_fila",
                            documentos=len(documentos), tentativas=0)
        self.redis.rpush(FILA, json.dumps(tarefa))
        return identificador

    # ---------- consumo ----------

    def consumir(self, timeout: int = 5):
        """Bloqueia ate chegar tarefa (ou o timeout). Devolve o dict ou None."""
        item = self.redis.blpop(FILA, timeout=timeout)
        if item is None:
            return None
        return json.loads(item[1])

    def republicar(self, tarefa: dict) -> None:
        """Recoloca a tarefa na fila SEM gastar tentativa.

        Usado quando o impedimento nao e culpa da tarefa (outro worker detem a
        trava do indice). Contar isso como falha levaria uma tarefa boa ao
        descarte so porque o sistema estava ocupado.
        """
        self.definir_status(tarefa["id"], status="na_fila")
        self.redis.rpush(FILA, json.dumps(tarefa))

    def devolver(self, tarefa: dict) -> None:
        """Recoloca a tarefa no fim da fila, com uma tentativa a mais."""
        tarefa["tentativas"] = tarefa.get("tentativas", 0) + 1
        self.definir_status(tarefa["id"], status="retentando",
                            tentativas=tarefa["tentativas"])
        self.redis.rpush(FILA, json.dumps(tarefa))

    def descartar(self, tarefa: dict, erro: str) -> None:
        """Dead-letter. Falha tem estado TERMINAL.

        Sem gravar 'erro' no status, o cliente consultaria /tarefa/{id} para
        sempre sem nunca descobrir que a tarefa morreu - falha silenciosa, que e
        pior que falha ruidosa.
        """
        tarefa["erro"] = erro
        self.redis.rpush(FILA_DESCARTE, json.dumps(tarefa))
        self.definir_status(tarefa["id"], status="erro", erro=erro,
                            tentativas=tarefa.get("tentativas", 0))

    # ---------- status ----------

    def definir_status(self, identificador: str, **campos) -> None:
        chave = f"tarefa:{identificador}"
        atual = self.obter_status(identificador) or {"id": identificador}
        atual.update(campos)
        atual["atualizado_em"] = time.time()
        self.redis.set(chave, json.dumps(atual), ex=TTL_STATUS)

    def obter_status(self, identificador: str):
        bruto = self.redis.get(f"tarefa:{identificador}")
        return json.loads(bruto) if bruto else None

    # ---------- trava ----------

    @contextmanager
    def trava(self, nome: str = "indice", ttl_segundos: int = 60):
        """Escritor unico do indice.

        Reindexar e escrita no indice INTEIRO (o vocabulario muda). Dois workers
        reindexando ao mesmo tempo se sobrescreveriam e um dos lotes desapareceria
        sem erro. O TTL garante que um worker morto nao tranque a fila para sempre.
        """
        chave = f"trava:{nome}"
        token = uuid.uuid4().hex
        if not self.redis.set(chave, token, nx=True, px=ttl_segundos * 1000):
            raise TravaOcupada(f"trava '{nome}' ocupada")
        try:
            yield
        finally:
            if self.redis.get(chave) == token:
                self.redis.delete(chave)

    # ---------- diagnostico ----------

    def tamanhos(self) -> dict:
        return {"fila": self.redis.llen(FILA), "descarte": self.redis.llen(FILA_DESCARTE)}

    def disponivel(self) -> bool:
        try:
            return bool(self.redis.ping())
        except redis.RedisError:
            return False
