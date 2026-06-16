import type {AppPreferences, Case, ChatMessage} from './types';

export const initialPreferences: AppPreferences = {
  responseStyle: 'detalhado',
  userProfile: {
    name: 'Convidado',
    email: '',
    avatarUrl: '',
  },
  systemStatus: {
    knowledgeBase: true,
    citations: true,
    securityCheck: true,
  },
};

function makeDemoMessages(
  turns: Array<{user: string; assistant: string}>,
  baseTs: number,
): ChatMessage[] {
  return turns.flatMap(({user, assistant}, i) => [
    {
      id: `d-u-${i}`,
      sender: 'user' as const,
      text: user,
      timestamp: baseTs - (turns.length - i) * 60000,
    },
    {
      id: `d-a-${i}`,
      sender: 'assistant' as const,
      text: assistant,
      timestamp: baseTs - (turns.length - i) * 60000 + 1000,
    },
  ]);
}

const NOW = Date.now();

export const seedCases: Case[] = [
  {
    id: 'case-1',
    title: 'Celular com defeito',
    date: 'Hoje',
    lastMessage: 'Voce tem 30 dias para reclamar de vicio em produto nao duravel (CDC art. 26).',
    tagText: 'DEMO',
    iconName: 'shopping_bag',
    timestamp: NOW - 60000,
    responseStyle: 'detalhado',
    is_demo: true,
    chatHistory: makeDemoMessages(
      [
        {
          user: 'Comprei um celular com defeito na tela. O que faco?',
          assistant:
            'Voce tem 30 dias para reclamar de vicio em produto nao duravel (CDC art. 26). Procure a loja e exija a troca ou o conserto.',
        },
      ],
      NOW - 60000,
    ),
  },
  {
    id: 'case-2',
    title: 'Arrependimento de compra online',
    date: 'Hoje',
    lastMessage: 'Voce tem 7 dias corridos para cancelar a compra (CDC art. 49).',
    tagText: 'DEMO',
    iconName: 'receipt_long',
    timestamp: NOW - 120000,
    responseStyle: 'detalhado',
    is_demo: true,
    chatHistory: makeDemoMessages(
      [
        {
          user: 'Quero cancelar uma compra online. Qual o prazo?',
          assistant:
            'Voce tem 7 dias corridos a partir do recebimento para exercer o direito de arrependimento (CDC art. 49).',
        },
      ],
      NOW - 120000,
    ),
  },
  {
    id: 'case-3',
    title: 'Cobranca indevida',
    date: 'Hoje',
    lastMessage: 'Envie uma notificacao extrajudicial exigindo a suspensao da cobranca.',
    tagText: 'DEMO',
    iconName: 'gavel',
    timestamp: NOW - 180000,
    responseStyle: 'detalhado',
    is_demo: true,
    chatHistory: makeDemoMessages(
      [
        {
          user: 'Estou sendo cobrado por um servico que cancelei. Como faco?',
          assistant:
            'Voce pode enviar uma notificacao extrajudicial exigindo a suspensao da cobranca em 10 dias uteis, sob pena de acao judicial.',
        },
      ],
      NOW - 180000,
    ),
  },
];
