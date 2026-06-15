import React, { useState, useEffect } from "react";
import { 
  Gavel, 
  Bell, 
  Home as HomeIcon, 
  MessageSquare, 
  FolderLock, 
  Settings as SettingsIcon, 
  Plus, 
  CheckCircle,
  X 
} from "lucide-react";
import { Case, ChatMessage, Deadline, AppPreferences } from "./types";
import HomeDashboard from "./components/HomeDashboard";
import ChatInterface from "./components/ChatInterface";
import CasesList from "./components/CasesList";
import ProfilePreferences from "./components/ProfilePreferences";

// Realistic Seed Cases with pre-loaded Portuguese chat histories matching CDC scenarios
const seedCases: Case[] = [
  {
    id: "case-1",
    title: "Celular comprado online",
    date: "Hoje",
    lastMessage: "Prazo de arrependimento calculado...",
    tagText: "Prazo calculado",
    iconName: "shopping_bag",
    timestamp: Date.now(),
    responseStyle: "detalhado",
    chatHistory: [
      {
        id: "msg-1a",
        sender: "user",
        text: "Comprei um celular online e me arrependi. Recebi ontem, mas a loja disse que não aceita devolução.",
        timestamp: Date.now() - 3600000 * 2
      },
      {
        id: "msg-1b",
        sender: "assistant",
        text: "O Artigo 49 do CDC resguarda compras fora de estabelecimento físico.",
        timestamp: Date.now() - 3600000 * 1.9,
        stepTitle: "Entendi o caso",
        stepContent: "Você realizou uma compra de um produto (celular) fora do estabelecimento comercial (online) e deseja exercer o direito de arrependimento logo após o recebimento, mas enfrentou recusa da loja.",
        relevantTitle: "O que pode ser relevante",
        relevantContent: "O Código de Defesa do Consumidor (CDC), em seu artigo 49, garante o direito de arrependimento em até 7 dias para compras feitas fora do estabelecimento comercial, independentemente do motivo.",
        deadline: {
          title: "Prazo calculado",
          type: "Direito de arrependimento",
          startDate: "10/06/2026",
          endDate: "17/06/2026",
          base: "CDC art. 49",
          note: "Estimativa baseada nas informações fornecidas. A data correta pode depender dos detalhes do caso."
        },
        questions: [
          "A compra foi feita pela internet, telefone ou aplicativo?",
          "Você recebeu o produto em que data exata?",
          "O produto está completo, com embalagem e acessórios originais?"
        ],
        suggestiveText: "Com base nisso, posso preparar uma mensagem para a loja pedindo o cancelamento e reembolso.",
        quickReplies: ["Preparar mensagem", "Continuar orientação", "Fazer outra pergunta"]
      }
    ]
  },
  {
    id: "case-2",
    title: "Cobrança duplicada",
    date: "Ontem",
    lastMessage: "Você pode reunir comprovantes...",
    tagText: undefined,
    iconName: "receipt_long",
    timestamp: Date.now() - 3600000 * 24,
    responseStyle: "simples",
    chatHistory: [
      {
        id: "msg-2a",
        sender: "user",
        text: "Me cobraram duas vezes a assinatura no cartão de crédito.",
        timestamp: Date.now() - 3600000 * 25
      },
      {
        id: "msg-2b",
        sender: "assistant",
        text: "Você pode contestar a cobrança e solicitar a devolução de forma dobrada.",
        timestamp: Date.now() - 3600000 * 24.8,
        stepTitle: "Cobrança Duplicada Identificada",
        stepContent: "Foi cobrado duas vezes pelo mesmo serviço no seu cartão e precisa reaver os valores.",
        relevantTitle: "Indébito em Dobro (CDC Artigo 42)",
        relevantContent: "O artigo 42, parágrafo único, do CDC, preceitua que o consumidor cobrado indevidamente faz jus à restituição em dobro do excesso pago, salvo hipóteses de engano justificável por parte do credor.",
        questions: [
          "Já entrou em contato com o suporte ou banco?",
          "As duas cobranças aparecem faturadas ou apenas pendentes?"
        ],
        suggestiveText: "Com esses comprovantes em mãos, podemos preparar sua contestação legal."
      }
    ]
  },
  {
    id: "case-3",
    title: "Atraso na entrega",
    date: "12 jun",
    lastMessage: "Mensagem para a empresa preparada...",
    tagText: "Mensagem pronta",
    iconName: "local_shipping",
    timestamp: Date.now() - 3600000 * 48,
    responseStyle: "firme",
    chatHistory: [
      {
        id: "msg-3a",
        sender: "user",
        text: "Meu guarda-roupa devia ter chegado dia 5 e até agora nada. Quero meu dinheiro de volta ou entrega expressa.",
        timestamp: Date.now() - 3600000 * 49
      },
      {
        id: "msg-3b",
        sender: "assistant",
        text: "O atraso injustificado dá direito ao cumprimento forçado ou cancelamento.",
        timestamp: Date.now() - 3600000 * 48.5,
        stepTitle: "Atraso Grave na Entrega",
        stepContent: "O prazo estipulado contratualmente expirou sem que a mercadoria fosse entregue ao consumidor final.",
        relevantTitle: "Descumprimento de Oferta (CDC Artigo 35)",
        relevantContent: "O Código faculta ao consumidor rescindir o pacto com estorno corrigido frente à recusa do fornecedor em suprir as datas aventadas.",
        templateLetter: `À [Nome do Estabelecimento]
Notificação formal por atraso na entrega (Art. 35 do CDC)

Solicito a imediata devolução dos valores pagos frente à quebra de oferta do guarda-roupa com entrega em atraso desde o dia 5.`,
        suggestiveText: "Notificação extrajudicial gerada com sucesso. Copie o texto para contatar o suporte."
      }
    ]
  }
];

const initialPreferences: AppPreferences = {
  responseStyle: "detalhado",
  userProfile: {
    name: "Dr. Ricardo Silva",
    email: "ricardo.silva@exemplo.com",
    avatarUrl: "https://lh3.googleusercontent.com/aida-public/AB6AXuD4QKwTDtz0Z5Bt6pBtWBGZN1P1m5rOqAlJZi6W8pIx0lH_cjLoHztEcbu92KAl8S3HfuQ091CC06vJ5wbGPEtRKU8gJqXmJCqbyhC97pciDQytYPmDDB38XuhhbuyVOkzlLhUfpI5e0MTHmgcuUv26XweVQ4dzn136wjcw1dk_o6bIBs7ohPn3i2eVnDSojNgp7ieT9-be-IBidM0uV6IQIUyU6uEA_zHKumGxrVKc37zODHnnMudrwGS79Nv2NWTNgn0o4-GdSeNv"
  },
  systemStatus: {
    knowledgeBase: true,
    citations: true,
    securityCheck: true
  }
};

export default function App() {
  const [activeTab, setActiveTab] = useState<"inicio" | "conversar" | "casos" | "perfil">("inicio");
  const [cases, setCases] = useState<Case[]>(seedCases);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [currentChatHistory, setCurrentChatHistory] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [preferences, setPreferences] = useState<AppPreferences>(initialPreferences);

  // In-app visual notifications toast (preserves iframe sandbox rules)
  const [toast, setToast] = useState<{ show: boolean; msg: string; type: "success" | "info" }>({
    show: false,
    msg: "",
    type: "success"
  });

  const triggerToast = (msg: string, type: "success" | "info" = "success") => {
    setToast({ show: true, msg, type });
  };

  useEffect(() => {
    if (toast.show) {
      const timer = setTimeout(() => setToast(t => ({ ...t, show: false })), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast.show]);

  // Loading case on selection
  const handleSelectCase = (caseId: string) => {
    const selected = cases.find(c => c.id === caseId);
    if (selected) {
      setActiveCaseId(caseId);
      setCurrentChatHistory(selected.chatHistory);
      setActiveTab("conversar");
      triggerToast(`Carregado: ${selected.title}`, "info");
    }
  };

  // Safe Case Deletion
  const handleDeleteCase = (caseId: string) => {
    setCases(prev => prev.filter(c => c.id !== caseId));
    if (activeCaseId === caseId) {
      setActiveCaseId(null);
      setCurrentChatHistory([]);
    }
    triggerToast("Consulta excluída com sucesso.");
  };

  const handleRenameCase = (caseId: string, newTitle: string) => {
    setCases(prev => prev.map(c => {
      if (c.id === caseId) {
        return { ...c, title: newTitle };
      }
      return c;
    }));
    triggerToast("Consulta renomeada com sucesso!");
  };

  // Create empty new consultation
  const handleStartConsultation = (initialPrompt?: string) => {
    setActiveCaseId(null);
    setCurrentChatHistory([]);
    setActiveTab("conversar");
    if (initialPrompt) {
      // Simulate typing prompt right in
      triggerToast("Análise de caso iniciada...");
      handleSendMessage(initialPrompt);
    }
  };

  // Message dispatcher
  const handleSendMessage = async (text: string) => {
    const userMsgId = `user-msg-${Date.now()}`;
    const newUserMsg: ChatMessage = {
      id: userMsgId,
      sender: "user",
      text,
      timestamp: Date.now()
    };

    // Update active screen state
    const updatedHistory = [...currentChatHistory, newUserMsg];
    setCurrentChatHistory(updatedHistory);
    setIsLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: updatedHistory,
          responseStyle: preferences.responseStyle
        })
      });

      if (!response.ok) {
        throw new Error("API return status not ok");
      }

      const resData = await response.json();

      const botMsg: ChatMessage = {
        id: `bot-msg-${Date.now()}`,
        sender: "assistant",
        text: resData.stepContent || "Consulta processada.",
        timestamp: Date.now(),
        stepTitle: resData.stepTitle,
        stepContent: resData.stepContent,
        relevantTitle: resData.relevantTitle,
        relevantContent: resData.relevantContent,
        deadline: resData.deadline,
        questions: resData.questions,
        suggestiveText: resData.suggestiveText,
        templateLetter: resData.templateLetter,
        quickReplies: resData.quickReplies
      };

      const finalHistory = [...updatedHistory, botMsg];
      setCurrentChatHistory(finalHistory);

      // Save log dynamically under the loaded case, if any is active
      if (activeCaseId) {
        setCases(prev => prev.map(c => {
          if (c.id === activeCaseId) {
            return {
              ...c,
              lastMessage: botMsg.stepContent || botMsg.text,
              chatHistory: finalHistory,
              tagText: botMsg.deadline ? "Prazo calculado" : botMsg.templateLetter ? "Mensagem pronta" : undefined
            };
          }
          return c;
        }));
      }
    } catch (err) {
      console.error("Consultation sending error:", err);
      // Failover message block
      const botMsg: ChatMessage = {
        id: `bot-msg-err-${Date.now()}`,
        sender: "assistant",
        text: "Desculpe pelo contratempo. Ocorreu um problema no gateway de IA, mas você ainda conta com a proteção do Código de Defesa do Consumidor brasileiro. Refaça a dúvida curta para outra resolução.",
        timestamp: Date.now()
      };
      setCurrentChatHistory([...updatedHistory, botMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  // Interactive Save action inside tool cards
  const handleSaveCaseFromChat = (deadline?: Deadline) => {
    // Generate a title based on the first user message or calculation
    const firstUserMsg = currentChatHistory.find(m => m.sender === "user")?.text || "Nova Consulta";
    const titleText = deadline ? `${deadline.title.replace("calculado de ", "")}` : `Consulta do Consumidor`;
    const customizedTitle = firstUserMsg.toLowerCase().includes("celular") 
      ? "Celular comprado online" 
      : firstUserMsg.toLowerCase().includes("cobrança") 
      ? "Cobrança indevida" 
      : firstUserMsg.toLowerCase().includes("atraso") 
      ? "Atraso na entrega" 
      : titleText;

    // Check if we are modifying/saving an existing case or creating a brand new one
    if (activeCaseId) {
      setCases(prev => prev.map(c => {
        if (c.id === activeCaseId) {
          return {
            ...c,
            title: customizedTitle,
            chatHistory: currentChatHistory,
            tagText: deadline ? "Prazo calculado" : "Mensagem pronta"
          };
        }
        return c;
      }));
      triggerToast("Caso e cálculo persistidos com sucesso!");
    } else {
      const newId = `case-new-${Date.now()}`;
      const newC: Case = {
        id: newId,
        title: customizedTitle,
        date: "Hoje",
        lastMessage: currentChatHistory[currentChatHistory.length - 1]?.text || "Histórico guardado.",
        tagText: deadline ? "Prazo calculado" : "Mensagem pronta",
        iconName: firstUserMsg.toLowerCase().includes("celular") ? "shopping_bag" : "gavel",
        timestamp: Date.now(),
        responseStyle: preferences.responseStyle,
        chatHistory: currentChatHistory
      };
      
      setCases(prev => [newC, ...prev]);
      setActiveCaseId(newId);
      triggerToast("Consulta adicionada à aba Meus Casos!");
    }
  };

  const handleUpdatePreferences = (updated: Partial<AppPreferences>) => {
    setPreferences(prev => ({ ...prev, ...updated }));
    triggerToast("Configurações atualizadas!");
  };

  return (
    <div className="bg-[#fbf9f8] min-h-screen text-slate-900 font-sans flex flex-col antialiased">
      
      {/* Dynamic Header top navigation (Web view & iPad) */}
      <header className="fixed top-0 left-0 w-full bg-white border-b border-slate-200 z-50 h-16 shadow-[0px_2px_4px_rgba(0,33,71,0.01)] px-5 flex items-center justify-between" id="app-header-nav">
        <div className="flex items-center gap-2.5">
          <div className="bg-[#002147] p-2 rounded-xl text-white">
            <Gavel className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-bold text-[#002147] tracking-tight text-base">Advogado de Bolso</h1>
            <span className="text-[10px] text-slate-400 font-bold tracking-wider uppercase block -mt-0.5">CDC Inteligente</span>
          </div>
        </div>

        {/* Desktop Navbar Tabs layout */}
        <nav className="hidden md:flex items-center gap-2">
          {[
            { id: "inicio", label: "Início", icon: HomeIcon },
            { id: "conversar", label: "Conversar", icon: MessageSquare },
            { id: "casos", label: "Meus Casos", icon: FolderLock },
            { id: "perfil", label: "Preferências", icon: SettingsIcon }
          ].map(tab => {
            const Icon = tab.icon;
            const isSel = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id as any);
                  if (tab.id === "conversar" && currentChatHistory.length === 0) {
                    // Seed if empty on quick tab
                    setCurrentChatHistory([]);
                  }
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                  isSel 
                    ? "bg-[#002147] text-[#aec7f6] shadow-sm scale-102" 
                    : "text-slate-500 hover:bg-slate-50 hover:text-[#002147]"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* Notifications and status area */}
        <div className="flex items-center gap-2">
          <button 
            type="button"
            onClick={() => triggerToast("Sem notificações no momento.", "info")}
            className="text-slate-400 hover:text-[#002147] bg-slate-50 hover:bg-slate-100 p-2 rounded-xl transition-all relative"
            title="Notificações"
          >
            <Bell className="w-4.5 h-4.5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#aec7f6] rounded-full"></span>
          </button>
        </div>
      </header>

      {/* Main viewport canvas */}
      <main className="flex-grow pt-20 pb-20 md:pb-6 px-4 max-w-[1100px] w-full mx-auto" id="app-main-canvas">
        <div className="h-full flex flex-col" id="app-tab-switcher">
          {activeTab === "inicio" && (
            <HomeDashboard 
              cases={cases}
              onStartConsultation={handleStartConsultation}
              onSelectCase={handleSelectCase}
            />
          )}

          {activeTab === "conversar" && (
            <ChatInterface 
              chatHistory={currentChatHistory}
              isLoading={isLoading}
              onSendMessage={handleSendMessage}
              onSaveCase={handleSaveCaseFromChat}
            />
          )}

          {activeTab === "casos" && (
            <CasesList 
              cases={cases}
              onSelectCase={handleSelectCase}
               onNewConsultation={() => handleStartConsultation()}
              onDeleteCase={handleDeleteCase}
              onRenameCase={handleRenameCase}
            />
          )}

          {activeTab === "perfil" && (
            <ProfilePreferences 
              preferences={preferences}
              onUpdatePreferences={handleUpdatePreferences}
            />
          )}
        </div>
      </main>

      {/* Mobile responsive Fixed Bottom tab bar navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 w-full h-14 bg-white border-t border-slate-200 z-50 flex justify-around items-center px-4 shadow-[0px_-2px_12px_rgba(0,33,71,0.03)]" id="mobile-nav-bar">
        {[
          { id: "inicio", label: "Início", icon: HomeIcon },
          { id: "conversar", label: "Conversar", icon: MessageSquare },
          { id: "casos", label: "Casos", icon: FolderLock },
          { id: "perfil", label: "Preferências", icon: SettingsIcon }
        ].map(tab => {
          const Icon = tab.icon;
          const isSel = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex flex-col items-center justify-center flex-1 h-full py-1.5 cursor-pointer relative transition-all ${
                isSel ? "text-[#002147] font-bold scale-102" : "text-slate-400 font-medium"
              }`}
            >
              <Icon className="w-5 h-5 mb-0.5" />
              <span className="text-[9px] tracking-wide leading-none">{tab.label}</span>
              {isSel && (
                <span className="absolute bottom-1 w-1 h-1 bg-[#002147] rounded-full"></span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Persistent Inline Safe Toast Alerts (circumvents Sandbox restriction) */}
      {toast.show && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 bg-[#002147]/95 backdrop-blur-xs text-white text-xs font-bold py-2 px-4 rounded-xl flex items-center gap-2 shadow-lg border border-slate-800 animate-in fade-in slide-in-from-bottom duration-200" id="in-app-safe-toast">
          <CheckCircle className="w-4 h-4 text-[#aec7f6]" />
          <span>{toast.msg}</span>
          <button 
            onClick={() => setToast(t => ({ ...t, show: false }))}
            className="p-1 hover:text-[#aec7f6] transition-colors ml-2"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

    </div>
  );
}
