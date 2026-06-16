import {describe, expect, it} from 'vitest';

import {
  apiClient,
  deriveLastMessage,
  deriveTagText,
  formatCaseDate,
  mapCaseResponse,
  mapCaseSummary,
  mapChatMessage,
  mapDeadline,
  mapStructuredResponse,
  type WireCaseResponse,
  type WireCaseSummary,
  type WireChatMessage,
  type WireDeadlineResult,
  type WireStructuredChatResponse,
  type WireUpdateCaseRequest,
} from './api';
import type {ChatMessage} from './types';

const DEADLINE: WireDeadlineResult = {
  tipo_prazo: 'arrependimento',
  data_inicio: '2025-01-15',
  data_limite: '2025-01-22',
  dias: 7,
  base_legal: 'CDC art. 49',
  item_label: null,
  vicio_oculto: false,
  nota: 'Use a data de recebimento.',
};

const NOW_ISO = new Date().toISOString();

describe('mapDeadline', () => {
  it('maps snake_case deadline fields to camelCase Deadline', () => {
    const out = mapDeadline(DEADLINE);
    expect(out).toEqual({
      title: 'Prazo calculado',
      type: 'arrependimento',
      startDate: '2025-01-15',
      endDate: '2025-01-22',
      base: 'CDC art. 49',
      note: 'Use a data de recebimento.',
    });
  });

  it('uses item_label over tipo_prazo when present', () => {
    const out = mapDeadline({...DEADLINE, item_label: 'produto duravel'});
    expect(out.type).toBe('produto duravel');
  });
});

describe('mapChatMessage', () => {
  it('maps every snake_case nested field on an assistant message', () => {
    const wire: WireChatMessage = {
      id: 'a-1',
      sender: 'assistant',
      text: 'Body',
      timestamp: 123,
      deadline: DEADLINE,
      questions: ['Posso cancelar?'],
      step_title: 'Step',
      step_content: 'Step content',
      relevant_title: 'Fonte A',
      relevant_content: 'Conteudo A',
      suggestive_text: 'Sugestao',
      template_letter: 'Carta',
      template_letter_assunto: 'Notificacao de Desistencia',
      quick_replies: ['Sim', 'Nao'],
    };
    const out = mapChatMessage(wire);
    expect(out.id).toBe('a-1');
    expect(out.sender).toBe('assistant');
    expect(out.text).toBe('Body');
    expect(out.timestamp).toBe(123);
    expect(out.deadline).toBeTruthy();
    expect(out.deadline?.endDate).toBe('2025-01-22');
    expect(out.deadline?.base).toBe('CDC art. 49');
    expect(out.deadline?.note).toBe('Use a data de recebimento.');
    expect(out.questions).toEqual(['Posso cancelar?']);
    expect(out.stepTitle).toBe('Step');
    expect(out.stepContent).toBe('Step content');
    expect(out.relevantTitle).toBe('Fonte A');
    expect(out.relevantContent).toBe('Conteudo A');
    expect(out.suggestiveText).toBe('Sugestao');
    expect(out.templateLetter).toBe('Carta');
    expect(out.templateLetterAssunto).toBe('Notificacao de Desistencia');
    expect(out.quickReplies).toEqual(['Sim', 'Nao']);
  });

  it('omits templateLetterAssunto when the wire field is null', () => {
    const wire: WireChatMessage = {
      id: 'a-1',
      sender: 'assistant',
      text: 'Body',
      timestamp: 1,
      template_letter: 'Carta',
      template_letter_assunto: null,
    };
    const out = mapChatMessage(wire);
    expect(out.templateLetter).toBe('Carta');
    expect(out.templateLetterAssunto).toBeUndefined();
  });

  it('keeps the user message shape minimal', () => {
    const out = mapChatMessage({id: 'u-1', sender: 'user', text: 'Hi', timestamp: 1});
    expect(out).toEqual({id: 'u-1', sender: 'user', text: 'Hi', timestamp: 1});
  });
});

describe('mapStructuredResponse', () => {
  it('maps the full chat history', () => {
    const wire: WireStructuredChatResponse = {
      session_id: 'sess-1',
      updated_at: NOW_ISO,
      chat_history: [
        {id: 'u-1', sender: 'user', text: 'Hi', timestamp: 1},
        {id: 'a-1', sender: 'assistant', text: 'Hello', timestamp: 2, step_title: 'T', step_content: 'C'},
      ],
    };
    const out = mapStructuredResponse(wire);
    expect(out.sessionId).toBe('sess-1');
    expect(out.updatedAt).toBe(NOW_ISO);
    expect(out.chatHistory).toHaveLength(2);
    expect(out.chatHistory[0]?.sender).toBe('user');
    expect(out.chatHistory[1]?.stepTitle).toBe('T');
    expect(out.chatHistory[1]?.stepContent).toBe('C');
  });
});

describe('mapCaseSummary', () => {
  it('populates required fields including timestamp, date, lastMessage, iconName, responseStyle, chatHistory: []', () => {
    const wire: WireCaseSummary = {
      id: 'id-1',
      title: 'Title',
      created_at: NOW_ISO,
      updated_at: NOW_ISO,
      last_message: 'Last',
      icon_name: 'shopping_bag',
      response_style: 'simples',
      tag_text: 'Prazo calculado',
      is_demo: false,
    };
    const out = mapCaseSummary(wire);
    expect(out.id).toBe('id-1');
    expect(out.title).toBe('Title');
    expect(out.iconName).toBe('shopping_bag');
    expect(out.responseStyle).toBe('simples');
    expect(out.tagText).toBe('Prazo calculado');
    expect(out.lastMessage).toBe('Last');
    expect(out.timestamp).toBe(Date.parse(NOW_ISO));
    expect(out.chatHistory).toEqual([]);
    expect(out.date).toBeTruthy();
  });

  it('formats today as "Hoje"', () => {
    const wire: WireCaseSummary = {
      id: 'id', title: '', created_at: NOW_ISO, updated_at: NOW_ISO,
      last_message: '', icon_name: 'gavel', response_style: 'detalhado',
      tag_text: null, is_demo: false,
    };
    expect(mapCaseSummary(wire).date).toBe('Hoje');
  });
});

describe('mapCaseResponse', () => {
  it('always populates required fields and derives lastMessage/tagText from last assistant', () => {
    const wire: WireCaseResponse = {
      id: 'id-2',
      title: 'T',
      created_at: NOW_ISO,
      updated_at: NOW_ISO,
      icon_name: 'gavel',
      response_style: 'firme',
      chat_history: [
        {id: 'u-1', sender: 'user', text: 'Q', timestamp: 1},
        {id: 'a-1', sender: 'assistant', text: 'A', timestamp: 2, step_title: 'T', step_content: 'C', template_letter: 'L'},
      ],
    };
    const out = mapCaseResponse(wire);
    expect(out.id).toBe('id-2');
    expect(out.iconName).toBe('gavel');
    expect(out.responseStyle).toBe('firme');
    expect(out.timestamp).toBe(Date.parse(NOW_ISO));
    expect(out.date).toBeTruthy();
    expect(out.chatHistory).toHaveLength(2);
    expect(out.lastMessage).toBe('C');
    expect(out.tagText).toBe('Mensagem pronta');
    expect(out.is_demo).toBe(false);
  });

  it('falls back to "" lastMessage when no assistant message exists', () => {
    const wire: WireCaseResponse = {
      id: 'id-3', title: '', created_at: NOW_ISO, updated_at: NOW_ISO,
      icon_name: 'gavel', response_style: 'detalhado',
      chat_history: [{id: 'u-1', sender: 'user', text: 'Q', timestamp: 1}],
    };
    expect(mapCaseResponse(wire).lastMessage).toBe('');
  });
});

describe('formatCaseDate / deriveLastMessage / deriveTagText', () => {
  it('formatCaseDate returns "Hoje" for today', () => {
    expect(formatCaseDate(NOW_ISO)).toBe('Hoje');
  });

  it('deriveLastMessage returns last assistant stepContent or text', () => {
    const history: ChatMessage[] = [
      {id: 'u', sender: 'user', text: 'Q', timestamp: 1},
      {id: 'a', sender: 'assistant', text: 'A', timestamp: 2, stepContent: 'Step'},
    ];
    expect(deriveLastMessage(history)).toBe('Step');
  });

  it('deriveTagText returns "Prazo calculado" when deadline present, "Mensagem pronta" when templateLetter present, undefined otherwise', () => {
    const withDeadline: ChatMessage[] = [
      {id: 'a', sender: 'assistant', text: 'A', timestamp: 1, deadline: {title: 't', type: 'x', startDate: 'a', endDate: 'b', base: 'c'}},
    ];
    expect(deriveTagText(withDeadline)).toBe('Prazo calculado');
    const withTemplate: ChatMessage[] = [
      {id: 'a', sender: 'assistant', text: 'A', timestamp: 1, templateLetter: 'L'},
    ];
    expect(deriveTagText(withTemplate)).toBe('Mensagem pronta');
    const none: ChatMessage[] = [
      {id: 'a', sender: 'assistant', text: 'A', timestamp: 1},
    ];
    expect(deriveTagText(none)).toBeUndefined();
  });
});

describe('apiClient methods (PATCH contract)', () => {
  it('updateCaseMeta sends PATCH with snake_case body and maps the CaseResponse', async () => {
    const expectedPatch: WireUpdateCaseRequest = {title: 'Novo'};
    let captured: {url: string; method: string; body: string} | null = null;
    const fakeFetch = async (url: string, init?: RequestInit) => {
      captured = {url, method: init?.method || 'GET', body: init?.body as string || ''};
      return new Response(
        JSON.stringify({
          id: 'id-1', title: 'Novo', created_at: NOW_ISO, updated_at: NOW_ISO,
          icon_name: 'gavel', response_style: 'detalhado',
          chat_history: [],
        }),
        {status: 200, headers: {'Content-Type': 'application/json'}},
      );
    };
    const originalFetch = globalThis.fetch;
    (globalThis as {fetch: typeof fetch}).fetch = fakeFetch as unknown as typeof fetch;
    try {
      const out = await apiClient.updateCaseMeta('id-1', expectedPatch);
      expect(captured).not.toBeNull();
      expect(captured!.method).toBe('PATCH');
      expect(captured!.url).toBe('/api/cases/id-1');
      expect(JSON.parse(captured!.body)).toEqual({title: 'Novo'});
      expect(out.id).toBe('id-1');
      expect(out.title).toBe('Novo');
    } finally {
      (globalThis as {fetch: typeof fetch}).fetch = originalFetch;
    }
  });

  it('renameCase delegates to the same PATCH contract', async () => {
    let captured: {url: string; method: string; body: string} | null = null;
    const fakeFetch = async (url: string, init?: RequestInit) => {
      captured = {url, method: init?.method || 'GET', body: init?.body as string || ''};
      return new Response(
        JSON.stringify({
          id: 'id-1', title: 'Renamed', created_at: NOW_ISO, updated_at: NOW_ISO,
          icon_name: 'gavel', response_style: 'detalhado',
          chat_history: [],
        }),
        {status: 200, headers: {'Content-Type': 'application/json'}},
      );
    };
    const originalFetch = globalThis.fetch;
    (globalThis as {fetch: typeof fetch}).fetch = fakeFetch as unknown as typeof fetch;
    try {
      await apiClient.renameCase('id-1', 'Renamed');
      expect(captured!.method).toBe('PATCH');
      expect(captured!.url).toBe('/api/cases/id-1');
      expect(JSON.parse(captured!.body)).toEqual({title: 'Renamed'});
    } finally {
      (globalThis as {fetch: typeof fetch}).fetch = originalFetch;
    }
  });

  it('chatStructured returns the raw Response so the App can inspect the 422 envelope', async () => {
    const fakeFetch = async () => new Response('{"blocked":true}', {status: 422});
    const originalFetch = globalThis.fetch;
    (globalThis as {fetch: typeof fetch}).fetch = fakeFetch as unknown as typeof fetch;
    try {
      const response = await apiClient.chatStructured({
        message: 'Hi', session_id: null, response_style: 'simples',
      });
      expect(response).toBeInstanceOf(Response);
      expect(response.status).toBe(422);
    } finally {
      (globalThis as {fetch: typeof fetch}).fetch = originalFetch;
    }
  });
});
