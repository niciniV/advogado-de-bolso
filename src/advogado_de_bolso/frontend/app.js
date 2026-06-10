const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const messages = document.querySelector("#messages");
const sendButton = document.querySelector("#send-button");
const resetButton = document.querySelector("#reset-session");
const statusBadge = document.querySelector("#connection-status");
const sessionKey = "advogado-de-bolso-session";
let activeRequest = null;
let conversationGeneration = 0;

function setStatus(label, state) {
  statusBadge.textContent = label;
  statusBadge.dataset.state = state;
}

function addMessage(role, content, isError = false) {
  const article = document.createElement("article");
  article.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;
  if (isError) article.classList.add("error-message");

  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "Voce" : "Assistente";

  const paragraph = document.createElement("p");
  paragraph.textContent = content;
  article.append(label, paragraph);
  messages.append(article);
  article.scrollIntoView({ behavior: "smooth", block: "end" });
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("API indisponivel");
    setStatus("API conectada", "ready");
  } catch {
    setStatus("API indisponivel", "error");
  }
}

async function sendMessage(message, signal) {
  const sessionId = sessionStorage.getItem(sessionKey);
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Nao foi possivel obter uma resposta.");
  }

  return response.json();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message || sendButton.disabled) return;

  addMessage("user", message);
  input.value = "";
  input.disabled = true;
  sendButton.disabled = true;
  sendButton.textContent = "Analisando...";
  const generation = conversationGeneration;
  activeRequest = new AbortController();

  try {
    const body = await sendMessage(message, activeRequest.signal);
    if (generation !== conversationGeneration) return;
    sessionStorage.setItem(sessionKey, body.session_id);
    addMessage("assistant", body.response);
    setStatus("API conectada", "ready");
  } catch (error) {
    if (error.name === "AbortError") return;
    addMessage("assistant", error.message, true);
    setStatus("Falha na API", "error");
  } finally {
    activeRequest = null;
    input.disabled = false;
    sendButton.disabled = false;
    sendButton.textContent = "Enviar pergunta";
    input.focus();
  }
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

resetButton.addEventListener("click", async () => {
  conversationGeneration += 1;
  activeRequest?.abort();
  const sessionId = sessionStorage.getItem(sessionKey);
  sessionStorage.removeItem(sessionKey);
  resetButton.disabled = true;
  let resetError = null;
  if (sessionId) {
    try {
      const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Nao foi possivel limpar a conversa anterior.");
    } catch (error) {
      resetError = error.message;
      setStatus("Falha ao limpar sessao", "error");
    }
  }
  messages.replaceChildren();
  addMessage("assistant", "Nova conversa iniciada. Qual problema voce precisa resolver?");
  if (resetError) addMessage("assistant", resetError, true);
  resetButton.disabled = false;
  input.focus();
});

checkHealth();
