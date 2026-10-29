"""
Tempo-limite e retentativa - exigidos pelo item 4 do edital, junto do disjuntor.

Os tres mecanismos tratam falhas DIFERENTES e por isso convivem:

  tempo-limite  -> a chamada travou. Cortar e melhor que esperar para sempre.
  retentativa   -> a falha foi TRANSITORIA (rede piscou, 429, 503 do provedor).
                   Tentar de novo resolve.
  disjuntor     -> a falha e PERSISTENTE. Insistir so propaga a lentidao;
                   recusar na hora protege o resto do sistema.

Ordem de composicao: o disjuntor envolve a operacao JA com retentativa. Uma
sequencia esgotada de tentativas conta como UMA falha para o disjuntor - se cada
tentativa contasse, o circuito abriria no primeiro soluco de rede.

NUNCA retentar erro permanente (401 chave invalida, 400 pedido malformado):
repetir o mesmo pedido errado so gasta tempo e quota.
"""
import time

import requests

from servicos.comum.log import configurar

logger = configurar("retentativa")

TRANSITORIOS_HTTP = {408, 425, 429, 500, 502, 503, 504}


def e_transitoria(erro: BaseException) -> bool:
    """So estas falhas merecem uma segunda chance."""
    if isinstance(erro, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(erro, requests.HTTPError) and erro.response is not None:
        return erro.response.status_code in TRANSITORIOS_HTTP
    return False


def com_retentativa(funcao, *args, tentativas: int = 3, espera_inicial: float = 0.5,
                    dormir=time.sleep, **kwargs):
    """Executa funcao e repete as falhas transitorias com espera progressiva."""
    ultima_falha = None
    for tentativa in range(1, tentativas + 1):
        try:
            return funcao(*args, **kwargs)
        except BaseException as erro:
            ultima_falha = erro
            if not e_transitoria(erro) or tentativa == tentativas:
                raise
            espera = espera_inicial * (2 ** (tentativa - 1))
            logger.warning("tentativa %d/%d falhou (%s): nova tentativa em %.1fs",
                           tentativa, tentativas, type(erro).__name__, espera)
            dormir(espera)
    raise ultima_falha
