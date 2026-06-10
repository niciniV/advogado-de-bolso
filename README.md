# Advogado de Bolso

Assistente de direitos do consumidor brasileiro com chat via terminal, API HTTP,
interface web responsiva e busca em uma base local de documentos.

> A aplicacao oferece informacao geral. Ela nao substitui orientacao juridica
> individualizada de advogado, Defensoria Publica, PROCON ou outro orgao competente.

## Inicio rapido

Requisitos: Python 3.11 ou superior e [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --extra dev --cache-dir .uv-cache
Copy-Item .env.example .env
```

Preencha `GEMINI_API_KEY` em `.env`. Depois, adicione arquivos PDF, HTML,
Markdown ou TXT em `data/raw` e crie o indice:

```powershell
uv run --cache-dir .uv-cache python -m advogado_de_bolso.ingest
```

Inicie a interface web e a API:

```powershell
uv run --cache-dir .uv-cache advogado-api
```

Abra `http://127.0.0.1:8000`. Para usar somente o terminal:

```powershell
uv run --cache-dir .uv-cache advogado
```

## Conexao com um frontend

A interface de referencia em `src/advogado_de_bolso/frontend` funciona sem
build ou dependencias JavaScript. Ela demonstra estados de carregamento e erro,
acessibilidade, sessao e comportamento responsivo. Qualquer frontend pode
substitui-la usando o mesmo contrato HTTP.

### Endpoints

| Metodo | Rota | Uso |
| --- | --- | --- |
| `GET` | `/api/health` | Verifica se o processo HTTP esta disponivel |
| `POST` | `/api/chat` | Envia uma mensagem e continua ou cria uma sessao |
| `DELETE` | `/api/sessions/{session_id}` | Remove o historico da sessao |
| `GET` | `/docs` | Documentacao OpenAPI interativa |

Primeira mensagem:

```http
POST /api/chat
Content-Type: application/json

{"message":"Recebi um produto com defeito. O que posso fazer?"}
```

Resposta:

```json
{
  "session_id": "identificador-opaco",
  "response": "Resposta do assistente..."
}
```

Envie o `session_id` nas mensagens seguintes:

```js
const result = await fetch("http://127.0.0.1:8000/api/chat", {
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
renderAssistantMessage(body.response);
```

O servidor mantem sessoes apenas em memoria, limita o tamanho do historico e
serializa requisicoes concorrentes da mesma sessao. Reiniciar o processo apaga
as conversas. O frontend incluido guarda somente o identificador opaco em
`sessionStorage`; nao persiste mensagens.

Antes de uma resposta ser entregue, um revisor independente valida o texto. Se
ele nao aprovar a resposta, o servidor descarta o rascunho e retorna uma
orientacao segura em vez de expor conteudo juridico nao validado.

### CORS e implantacao

Quando frontend e API estiverem na mesma origem, nenhuma configuracao CORS e
necessaria. Para um frontend separado, liste apenas suas origens exatas:

```dotenv
CORS_ORIGINS=https://app.exemplo.com,https://staging.exemplo.com
```

Nao use `*` em producao. Coloque a API atras de HTTPS e de um proxy reverso,
adicione autenticacao e rate limiting antes de disponibiliza-la publicamente,
e nunca envie chaves de provedor ao navegador. Para escalar para varios
processos, substitua as sessoes em memoria por um armazenamento compartilhado
com expiracao, como Redis.

### Recomendacoes para uma interface responsiva

- Comece em uma coluna para celular e aumente para duas areas somente quando
  houver largura suficiente; nao comprima o chat ao lado de textos longos.
- Mantenha o campo de mensagem e o botao de envio acessiveis, com foco visivel,
  labels reais e estados desabilitados durante requisicoes.
- Mostre claramente estados vazio, carregando, erro e reconexao. Nunca descarte
  silenciosamente a mensagem do usuario.
- Preserve quebras de linha, use largura de leitura confortavel e permita zoom.
- Guarde dados sensiveis pelo menor tempo possivel e ofereca uma acao clara de
  nova conversa que tambem remova a sessao no servidor.
- Teste larguras de `320px`, `768px` e desktop, navegacao por teclado,
  `prefers-reduced-motion`, conexao lenta e respostas extensas.

## Configuracao

| Variavel | Padrao | Descricao |
| --- | --- | --- |
| `GEMINI_API_KEY` | vazio | Chave preferida para o provedor Google |
| `GOOGLE_API_KEY` | vazio | Chave alternativa |
| `LLM_MODEL` | `gemma-4-31b-it` | Modelo enviado ao Pydantic AI |
| `THINKING_LEVEL` | `HIGH` | `HIGH`, `MEDIUM`, `LOW`, `MINIMAL` ou vazio |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Modelo local de embeddings |
| `DATA_PATH` | `./data/raw` | Documentos de origem |
| `CHROMA_PATH` | `./storage/chroma` | Banco vetorial persistido |
| `RETRIEVAL_TOP_K` | `5` | Trechos recuperados, entre 1 e 50 |
| `API_HOST` | `127.0.0.1` | Interface de rede do servidor |
| `API_PORT` | `8000` | Porta HTTP |
| `CORS_ORIGINS` | portas locais 3000 e 5173 | Origens externas permitidas |

Uma ingestao completa substitui a colecao anterior. Isso evita que documentos
removidos de `data/raw` continuem aparecendo em respostas futuras.

## Qualidade

Execute todos os gates antes de publicar:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
uv build --cache-dir .uv-cache
```

Os testes da API usam um servico falso injetado e, portanto, nao chamam LLM,
nao baixam modelos de embedding e nao precisam de chave real.
