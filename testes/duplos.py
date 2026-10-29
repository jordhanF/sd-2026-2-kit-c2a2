"""Duplos de teste: um Redis de mentira, suficiente para a fila do trabalho."""
import time


class RedisFalso:
    """Implementa so o que servicos/comum/fila.py usa."""

    def __init__(self):
        self.strings = {}
        self.listas = {}

    # strings
    def set(self, chave, valor, ex=None, nx=False, px=None):
        if nx and chave in self.strings:
            return None
        self.strings[chave] = valor
        return True

    def get(self, chave):
        return self.strings.get(chave)

    def delete(self, chave):
        self.strings.pop(chave, None)

    # listas
    def rpush(self, chave, valor):
        self.listas.setdefault(chave, []).append(valor)
        return len(self.listas[chave])

    def blpop(self, chave, timeout=0):
        fila = self.listas.get(chave, [])
        if not fila:
            return None
        return (chave, fila.pop(0))

    def llen(self, chave):
        return len(self.listas.get(chave, []))

    def ping(self):
        return True


def sem_dormir(_segundos):
    """Substitui time.sleep nos testes de retentativa."""
    return None


def agora():
    return time.time()
