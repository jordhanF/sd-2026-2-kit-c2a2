# TAREFAS - Trabalho C2.A2 (RAG Distribuido)

## Nucleo obrigatorio

- [x] **1. Persistir o indice** - `servicos/ingestao/app.py`
      Feito em `servicos/comum/repositorio.py`: `dados/indice.json` + o vetorizador
      em `dados/vetorizador.joblib`, gravados na mesma operacao e de forma atomica
      (arquivo temporario + `os.replace`). A ingestao recarrega quando o arquivo muda.

- [x] **2. Busca por similaridade** - `servicos/recuperacao/app.py`
      O vetor da pergunta vem de quem e dono do espaco vetorial (`POST /vetorizar`
      na ingestao); a comparacao e a ordenacao ficam em `servicos/comum/ranking.py`,
      em funcoes puras. Trecho com cosseno zero nao entra no resultado.

- [x] **3. Circuit breaker no LLM** - `servicos/geracao/app.py`
      Dois disjuntores: um para a chamada a recuperacao, outro para o LLM. 503 com
      `motivo` quando o circuito esta aberto, e o corpo leva os trechos recuperados.
      Com tempo-limite (`LLM_TIMEOUT`) e retentativa (`servicos/comum/retentativa.py`).

- [x] **4. Mensageria** - novo worker + `docker-compose.yml`
      `POST /indexar` responde 202 e publica na fila `indexacao` do Redis;
      `servicos/worker/indexador.py` consome, reindexa sob trava de escritor unico,
      retenta 3 vezes com espera progressiva e descarta na fila `descarte`.

- [x] **5. Fluxo completo** - de ponta a ponta
      `python exemplos/fluxo_completo.py` indexa a base e exige resposta fundamentada
      em tres perguntas, conferindo a fonte esperada de cada uma.

- [x] **6. README com diagrama** da arquitetura dos tres servicos.
      Diagrama da arquitetura, diagrama de sequencia da pergunta, medicoes reais,
      decisoes de projeto e limitacoes conhecidas.

## Extensoes opcionais

- [x] Reordenar os trechos por relevancia (reranking) - cosseno + cobertura dos termos
      da pergunta, em `servicos/comum/ranking.py`.
- [x] Citar quais documentos embasaram a resposta - campo `fontes` em `/perguntar`,
      com o melhor score de cada origem.
- [x] Persistir os vetores em disco - `servicos/comum/repositorio.py` (item 1).
- [x] Avaliacao automatica simples da qualidade da resposta - `servicos/comum/avaliacao.py`:
      fundamentacao da resposta no contexto e cobertura da pergunta pelo contexto,
      com veredito legivel no campo `avaliacao` de `/perguntar`.
- [ ] Trocar TF-IDF por embeddings de verdade (sentence-transformers) - fora de escopo:
      exigiria ~90 MB de download e quebraria a promessa de rodar offline.

## Antes de entregar

- [x] Desligue a internet: o modo simulado do LLM mantem o sistema de pe?
      Sim - sem `LLM_API_KEY` nenhuma chamada sai da maquina. Verificado com
      `exemplos/fluxo_completo.py`.
- [x] Derrube o servico de recuperacao: o disjuntor abre como esperado?
      Sim - 3 falhas de 2,04s e o circuito abre; as seguintes sao recusadas em 0,01s.
      Roteiro e saida real no README (`exemplos/roteiro_disjuntor.py`).
- [x] A chave da API esta FORA do codigo (em variavel de ambiente)?
      Sim - `LLM_API_KEY` lida do ambiente, `.env` no `.gitignore`, compose repassa
      a variavel sem valor embutido.
- [x] Apague a pasta, clone do zero e siga o SEU proprio README.
      Feito: clone limpo + `docker compose up -d --build` + `fluxo_completo.py`.
