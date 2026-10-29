"""
Embeddings da disciplina - PRONTO, NAO PRECISA ALTERAR.

Transforma texto em vetor de numeros. Usa TF-IDF (offline, sem download).
Se quiser trocar por um modelo de embeddings de verdade (sentence-transformers),
basta manter a mesma interface: ajustar(textos) e vetorizar(texto).

Voce NAO precisa entender a matematica. Precisa saber:
  - vetorizar(texto) devolve uma lista de numeros
  - similaridade(a, b) devolve o quanto dois vetores se parecem (0 a 1)
"""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class Vetorizador:

    def __init__(self):
        self._tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        self._ajustado = False

    def ajustar(self, textos):
        """Aprende o vocabulario a partir dos documentos indexados."""
        self._tfidf.fit(textos)
        self._ajustado = True

    def vetorizar(self, texto):
        if not self._ajustado:
            raise RuntimeError("chame ajustar() antes de vetorizar()")
        return self._tfidf.transform([texto]).toarray()[0].tolist()


def similaridade(a, b):
    """Similaridade do cosseno entre dois vetores."""
    va, vb = np.array(a), np.array(b)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))
