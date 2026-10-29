# C2.A2 — RAG distribuído em microsserviços (desenho)

**Data:** 29/10/2026 · **Disciplina:** Sistemas Distribuídos e Computação em Nuvem — FAESA 2026/2
**Kit de partida:** `howardroatti/sd-2026-2-kit-c2a2` · **Entrega:** `jordhanF/sd-2026-2-kit-c2a2`

## Objetivo

Completar o núcleo obrigatório das seis tarefas do kit (persistência do índice, busca por
similaridade, circuit breaker no LLM, mensageria, fluxo ponta a ponta e README com diagrama),
no padrão da entrega C1.A2: README com diagrama, decisões de projeto justificadas e limitações
conhecidas declaradas.

A rubrica pontua **engenharia distribuída** — arquitetura (1,5), comunicação (1,5), resiliência
(1,0) e execução reproduzível (1,0). A sofisticação do modelo de IA **não pontua**, então o
TF-IDF do kit permanece.

## Arquitetura

Quatro processos, uma responsabilidade cada:

| Processo | Responsabilidade | Porta |
|---|---|---|
| `servicos/ingestao` | dono do índice e do espaço vetorial; aceita documentos, publica na fila, serve o índice | 8001 |
| `servicos/worker` | reajusta o vocabulário, revetoriza o corpus e persiste — fora do caminho da requisição | — |
| `servicos/recuperacao` | compara a pergunta com o índice e devolve os `top_k` | 8002 |
| `servicos/geracao` | monta o prompt, chama o LLM, cita as fontes | 8003 |

Módulos compartilhados em `servicos/comum/`: `embeddings.py` e `circuit_breaker.py` (do kit,
intocados), mais `repositorio.py` (persistência), `fila.py` (Redis) e `log.py` (log padronizado).

### Por que a mensageria entra na indexação

O TF-IDF tem **vocabulário global**: indexar um documento novo reajusta o espaço vetorial inteiro
e obriga a revetorizar todo o corpus. É operação de lote, de custo proporcional ao índice, que não
cabe no caminho de uma requisição HTTP. Logo `POST /indexar` devolve **202** e publica na fila; o
worker faz o trabalho.

A consulta (`/perguntar`) permanece sincrona — a TAREFA 5 pede que a pergunta entre e a resposta
saia, sem polling.

### Por que a recuperação não vetoriza sozinha

O espaço vetorial é um só e tem um dono. A recuperação pede o vetor da pergunta à ingestão
(`POST /vetorizar`) em vez de reconstruir o vetorizador localmente: duas réplicas do vocabulário
seriam duas fontes de verdade, e a comparação daria silenciosamente errado quando divergissem.

## Contratos

### Ingestão (8001)
- `POST /indexar` — `[{texto, origem}]` → **202** `{id, status:"na_fila", documentos:N}`
- `GET /tarefa/{id}` → `{status: na_fila|processando|pronto|erro, ...}` · **404** se desconhecido
- `GET /indice` → `{versao, total, itens:[{texto, origem, vetor}]}`
- `GET /indice/versao` → `{versao, total}` (sonda leve para invalidar cache)
- `POST /vetorizar` — `{texto}` → `{vetor, versao}` · **409** se o índice estiver vazio
- `GET /saude` → `{status, documentos, versao}`

### Recuperação (8002)
- `POST /buscar` — `{pergunta, top_k}` → `{resultados:[{texto, origem, score, cobertura}], versao}`
- `GET /saude`

### Geração (8003)
- `POST /perguntar` — `{pergunta}` → `{pergunta, resposta, fontes:[{origem, score}], contexto}`
  · **503** quando um dos disjuntores está aberto
- `GET /saude` → `{status, disjuntores:{recuperacao, llm}}`

## Persistência (TAREFA 1)

`dados/indice.json` (`{versao, atualizado_em, itens:[{texto, origem, vetor}]}`) e
`dados/vetorizador.joblib` (o `Vetorizador` ajustado). Gravação **atômica**: arquivo temporário
no mesmo diretório + `os.replace`, para que um worker morto no meio da escrita não deixe índice
truncado.

`versao` é o SHA-1 do corpus (`origem` + `texto`, em ordem). Serve de chave de cache e de prova de
que dois serviços estão falando do mesmo índice.

O volume é compartilhado entre worker (escreve) e ingestão (lê). A ingestão compara o `mtime` a
cada requisição e recarrega quando mudou — é como um processo de leitura descobre a escrita do outro.

## Fila e resiliência (TAREFAS 3 e 4)

- Fila `indexacao` no Redis, consumida com `BLPOP`.
- **Escritor único:** o worker toma um lock (`SET NX PX`) antes de reescrever o índice. Reajuste
  de vocabulário é escrita no índice todo; dois escritores simultâneos se sobrescreveriam.
- **Retentativa + descarte:** 3 tentativas com espera progressiva; depois a tarefa vai para a fila
  `descarte` e o status fica `erro`. Falha tem estado terminal — sem isso o cliente consultaria
  `/tarefa/{id}` para sempre sem descobrir que a tarefa morreu.
- **Dois disjuntores no serviço de geração**, não um: `disjuntor_recuperacao` cobre a chamada HTTP
  à recuperação e `disjuntor_llm` cobre `gerar(...)`. O checklist do kit manda derrubar a
  *recuperação* e ver o circuito abrir — um disjuntor só no LLM não atenderia. Cada um devolve 503
  com mensagem própria, e `GET /saude` expõe os dois estados.
- **Cache do índice na recuperação**, invalidado por `versao`: a sonda `/indice/versao` é barata e
  evita trafegar todos os vetores a cada pergunta.
- **Índice vazio não é falha:** `/buscar` devolve lista vazia e a geração responde que não há
  documentos indexados — 200, não 503.

## Execução reproduzível

Um **Dockerfile único** compartilhado pelos quatro processos (mesma base, mesmas dependências; só
o `command` muda no compose) — quatro Dockerfiles idênticos seriam duplicação. `docker-compose.yml`
com `redis + ingestao + worker + recuperacao + geracao`, healthchecks, `depends_on` e volume do
índice. Segredos só por variável de ambiente (`.env`), nunca no código.

## Testes

Suíte `pytest` offline e sem servidor de pé:
- busca ordena por similaridade e respeita `top_k`;
- reranking não quebra a ordenação quando a cobertura empata;
- persistência sobrevive ao reinício (gravar, recarregar, comparar versão);
- disjuntor percorre fechado → aberto → meio → fechado;
- `/perguntar` devolve 503 com o disjuntor aberto (TestClient + duplo de teste).

Scripts em `exemplos/`: indexar `documentos/`, perguntar, e derrubar a recuperação para ver o
disjuntor abrir.

## Extensões incluídas

- **Citação das fontes:** a resposta carrega `origem` e score de cada trecho que a embasou.
- **Reranking:** os `top_k * 2` melhores por cosseno são reordenados por cobertura dos termos da
  pergunta (sem acento, minúsculas) e só então cortados em `top_k`.

Fora de escopo: `sentence-transformers` (exigiria download de ~90 MB e quebraria a promessa de
rodar offline no laboratório, sem pontuar na rubrica).

## Limitações aceitas

- `BLPOP` remove a tarefa antes de processá-la: worker morto no meio perde aquela tarefa.
- O reajuste do vocabulário é O(corpus) a cada lote — serve para a escala do trabalho, não para
  um índice grande; um banco vetorial de verdade resolveria.
- Status de tarefa com TTL no Redis; índice sem compactação ou remoção de documentos.
- Sem autenticação nem limite de requisições.
