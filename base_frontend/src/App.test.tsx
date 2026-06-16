import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import { seedCases } from './defaults';
import type { WireChatMessage, WireCaseResponse, WireCaseSummary, WireStructuredChatResponse } from './api';

type FetchCall = {
  url: string;
  method: string;
  body?: Record<string, unknown>;
};

const REAL_ID = '11111111-1111-4111-8111-111111111111';
const REAL_ID_2 = '22222222-2222-4222-8222-222222222222';
const BLOCKED_ID = '33333333-3333-4333-8333-333333333333';
const UPDATED_AT = new Date().toISOString();

function jsonResponse<T>(body: T, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {'Content-Type': 'application/json'},
  });
}

function assistantMessage(text: string, extra: Partial<WireChatMessage> = {}): WireChatMessage {
  return {
    id: `assistant-${Math.random().toString(36).slice(2, 8)}`,
    sender: 'assistant',
    text,
    timestamp: Date.now(),
    step_title: 'Análise inicial',
    step_content: text,
    quick_replies: ['Continuar orientação'],
    ...extra,
  };
}

function userMessage(text: string): WireChatMessage {
  return {
    id: `user-${Math.random().toString(36).slice(2, 8)}`,
    sender: 'user',
    text,
    timestamp: Date.now(),
  };
}

function chatStructuredResponse(
  sessionId: string,
  history: WireChatMessage[],
  extra: Partial<WireStructuredChatResponse> = {},
): Response {
  return jsonResponse<WireStructuredChatResponse>({
    session_id: sessionId,
    updated_at: UPDATED_AT,
    chat_history: history,
    ...extra,
  });
}

function blockedResponse(
  sessionId: string,
  blockedMessage: string,
  history: WireChatMessage[] = [],
): Response {
  return jsonResponse<WireStructuredChatResponse>({
    session_id: sessionId,
    updated_at: UPDATED_AT,
    chat_history: history,
    blocked: true,
    blocked_message: blockedMessage,
  }, 422);
}

function caseSummary(
  id: string,
  title: string,
  lastMessage = 'Resposta do caso.',
  tagText: string | null = null,
  icon: WireCaseSummary['icon_name'] = 'gavel',
): WireCaseSummary {
  return {
    id,
    title,
    created_at: UPDATED_AT,
    updated_at: UPDATED_AT,
    last_message: lastMessage,
    icon_name: icon,
    response_style: 'detalhado',
    tag_text: tagText,
    is_demo: false,
  };
}

function caseResponse(
  id: string,
  title: string,
  history: WireChatMessage[] = [
    userMessage('Pergunta do caso.'),
    assistantMessage('Resposta do caso.'),
  ],
): WireCaseResponse {
  return {
    id,
    title,
    created_at: UPDATED_AT,
    updated_at: UPDATED_AT,
    icon_name: 'gavel',
    response_style: 'detalhado',
    chat_history: history,
  };
}

function seedCaseSummaries(): WireCaseSummary[] {
  return seedCases.map((c) => ({
    id: c.id,
    title: c.title,
    created_at: new Date(c.timestamp).toISOString(),
    updated_at: new Date(c.timestamp).toISOString(),
    last_message: c.lastMessage,
    icon_name: c.iconName,
    response_style: c.responseStyle,
    tag_text: c.tagText || null,
    is_demo: true,
  }));
}

function setupFetch(handler: (calls: FetchCall[]) => Promise<Response>) {
  const originalFetch = globalThis.fetch;
  const calls: FetchCall[] = [];
  const fakeFetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const rawUrl = url instanceof Request ? url.url : String(url);
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined;
    calls.push({url: rawUrl, method: init?.method || 'GET', body});
    return handler(calls);
  }) as unknown as typeof fetch;

  globalThis.fetch = fakeFetch;

  return {
    calls,
    restore: () => {
      globalThis.fetch = originalFetch;
    },
  };
}

function renderApp(handler: (calls: FetchCall[]) => Promise<Response>) {
  const fetchState = setupFetch(handler);
  render(<App />);
  return fetchState;
}

function clickSendButton() {
  const sendButton = document.getElementById('send-button-click');
  expect(sendButton).not.toBeNull();
  fireEvent.click(sendButton as HTMLElement);
}

async function sendChatMessage(text: string) {
  const input = (await screen.findByPlaceholderText(
    'Digite sua duvida ou responda ao advogado...',
  )) as HTMLInputElement;
  fireEvent.change(input, {target: {value: text}});
  clickSendButton();
}

function clickTab(name: RegExp) {
  fireEvent.click(screen.getAllByRole('button', {name})[0]);
}

function clickHomeTab() {
  clickTab(/inicio/i);
}

function clickConversarTab() {
  clickTab(/conversar/i);
}

function clickCasesTab() {
  clickTab(/meus casos/i);
}

function openCaseMenu(caseTitle: string) {
  const card = screen.getByText(caseTitle).closest('[id^="case-card-"]');
  expect(card).not.toBeNull();
  const menuButton = card?.querySelector('[title="Menu de ações"]') as HTMLElement;
  fireEvent.click(menuButton);
}

function selectDemoCase(title: string) {
  fireEvent.click(screen.getByText(title));
}

function selectRealCase(title: string) {
  fireEvent.click(screen.getByText(title));
}

afterEach(() => {
  cleanup();
});

describe('App frontend integration', () => {
  it('starts with no demo cases when the real cases endpoint returns an empty list', async () => {
    const {calls, restore} = renderApp(async () => jsonResponse<WireCaseSummary[]>([]));

    try {
      clickConversarTab();
      await screen.findByText('Inicie sua Consulta de Consumo');
      expect(screen.queryByText('Celular com defeito')).not.toBeInTheDocument();
      expect(calls).toEqual([
        {url: '/api/cases', method: 'GET'},
      ]);
    } finally {
      restore();
    }
  });

  it('selecting, renaming, and deleting a demo case makes no API request', async () => {
    const {calls, restore} = renderApp(async () => jsonResponse<WireCaseSummary[]>([]));

    try {
      await screen.findByText('Celular com defeito');
      selectDemoCase('Celular com defeito');
      await waitFor(() => expect(screen.getByText('Comprei um celular com defeito na tela. O que faco?')).toBeInTheDocument());

      clickCasesTab();
      await screen.findByText('Celular com defeito');
      openCaseMenu('Celular com defeito');
      fireEvent.click(screen.getByText('Renomear'));

      const renameInput = screen.getByPlaceholderText('Ex: Celular comprando online...') as HTMLInputElement;
      fireEvent.change(renameInput, {target: {value: 'Demo renomeado'}});
      fireEvent.click(screen.getByText('Salvar Alteração'));
      await waitFor(() => expect(screen.getByText('Demo renomeado')).toBeInTheDocument());
      await waitFor(() => expect(screen.getByText('Consulta renomeada com sucesso!')).toBeInTheDocument());

      openCaseMenu('Demo renomeado');
      fireEvent.click(screen.getByText('Excluir consulta'));
      fireEvent.click(screen.getByText('Sim, Excluir'));
      await waitFor(() => expect(screen.getByText('Consulta excluida com sucesso.')).toBeInTheDocument());

      expect(calls).toEqual([
        {url: '/api/cases', method: 'GET'},
      ]);
    } finally {
      restore();
    }
  });

  it('sending while a demo is active posts session_id null and removes demos after the real response', async () => {
    const {calls, restore} = renderApp(async (allCalls) => {
      const call = allCalls[allCalls.length - 1];
      if (call.url === '/api/cases') return jsonResponse(seedCaseSummaries());
      if (call.url === '/api/chat/structured') {
        expect(call.body).toEqual({
          message: 'Comprei um celular com defeito.',
          session_id: null,
          response_style: 'detalhado',
          title: 'Celular comprado online',
          icon_name: 'shopping_bag',
        });
        return chatStructuredResponse(REAL_ID, [
          userMessage('Comprei um celular com defeito.'),
          assistantMessage('Voce pode exigir o conserto ou a troca do produto.'),
        ]);
      }
      return jsonResponse({error: 'unexpected'}, 500);
    });

    try {
      await screen.findByText('Celular com defeito');
      selectDemoCase('Celular com defeito');
      await sendChatMessage('Comprei um celular com defeito.');

      await waitFor(() => expect(calls.some((c) => c.url === '/api/chat/structured')).toBe(true));
      await waitFor(() => expect(screen.getByText('Voce pode exigir o conserto ou a troca do produto.')).toBeInTheDocument());

      clickCasesTab();
      await waitFor(() => expect(screen.getByText('Celular comprado online')).toBeInTheDocument());
      expect(screen.queryByText('Celular com defeito')).not.toBeInTheDocument();
      expect(screen.queryByText('Arrependimento de compra online')).not.toBeInTheDocument();
      expect(screen.queryByText('Cobranca indevida')).not.toBeInTheDocument();
    } finally {
      restore();
    }
  });

  it('a successful first message synthesizes a real case from request metadata without fetching the case by id', async () => {
    const {calls, restore} = renderApp(async (allCalls) => {
      const call = allCalls[allCalls.length - 1];
      if (call.url === '/api/cases') return jsonResponse<WireCaseSummary[]>([]);
      if (call.url === '/api/chat/structured') {
        expect(call.body).toEqual({
          message: 'Fui cobrado duas vezes pelo mesmo produto.',
          session_id: null,
          response_style: 'detalhado',
          title: 'Cobranca indevida',
          icon_name: 'receipt_long',
        });
        return chatStructuredResponse(REAL_ID, [
          userMessage('Fui cobrado duas vezes pelo mesmo produto.'),
          assistantMessage('Voce pode pedir a restituicao em dobro do valor cobrado indevidamente.', {
            deadline: {
              tipo_prazo: 'reclamacao_vicio',
              data_inicio: '2026-06-01',
              data_limite: '2026-06-08',
              dias: 7,
              base_legal: 'CDC art. 42',
              item_label: null,
              vicio_oculto: false,
              nota: 'Guarde o comprovante.',
            },
          }),
        ]);
      }
      return jsonResponse({error: 'unexpected'}, 500);
    });

    try {
      clickConversarTab();
      await screen.findByText('Inicie sua Consulta de Consumo');
      await sendChatMessage('Fui cobrado duas vezes pelo mesmo produto.');

      await waitFor(() => expect(calls.some((c) => c.url === '/api/chat/structured')).toBe(true));
      await waitFor(() => expect(screen.getByText('Voce pode pedir a restituicao em dobro do valor cobrado indevidamente.')).toBeInTheDocument());

      clickCasesTab();
      await waitFor(() => expect(screen.getByText('Cobranca indevida')).toBeInTheDocument());
      expect(screen.getByText('Prazo estimado ativo')).toBeInTheDocument();
      expect(calls.some((c) => /^\/api\/cases\/[^/]+$/.test(c.url))).toBe(false);
    } finally {
      restore();
    }
  });

  it('a blocked first message renders blocked_message and the next send reuses the returned session id and original metadata', async () => {
    const {calls, restore} = renderApp(async (allCalls) => {
      const call = allCalls[allCalls.length - 1];
      if (call.url === '/api/cases') return jsonResponse<WireCaseSummary[]>([]);
      if (call.url === '/api/chat/structured') {
        if (calls.length === 2) {
          return blockedResponse(
            BLOCKED_ID,
            'Precisamos reformular a pergunta para continuar.',
            [userMessage('Comprei um celular online e me arrependi.')],
          );
        }
        expect(call.body).toEqual({
          message: 'Tenho mais detalhes sobre o recebimento.',
          session_id: BLOCKED_ID,
          response_style: 'detalhado',
          title: 'Celular comprado online',
          icon_name: 'shopping_bag',
        });
        return chatStructuredResponse(BLOCKED_ID, [
          userMessage('Comprei um celular online e me arrependi.'),
          assistantMessage('Precisamos reformular a pergunta para continuar.'),
          userMessage('Tenho mais detalhes sobre o recebimento.'),
          assistantMessage('Informe a data exata do recebimento.'),
        ]);
      }
      return jsonResponse({error: 'unexpected'}, 500);
    });

    try {
      clickConversarTab();
      await screen.findByText('Inicie sua Consulta de Consumo');
      await sendChatMessage('Comprei um celular online e me arrependi.');

      await waitFor(() => expect(calls.some((c) => c.url === '/api/chat/structured' && c.method === 'POST')).toBe(true));
      await waitFor(() => expect(screen.getByText('Precisamos reformular a pergunta para continuar.')).toBeInTheDocument());

      await sendChatMessage('Tenho mais detalhes sobre o recebimento.');

      await waitFor(() => expect(calls.filter((c) => c.url === '/api/chat/structured').length).toBe(2));
      await waitFor(() => expect(screen.getByText('Informe a data exata do recebimento.')).toBeInTheDocument());
    } finally {
      restore();
    }
  });

  it('starting a new consultation or selecting another case clears a pending blocked retry', async () => {
    const {calls, restore} = renderApp(async (allCalls) => {
      const call = allCalls[allCalls.length - 1];
      if (call.url === '/api/cases') return jsonResponse<WireCaseSummary[]>([]);
      if (call.url === `/api/cases/${REAL_ID}` && call.method === 'GET') {
        return jsonResponse(caseResponse(REAL_ID, 'Atraso na entrega', [
          userMessage('Minha compra online está com a entrega muito atrasada.'),
          assistantMessage('Voce pode exigir cumprimento forcado ou cancelar o pedido.'),
        ]));
      }
      if (call.url === '/api/chat/structured') {
        if (calls.length === 2) {
          return blockedResponse(
            BLOCKED_ID,
            'Precisamos reformular a pergunta para continuar.',
            [userMessage('Comprei um celular online e me arrependi.')],
          );
        }
        if (call.body?.message === 'Minha compra online está com a entrega muito atrasada.') {
          expect(call.body).toEqual({
            message: 'Minha compra online está com a entrega muito atrasada.',
            session_id: null,
            response_style: 'detalhado',
            title: 'Atraso na entrega',
            icon_name: 'local_shipping',
          });
          return chatStructuredResponse(REAL_ID, [
            userMessage('Minha compra online está com a entrega muito atrasada.'),
            assistantMessage('Voce pode exigir cumprimento forcado ou cancelar o pedido.'),
          ]);
        }
        if (call.body?.message === 'Comprei um celular com defeito.') {
          return blockedResponse(
            REAL_ID_2,
            'Ainda precisamos de mais dados.',
            [userMessage('Comprei um celular com defeito.')],
          );
        }
        expect(call.body).toEqual({
          message: 'O prazo continua igual?',
          session_id: REAL_ID,
          response_style: 'detalhado',
        });
        return chatStructuredResponse(REAL_ID, [
          userMessage('Minha compra online está com a entrega muito atrasada.'),
          assistantMessage('Voce pode exigir cumprimento forcado ou cancelar o pedido.'),
          userMessage('O prazo continua igual?'),
          assistantMessage('Sim, conte a partir do recebimento.'),
        ]);
      }
      return jsonResponse({error: 'unexpected'}, 500);
    });

    try {
      clickConversarTab();
      await screen.findByText('Inicie sua Consulta de Consumo');
      await sendChatMessage('Comprei um celular online e me arrependi.');
      await waitFor(() => expect(screen.getByText('Precisamos reformular a pergunta para continuar.')).toBeInTheDocument());

      clickHomeTab();
      fireEvent.click(screen.getByRole('button', {name: 'Nova Consulta Inteligente'}));
      await sendChatMessage('Minha compra online está com a entrega muito atrasada.');
      await waitFor(() => expect(calls.some((c) => c.body?.message === 'Minha compra online está com a entrega muito atrasada.' && c.body?.session_id === null)).toBe(true));

      clickHomeTab();
      fireEvent.click(screen.getByRole('button', {name: 'Nova Consulta Inteligente'}));
      await sendChatMessage('Comprei um celular com defeito.');
      await waitFor(() => expect(screen.getByText('Ainda precisamos de mais dados.')).toBeInTheDocument());

      clickCasesTab();
      await waitFor(() => expect(screen.getByText('Atraso na entrega')).toBeInTheDocument());
      selectRealCase('Atraso na entrega');
      await waitFor(() => expect(calls.some((c) => c.url === `/api/cases/${REAL_ID}` && c.method === 'GET')).toBe(true));

      await sendChatMessage('O prazo continua igual?');
      await waitFor(() => expect(calls.some((c) => c.body?.message === 'O prazo continua igual?' && c.body?.session_id === REAL_ID)).toBe(true));
      expect(calls.some((c) => c.body?.session_id === BLOCKED_ID && c.body?.message === 'O prazo continua igual?')).toBe(false);
    } finally {
      restore();
    }
  });

  it('starting a quick-guide consultation while a real case is active creates a new session without mutating the active case', async () => {
    const {calls, restore} = renderApp(async (allCalls) => {
      const call = allCalls[allCalls.length - 1];
      if (call.url === '/api/cases') return jsonResponse<WireCaseSummary[]>([]);
      if (call.url === '/api/chat/structured') {
        if (calls.length === 2) {
          expect(call.body).toEqual({
            message: 'Fui cobrado duas vezes pelo mesmo produto.',
            session_id: null,
            response_style: 'detalhado',
            title: 'Cobranca indevida',
            icon_name: 'receipt_long',
          });
          return chatStructuredResponse(REAL_ID, [
            userMessage('Fui cobrado duas vezes pelo mesmo produto.'),
            assistantMessage('Resposta do primeiro caso.'),
          ]);
        }
        expect(call.body).toEqual({
          message: 'Comprei um celular online e me arrependi. Recebi ontem, mas a loja disse que não aceita devolução.',
          session_id: null,
          response_style: 'detalhado',
          title: 'Celular comprado online',
          icon_name: 'shopping_bag',
        });
        return chatStructuredResponse(REAL_ID_2, [
          userMessage('Comprei um celular online e me arrependi. Recebi ontem, mas a loja disse que não aceita devolução.'),
          assistantMessage('Resposta do guia.'),
        ]);
      }
      return jsonResponse({error: 'unexpected'}, 500);
    });

    try {
      clickConversarTab();
      await screen.findByText('Inicie sua Consulta de Consumo');
      await sendChatMessage('Fui cobrado duas vezes pelo mesmo produto.');
      await waitFor(() => expect(calls.some((c) => c.body?.message === 'Fui cobrado duas vezes pelo mesmo produto.')).toBe(true));

      clickHomeTab();
      const quickGuideButton = await screen.findByRole('button', {name: /Celular comprado online de que me arrependi/});
      fireEvent.click(quickGuideButton);
      await waitFor(() => expect(calls.some((c) => c.body?.message === 'Comprei um celular online e me arrependi. Recebi ontem, mas a loja disse que não aceita devolução.')).toBe(true));

      expect(calls.some((c) => c.method === 'PATCH')).toBe(false);
      expect(calls.some((c) => /^\/api\/cases\/[^/]+$/.test(c.url))).toBe(false);

      clickCasesTab();
      await waitFor(() => expect(screen.getByText('Cobranca indevida')).toBeInTheDocument());
      await waitFor(() => expect(screen.getByText('Celular comprado online')).toBeInTheDocument());
      expect(screen.getByText('Resposta do primeiro caso.')).toBeInTheDocument();
    } finally {
      restore();
    }
  });

  it('selecting, renaming, and deleting a real case calls the expected UUID endpoints', async () => {
    const summary = caseSummary(REAL_ID, 'Cobranca indevida', 'Resposta inicial.', 'Prazo calculado', 'receipt_long');
    const {calls, restore} = renderApp(async (allCalls) => {
      const call = allCalls[allCalls.length - 1];
      if (call.url === '/api/cases') return jsonResponse([summary]);
      if (call.url === `/api/cases/${REAL_ID}` && call.method === 'GET') {
        return jsonResponse(caseResponse(REAL_ID, 'Cobranca indevida', [
          userMessage('Fui cobrado duas vezes.'),
          assistantMessage('Resposta inicial.'),
        ]));
      }
      if (call.url === `/api/cases/${REAL_ID}` && call.method === 'PATCH') {
        expect(call.body).toEqual({title: 'Cobranca renomeada'});
        return jsonResponse(caseResponse(REAL_ID, 'Cobranca renomeada', [
          userMessage('Fui cobrado duas vezes.'),
          assistantMessage('Resposta inicial.'),
        ]));
      }
      if (call.url === `/api/cases/${REAL_ID}` && call.method === 'DELETE') {
        return jsonResponse({}, 200);
      }
      return jsonResponse({error: 'unexpected'}, 500);
    });

    try {
      await screen.findByText('Cobranca indevida');
      selectRealCase('Cobranca indevida');
      await waitFor(() => expect(calls.some((c) => c.url === `/api/cases/${REAL_ID}` && c.method === 'GET')).toBe(true));

      clickCasesTab();
      await screen.findByText('Cobranca indevida');
      openCaseMenu('Cobranca indevida');
      fireEvent.click(screen.getByText('Renomear'));
      const renameInput = screen.getByPlaceholderText('Ex: Celular comprando online...') as HTMLInputElement;
      fireEvent.change(renameInput, {target: {value: 'Cobranca renomeada'}});
      fireEvent.click(screen.getByText('Salvar Alteração'));
      await waitFor(() => expect(calls.some((c) => c.url === `/api/cases/${REAL_ID}` && c.method === 'PATCH')).toBe(true));
      await waitFor(() => expect(screen.getByText('Cobranca renomeada')).toBeInTheDocument());

      openCaseMenu('Cobranca renomeada');
      fireEvent.click(screen.getByText('Excluir consulta'));
      fireEvent.click(screen.getByText('Sim, Excluir'));
      await waitFor(() => expect(calls.some((c) => c.url === `/api/cases/${REAL_ID}` && c.method === 'DELETE')).toBe(true));
      await waitFor(() => expect(screen.getByText('Consulta excluida com sucesso.')).toBeInTheDocument());
    } finally {
      restore();
    }
  });
});
