"""
Carrega o .env antes de qualquer modulo ler variavel de ambiente.

O kit manda copiar .env.example para .env, mas nada no projeto lia esse arquivo:
quem colocasse a LLM_API_KEY la e rodasse 'uvicorn' continuaria no modo simulado
sem entender por que. Isto resolve - e e por isso que este modulo e importado
PRIMEIRO nos quatro pontos de entrada, antes de servicos.comum.llm, que le a
chave no momento do import.

override=False de proposito: variavel ja definida no ambiente (docker compose,
CI, 'LLM_API_KEY=xxx uvicorn ...') vence o arquivo. O arquivo e o padrao, nao a
autoridade.
"""
import os

CAMINHO_ENV = os.getenv("CAMINHO_ENV", ".env")

try:  # python-dotenv e conveniencia, nao requisito: sem ele valem os defaults.
    from dotenv import load_dotenv

    load_dotenv(CAMINHO_ENV, override=False)
except ModuleNotFoundError:  # pragma: no cover
    pass
