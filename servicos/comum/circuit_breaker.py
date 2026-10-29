"""
Circuit breaker de referencia - Aula 13.

Este arquivo esta COMPLETO e serve de modelo. Voce vai adapta-lo para
proteger a chamada ao LLM no servico de geracao.

Estados:
  fechado  -> deixa passar (normal)
  aberto   -> recusa na hora, sem tentar (servico esta quebrado)
  meio     -> deixa passar UMA chamada de teste para ver se voltou
"""
import time


class CircuitoAberto(Exception):
    """Levantada quando o disjuntor esta aberto e recusa a chamada."""


class CircuitBreaker:

    def __init__(self, limite_falhas=5, espera_segundos=30):
        self.limite_falhas = limite_falhas
        self.espera_segundos = espera_segundos
        self.falhas = 0
        self.estado = "fechado"
        self.aberto_em = 0.0

    def chamar(self, funcao, *args, **kwargs):
        if self.estado == "aberto":
            if time.time() - self.aberto_em >= self.espera_segundos:
                self.estado = "meio"
            else:
                raise CircuitoAberto("disjuntor aberto: chamada recusada")
        try:
            resultado = funcao(*args, **kwargs)
        except Exception:
            self._registrar_falha()
            raise
        self._registrar_sucesso()
        return resultado

    def _registrar_falha(self):
        self.falhas += 1
        if self.falhas >= self.limite_falhas or self.estado == "meio":
            self.estado = "aberto"
            self.aberto_em = time.time()

    def _registrar_sucesso(self):
        self.falhas = 0
        self.estado = "fechado"
