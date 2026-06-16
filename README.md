# Advogado de Bolso

Assistente de direitos do consumidor brasileiro com chat via terminal, API HTTP,
interface web responsiva e busca em uma base local de documentos.

> A aplicacao oferece informacao geral. Ela nao substitui orientacao juridica
> individualizada de advogado, Defensoria Publica, PROCON ou outro orgao competente.

## Inicio rapido

Requisitos: Python 3.11 ou superior, [uv](https://docs.astral.sh/uv/),
Node.js 20+ e npm 10+.

```powershell
uv sync --extra dev --cache-dir .uv-cache
Copy-Item .env.example .env
```

Preencha `GEMINI_API_KEY` em `.env`. Depois, adicione arquivos PDF, HTML,
Markdown ou TXT em `data/raw` e crie o indice:

```powershell
uv run --cache-dir .uv-cache python -m advogado_de_bolso.ingest
```

Construa o frontend estatico (somente na primeira vez ou apos mudar a UI):

```powershell
make frontend
```

Inicie a API servindo o build estatico do frontend:

```powershell
uv run --cache-dir .uv-cache advogado-api
```

Abra `http://127.0.0.1:8000`. Para usar somente o terminal:

```powershell
uv run --cache-dir .uv-cache advogado
```

## Conexao com um frontend

A interface de referencia em `base_frontend/` e um SPA React + Vite + TypeScript
com testes em Vitest e Testing Library. Em desenvolvimento, abra os dois
servidores em terminais paralelos:

```powershell
make dev
```

Este alvo executa `make -j2 dev-api dev-frontend`. A API sobe em :8000 e o
Vite em :5173. O Vite faz proxy de `/api/*` para `http://localhost:8000`
(ver `base_frontend/vite.config.ts`), entao o navegador fala com a API real
sem configuracao adicional de CORS.

Em producao, `make frontend` gera `base_frontend/dist/` e a API FastAPI serve
esses arquivos estaticos em :8000 (montagem `/assets` + fallback SPA para
rotas de primeira camada diferentes de `api` e `assets`).

Qualquer frontend pode substituir o incluido desde que respeite o mesmo
contrato HTTP descrito em `Endpoints`.

### Endpoints

| Metodo | Rota | Uso |
| --- | --- | --- |
| `GET` | `/api/health` | Verifica se o processo HTTP esta disponivel |
| `POST` | `/api/chat/structured` | Envia uma mensagem, cria ou continua um caso |
| `GET` | `/api/cases` | Lista os casos persistidos |
| `GET` | `/api/cases/{case_id}` | Detalhe completo de um caso (UUID) |
| `PATCH` | `/api/cases/{case_id}` | Atualiza `title`, `icon_name` ou `response_style` (UUID) |
| `DELETE` | `/api/cases/{case_id}` | Remove o caso do disco (UUID, 204) |
| `GET` | `/api/cases/{case_id}/history` | Historico de mensagens do caso (UUID) |
| `GET` | `/docs` | Documentacao OpenAPI interativa |

Primeira mensagem (cria um caso novo):

```http
POST /api/chat/structured
Content-Type: application/json

{
  "message": "Recebi um produto com defeito. O que posso fazer?",
  "response_style": "detalhado",
  "title": "Produto com defeito",
  "icon_name": "shopping_bag"
}
```

Resposta (200):

```json
{
  "session_id": "9c1b8e74-1f0d-4a1b-9b9e-2c1f7a3e8a01",
  "updated_at": "2026-06-16T18:42:11.123Z",
  "chat_history": [
    {
      "id": "user-1718563331123",
      "sender": "user",
      "text": "Recebi um produto com defeito. O que posso fazer?",
      "timestamp": 1718563331123
    }
  ],
  "step_title": "Análise inicial",
  "step_content": "Resposta completa do assistente...",
  "relevant_title": "CDC - art. 49",
  "relevant_content": "O consumidor pode desistir...",
  "deadline": null,
  "questions": ["A compra foi online ou na loja?"],
  "suggestive_text": "Posso ajudar a redigir uma reclamacao.",
  "template_letter": null,
  "quick_replies": ["Calcular prazo", "Redigir reclamacao", "Buscar na base"]
}
```

Mensagens seguintes enviam o `session_id`:

```js
const result = await fetch("http://127.0.0.1:8000/api/chat/structured", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: "Foi uma compra online.",
    session_id: sessionStorage.getItem("chat-session"),
  }),
});

if (!result.ok) {
  throw new Error(`API indisponivel: ${result.status}`);
}

const body = await result.json();
sessionStorage.setItem("chat-session", body.session_id);
renderAssistantMessage(body);
```

Resposta bloqueada pelo revisor (HTTP 422, corpo completo do envelope):

```json
{
  "session_id": "9c1b8e74-1f0d-4a1b-9b9e-2c1f7a3e8a01",
  "updated_at": "2026-06-16T18:42:11.123Z",
  "chat_history": [],
  "blocked": true,
  "blocked_message": "Nao foi possivel validar esta resposta com seguranca. Tente reformular a pergunta ou procure o PROCON, a Defensoria Publica ou um advogado de confianca."
}
```

CRUD de casos usa UUIDs:

```js
await fetch(`/api/cases/${caseId}`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ title: "Novo titulo", response_style: "simples" }),
});
// 200 -> CaseResponse atualizado
// 404 -> caso inexistente
// 422 -> UUID malformado, corpo vazio ou campo desconhecido

await fetch(`/api/cases/${caseId}`, { method: "DELETE" });
// 204 -> removido
// 404 -> caso inexistente
```

Antes de uma resposta ser entregue, um revisor independente valida o texto. Se
ele nao aprovar a resposta, o servidor descarta o rascunho e retorna o
envelope 422 acima. Para casos ja persistidos, o historico nao e alterado
quando o revisor bloqueia.

### Persistencia

Os casos sao persistidos como arquivos JSON em `./storage/cases/`, um por
caso (`{case_id}.json`). O caminho e configurado pela variavel `CASES_PATH`
(`Settings.cases_path`, alias `CASES_PATH`). O disco e a fonte da verdade:
a API nao mantem sessoes em memoria. Reiniciar o processo nao apaga as
conversas.

Restricoes de implantacao:

- **Limite de escala de casos**: o `list_all()` em `storage/cases.py` le o
  diretorio inteiro a cada chamada. O codigo foi desenhado para ate `1000`
  casos; acima disso a latencia de listagem degrada linearmente. Um
  `_index.json` ou um SQLite sao o caminho de evolucao.
- **Um unico worker**: o `ChatService` mantem um `asyncio.Lock` por caso em
  memoria. Rodar a API com `--workers > 1` (uvicorn com varios processos)
  faria com que cada worker tivesse seu proprio registro de locks, abrindo
  uma janela de condicao de corrida. Em producao use `--workers 1` ou
  substitua o lock in-process por um distribuido (Redis, etcd) antes de
  escalar para varios processos.
- **Escritas concorrentes API + CLI**: o salvamento e atomico (`os.replace`
  apos escrever em um `.tmp` unico), entao o JSON nunca fica corrompido.
  Porem, dois processos (por exemplo, a API e o CLI) que leem, modificam
  e gravam o mesmo caso ao mesmo tempo tem semantica de last-writer-wins
  para atualizacoes completas. Para coordenacao entre processos use um
  lock distribuido.

### CORS e implantacao

Quando frontend e API estiverem na mesma origem, nenhuma configuracao CORS e
necessaria. Para um frontend separado, liste apenas suas origens exatas:

```dotenv
CORS_ORIGINS=https://app.exemplo.com,https://staging.exemplo.com
```

Nao use `*` em producao. Coloque a API atras de HTTPS e de um proxy reverso,
adicione autenticacao e rate limiting antes de disponibiliza-la publicamente,
e nunca envie chaves de provedor ao navegador. Lembre-se de manter
`--workers 1` no uvicorn ate que o lock por caso seja movido para um
armazenamento compartilhado.

## Comandos Make

| Alvo | O que faz |
| --- | --- |
| `make frontend` | Instala dependencias do frontend via `npm ci` e roda `npm run build` |
| `make dev-api` | Sobe a API FastAPI com `uv run --cache-dir .uv-cache advogado-api` |
| `make dev-frontend` | Sobe o Vite dev server em :5173 com proxy para :8000 |
| `make dev` | Sobe API e frontend em paralelo (`make -j2 dev-api dev-frontend`) |

## Configuracao

| Variavel | Padrao | Descricao |
| --- | --- | --- |
| `GEMINI_API_KEY` | vazio | Chave preferida para o provedor Google |
| `GOOGLE_API_KEY` | vazio | Chave alternativa |
| `LLM_MODEL` | `gemma-4-31b-it` | Modelo enviado ao Pydantic AI |
| `LLM_PROVIDER` | `google` | Provedor usado pelo Pydantic AI |
| `THINKING_LEVEL` | `HIGH` | `HIGH`, `MEDIUM`, `LOW`, `MINIMAL` ou vazio |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Modelo local de embeddings |
| `HF_HOME` | `./storage/hf_cache` | Diretorio de cache do HuggingFace |
| `DATA_PATH` | `./data/raw` | Documentos de origem |
| `CHROMA_PATH` | `./storage/chroma` | Banco vetorial persistido |
| `COLLECTION_NAME` | `advogado_de_bolso` | Nome da colecao no Chroma |
| `CASES_PATH` | `./storage/cases` | Diretorio de casos (um JSON por caso) |
| `RETRIEVAL_TOP_K` | `5` | Trechos recuperados, entre 1 e 50 |
| `API_HOST` | `127.0.0.1` | Interface de rede do servidor |
| `API_PORT` | `8000` | Porta HTTP |
| `CORS_ORIGINS` | portas locais 3000 e 5173 | Origens externas permitidas |

Uma ingestao completa substitui a colecao anterior. Isso evita que documentos
removidos de `data/raw` continuem aparecendo em respostas futuras.

## Qualidade

Execute todos os gates antes de publicar.

Backend (Python):

```powershell
uv run --cache-dir .uv-cache pytest -q
uv run --cache-dir .uv-cache ruff check src/ tests/
uv run --cache-dir .uv-cache mypy src
```

Frontend (Node):

```powershell
cd base_frontend
npm ci
npm run test
npm run lint
npm run build
```

Os testes da API usam um servico falso injetado e, portanto, nao chamam LLM,
nao baixam modelos de embedding e nao precisam de chave real. Os testes do
frontend usam `vitest` em ambiente `jsdom` com `globalThis.fetch` stubado
(ver `base_frontend/src/test/setup.ts` e `base_frontend/src/App.test.tsx`).
