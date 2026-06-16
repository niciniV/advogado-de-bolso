import type {
  Case,
  ChatMessage,
  Deadline,
} from './types';

export interface WireDeadlineResult {
  tipo_prazo: 'reclamacao_vicio' | 'arrependimento';
  data_inicio: string;
  data_limite: string;
  dias: number;
  base_legal: string;
  item_label: string | null;
  vicio_oculto: boolean;
  nota: string;
}

export interface WireChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: number;
  deadline?: WireDeadlineResult | null;
  questions?: string[] | null;
  step_title?: string | null;
  step_content?: string | null;
  relevant_title?: string | null;
  relevant_content?: string | null;
  suggestive_text?: string | null;
  template_letter?: string | null;
  quick_replies?: string[] | null;
}

export interface WireStructuredChatResponse {
  session_id: string;
  updated_at: string;
  chat_history: WireChatMessage[];
  step_title?: string | null;
  step_content?: string | null;
  relevant_title?: string | null;
  relevant_content?: string | null;
  deadline?: WireDeadlineResult | null;
  questions?: string[] | null;
  suggestive_text?: string | null;
  template_letter?: string | null;
  quick_replies?: string[] | null;
  blocked?: boolean;
  blocked_message?: string | null;
}

export interface WireCaseSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message: string;
  icon_name: 'shopping_bag' | 'receipt_long' | 'local_shipping' | 'gavel';
  response_style: 'simples' | 'detalhado' | 'firme';
  tag_text?: string | null;
  is_demo: boolean;
}

export interface WireCaseResponse {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  icon_name: 'shopping_bag' | 'receipt_long' | 'local_shipping' | 'gavel';
  response_style: 'simples' | 'detalhado' | 'firme';
  chat_history: WireChatMessage[];
}

export interface WireStructuredChatRequest {
  message: string;
  session_id: string | null;
  response_style?: 'simples' | 'detalhado' | 'firme' | null;
  title?: string | null;
  icon_name?: 'shopping_bag' | 'receipt_long' | 'local_shipping' | 'gavel' | null;
}

export interface WireUpdateCaseRequest {
  title?: string;
  icon_name?: 'shopping_bag' | 'receipt_long' | 'local_shipping' | 'gavel';
  response_style?: 'simples' | 'detalhado' | 'firme';
}

const MONTHS_PT = [
  'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
  'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez',
];

export function formatCaseDate(updatedAt: string): string {
  const ts = Date.parse(updatedAt);
  if (Number.isNaN(ts)) return '';
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const target = new Date(ts);
  const targetDay = new Date(target.getFullYear(), target.getMonth(), target.getDate()).getTime();
  const oneDay = 24 * 60 * 60 * 1000;
  if (targetDay === today) return 'Hoje';
  if (targetDay === today - oneDay) return 'Ontem';
  return `${String(target.getDate()).padStart(2, '0')} ${MONTHS_PT[target.getMonth()]}`;
}

export function deriveLastMessage(chatHistory: ChatMessage[]): string {
  for (let i = chatHistory.length - 1; i >= 0; i -= 1) {
    const m = chatHistory[i];
    if (m && m.sender === 'assistant') {
      return (m.stepContent && m.stepContent.trim()) || m.text || '';
    }
  }
  return '';
}

export function deriveTagText(chatHistory: ChatMessage[]): string | undefined {
  for (let i = chatHistory.length - 1; i >= 0; i -= 1) {
    const m = chatHistory[i];
    if (m && m.sender === 'assistant') {
      if (m.deadline) return 'Prazo calculado';
      if (m.templateLetter) return 'Mensagem pronta';
      return undefined;
    }
  }
  return undefined;
}

export function mapDeadline(payload: WireDeadlineResult): Deadline {
  return {
    title: 'Prazo calculado',
    type: payload.item_label || payload.tipo_prazo,
    startDate: payload.data_inicio,
    endDate: payload.data_limite,
    base: payload.base_legal,
    note: payload.nota,
  };
}

export function mapChatMessage(payload: WireChatMessage): ChatMessage {
  const msg: ChatMessage = {
    id: payload.id,
    sender: payload.sender,
    text: payload.text,
    timestamp: payload.timestamp,
  };
  if (payload.deadline) msg.deadline = mapDeadline(payload.deadline);
  if (payload.questions) msg.questions = payload.questions;
  if (payload.step_title != null) msg.stepTitle = payload.step_title;
  if (payload.step_content != null) msg.stepContent = payload.step_content;
  if (payload.relevant_title != null) msg.relevantTitle = payload.relevant_title;
  if (payload.relevant_content != null) msg.relevantContent = payload.relevant_content;
  if (payload.suggestive_text != null) msg.suggestiveText = payload.suggestive_text;
  if (payload.template_letter != null) msg.templateLetter = payload.template_letter;
  if (payload.quick_replies) msg.quickReplies = payload.quick_replies;
  return msg;
}

export interface MappedStructuredResponse {
  sessionId: string;
  updatedAt: string;
  chatHistory: ChatMessage[];
}

export function mapStructuredResponse(payload: WireStructuredChatResponse): MappedStructuredResponse {
  return {
    sessionId: payload.session_id,
    updatedAt: payload.updated_at,
    chatHistory: (payload.chat_history || []).map(mapChatMessage),
  };
}

export function mapCaseSummary(payload: WireCaseSummary): Case {
  return {
    id: payload.id,
    title: payload.title,
    date: formatCaseDate(payload.updated_at),
    lastMessage: payload.last_message || '',
    tagText: payload.tag_text || undefined,
    iconName: payload.icon_name,
    timestamp: Date.parse(payload.updated_at),
    responseStyle: payload.response_style,
    is_demo: payload.is_demo,
    chatHistory: [],
  };
}

export function mapCaseResponse(payload: WireCaseResponse): Case {
  const chatHistory = (payload.chat_history || []).map(mapChatMessage);
  return {
    id: payload.id,
    title: payload.title,
    date: formatCaseDate(payload.updated_at),
    lastMessage: deriveLastMessage(chatHistory),
    tagText: deriveTagText(chatHistory),
    iconName: payload.icon_name,
    timestamp: Date.parse(payload.updated_at),
    responseStyle: payload.response_style,
    is_demo: false,
    chatHistory,
  };
}

async function throwOnError<T>(response: Response, parser: (r: Response) => Promise<T>): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status} ${response.statusText}: ${text.slice(0, 200)}`);
  }
  return parser(response);
}

export const apiClient = {
  async chatStructured(payload: WireStructuredChatRequest): Promise<Response> {
    return fetch('/api/chat/structured', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
  },

  async listCases(): Promise<Case[]> {
    const response = await fetch('/api/cases', {method: 'GET'});
    return throwOnError(response, async (r) => {
      const data: WireCaseSummary[] = await r.json();
      return data.map(mapCaseSummary);
    });
  },

  async getCase(caseId: string): Promise<Case> {
    const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}`, {method: 'GET'});
    return throwOnError(response, async (r) => {
      const data: WireCaseResponse = await r.json();
      return mapCaseResponse(data);
    });
  },

  async updateCaseMeta(caseId: string, patch: WireUpdateCaseRequest): Promise<Case> {
    const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(patch),
    });
    return throwOnError(response, async (r) => {
      const data: WireCaseResponse = await r.json();
      return mapCaseResponse(data);
    });
  },

  async renameCase(caseId: string, newTitle: string): Promise<Case> {
    return apiClient.updateCaseMeta(caseId, {title: newTitle});
  },

  async deleteCase(caseId: string): Promise<void> {
    const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`HTTP ${response.status} ${response.statusText}: ${text.slice(0, 200)}`);
    }
  },

  async getHistory(caseId: string): Promise<ChatMessage[]> {
    const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}/history`, {
      method: 'GET',
    });
    return throwOnError(response, async (r) => {
      const data: WireChatMessage[] = await r.json();
      return data.map(mapChatMessage);
    });
  },
};
