export interface Deadline {
  title: string;
  type: string;
  startDate: string;
  endDate: string;
  base: string;
  note?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: number;
  deadline?: Deadline;
  questions?: string[];
  stepTitle?: string;
  stepContent?: string;
  relevantTitle?: string;
  relevantContent?: string;
  suggestiveText?: string;
  templateLetter?: string;
  templateLetterAssunto?: string;
  quickReplies?: string[];
}

export interface Case {
  id: string;
  title: string;
  date: string; // e.g. "Hoje", "Ontem"
  lastMessage: string;
  tagText?: string; // "Prazo calculado" or "Mensagem pronta" or "DEMO" or null
  iconName: 'shopping_bag' | 'receipt_long' | 'local_shipping' | 'gavel';
  timestamp: number;
  chatHistory: ChatMessage[];
  responseStyle: 'simples' | 'detalhado' | 'firme';
  is_demo?: boolean; // ISSUE-M3-005: frontend-only marker for the three seed demos
}

export interface UserProfile {
  name: string;
  email: string;
  avatarUrl: string;
}

export interface SystemStatus {
  knowledgeBase: boolean;
  citations: boolean;
  securityCheck: boolean;
}

export interface AppPreferences {
  responseStyle: 'simples' | 'detalhado' | 'firme';
  userProfile: UserProfile;
  systemStatus: SystemStatus;
}
