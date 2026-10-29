"""Avaliacao automatica da resposta - extensao opcional do edital."""
from servicos.comum.avaliacao import avaliar

CONTEXTO = ["O teorema CAP afirma que, diante de uma particao de rede, um sistema "
            "distribuido precisa escolher entre consistencia e disponibilidade."]
PERGUNTA = "o que diz o teorema CAP sobre particao?"


def test_resposta_ancorada_no_contexto_e_fundamentada():
    """Parafrase boa nao chega a 1,0 - e nao deveria.

    "escolher" no contexto e "escolhe" na resposta sao termos diferentes para uma
    medida lexical. Uma resposta fiel e reescrita fica em torno de 0,85; exigir
    quase 1,0 premiaria copiar o contexto palavra por palavra.
    """
    resposta = ("O teorema CAP diz que diante de uma particao de rede o sistema "
                "escolhe entre consistencia e disponibilidade.")
    medida = avaliar(PERGUNTA, resposta, CONTEXTO)
    assert 0.8 <= medida["fundamentacao"] < 1.0
    assert medida["veredito"] == "fundamentada"


def test_resposta_inventada_perde_fundamentacao():
    """O sintoma classico de alucinacao: falar do que ninguem recuperou."""
    resposta = ("A receita leva farinha, ovos, manteiga e acucar, assados em forno "
                "medio durante quarenta minutos.")
    medida = avaliar(PERGUNTA, resposta, CONTEXTO)
    assert medida["fundamentacao"] < 0.2
    assert medida["veredito"] == "pouco respaldo no contexto"


def test_contexto_que_nao_responde_a_pergunta_acusa_a_recuperacao():
    """Cobertura baixa aponta para o servico de recuperacao, nao para o gerador."""
    medida = avaliar("como funciona a eleicao de lider no Raft?",
                     "Nao sei responder com o material disponivel.",
                     ["Receita de bolo: farinha, ovos e manteiga no forno."])
    assert medida["cobertura_da_pergunta"] == 0.0
    assert medida["veredito"] == "contexto fraco para a pergunta"


def test_sem_contexto_nao_estoura():
    medida = avaliar(PERGUNTA, "qualquer coisa", [])
    assert medida["veredito"] == "sem contexto"
    assert medida["fundamentacao"] == 0.0


def test_resposta_vazia_nao_divide_por_zero():
    medida = avaliar(PERGUNTA, "", CONTEXTO)
    assert medida["fundamentacao"] == 0.0
    assert medida["termos_da_resposta"] == 0


def test_acento_nao_derruba_a_medida():
    """Pergunta acentuada e contexto sem acento tem de casar."""
    medida = avaliar("consistência e disponibilidade?",
                     "Consistencia e disponibilidade.", CONTEXTO)
    assert medida["cobertura_da_pergunta"] == 1.0
    assert medida["fundamentacao"] == 1.0
