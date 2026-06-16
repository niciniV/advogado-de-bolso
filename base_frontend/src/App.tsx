import React, { useState, useEffect, useRef } from "react";
import {
  Gavel,
  Bell,
  Home as HomeIcon,
  MessageSquare,
  FolderLock,
  Settings as SettingsIcon,
  CheckCircle,
  X,
} from "lucide-react";
import { Case, ChatMessage, Deadline, AppPreferences } from "./types";
import HomeDashboard from "./components/HomeDashboard";
import ChatInterface from "./components/ChatInterface";
import CasesList from "./components/CasesList";
import ProfilePreferences from "./components/ProfilePreferences";
import { seedCases, initialPreferences } from "./defaults";
import {
  apiClient,
  deriveLastMessage,
  deriveTagText,
  formatCaseDate,
  mapStructuredResponse,
  type WireStructuredChatRequest,
} from "./api";

type IconName = Case["iconName"];
type ResponseStyle = Case["responseStyle"];

interface PendingBlockedCase {
  sessionId: string;
  title: string;
  iconName: IconName;
  responseStyle: ResponseStyle;
}

interface SendOptions {
  forceNewCase?: boolean;
}

function deriveCaseMeta(text: string): { title: string; icon_name: IconName } {
  const lower = text.toLowerCase();
  if (/\bcelular\b/i.test(lower)) {
    return { title: "Celular comprado online", icon_name: "shopping_bag" };
  }
  if (/\bcobr(a|an|ad)/i.test(lower)) {
    return { title: "Cobranca indevida", icon_name: "receipt_long" };
  }
  if (/\b(atraso|entrega)\b/i.test(lower)) {
    return { title: "Atraso na entrega", icon_name: "local_shipping" };
  }
  if (/\b(notif\w+|extrajudicial)\b/i.test(lower)) {
    return { title: "Notificacao extrajudicial", icon_name: "gavel" };
  }
  return { title: "Nova consulta", icon_name: "gavel" };
}

export default function App() {
  const [activeTab, setActiveTab] = useState<"inicio" | "conversar" | "casos" | "perfil">("inicio");
  const [cases, setCases] = useState<Case[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [currentChatHistory, setCurrentChatHistory] = useState<ChatMessage[]>([]);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [isLoadingCases, setIsLoadingCases] = useState<boolean>(true);
  const [preferences, setPreferences] = useState<AppPreferences>(initialPreferences);

  const pendingBlockedCaseRef = useRef<PendingBlockedCase | null>(null);

  // In-app visual notifications toast
  const [toast, setToast] = useState<{ show: boolean; msg: string; type: "success" | "info" }>({
    show: false,
    msg: "",
    type: "success",
  });

  const triggerToast = (msg: string, type: "success" | "info" = "success") => {
    setToast({ show: true, msg, type });
  };

  useEffect(() => {
    if (toast.show) {
      const timer = setTimeout(() => setToast((t) => ({ ...t, show: false })), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast.show]);

  // ISSUE-M3-017: load real cases on mount. Show seedCases only if no real cases are returned.
  // NEX-001: non-clobbering - if the user has already created a real case in the meantime,
  // do not overwrite it with the late listCases response.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const real = await apiClient.listCases();
        if (cancelled) return;
        setCases((prev) => (prev.length === 0 ? (real.length > 0 ? real : seedCases) : prev));
      } catch {
        if (!cancelled) setCases((prev) => (prev.length === 0 ? seedCases : prev));
      } finally {
        if (!cancelled) setIsLoadingCases(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const isDemoCase = (c: Case | undefined | null): boolean => Boolean(c?.is_demo);

  const activeCase = cases.find((c) => c.id === activeCaseId);

  // Selecting a case: demo stays local; real case fetches via API.
  const handleSelectCase = async (caseId: string) => {
    pendingBlockedCaseRef.current = null;
    const selected = cases.find((c) => c.id === caseId);
    if (!selected) return;
    if (isDemoCase(selected)) {
      setActiveCaseId(caseId);
      setCurrentChatHistory(selected.chatHistory);
      setActiveTab("conversar");
      triggerToast(`Carregado: ${selected.title}`, "info");
      return;
    }
    try {
      const full = await apiClient.getCase(caseId);
      setCases((prev) => prev.map((c) => (c.id === caseId ? full : c)));
      setActiveCaseId(caseId);
      setCurrentChatHistory(full.chatHistory);
      setActiveTab("conversar");
      triggerToast(`Carregado: ${full.title}`, "info");
    } catch (err) {
      console.error("Failed to load case", err);
      triggerToast("Falha ao carregar o caso.", "info");
    }
  };

  // Deleting a case: demo stays local; real case calls API.
  const handleDeleteCase = async (caseId: string) => {
    pendingBlockedCaseRef.current = null;
    const target = cases.find((c) => c.id === caseId);
    if (isDemoCase(target)) {
      setCases((prev) => prev.filter((c) => c.id !== caseId));
      if (activeCaseId === caseId) {
        setActiveCaseId(null);
        setCurrentChatHistory([]);
      }
      triggerToast("Consulta excluida com sucesso.");
      return;
    }
    try {
      await apiClient.deleteCase(caseId);
      setCases((prev) => prev.filter((c) => c.id !== caseId));
      if (activeCaseId === caseId) {
        setActiveCaseId(null);
        setCurrentChatHistory([]);
      }
      triggerToast("Consulta excluida com sucesso.");
    } catch (err) {
      console.error("Failed to delete case", err);
      triggerToast("Falha ao excluir o caso.", "info");
    }
  };

  const handleRenameCase = async (caseId: string, newTitle: string) => {
    const target = cases.find((c) => c.id === caseId);
    if (isDemoCase(target)) {
      setCases((prev) => prev.map((c) => (c.id === caseId ? { ...c, title: newTitle } : c)));
      triggerToast("Consulta renomeada com sucesso!");
      return;
    }
    try {
      const updated = await apiClient.renameCase(caseId, newTitle);
      setCases((prev) => prev.map((c) => (c.id === caseId ? updated : c)));
      triggerToast("Consulta renomeada com sucesso!");
    } catch (err) {
      console.error("Failed to rename case", err);
      triggerToast("Falha ao renomear o caso.", "info");
    }
  };

  // Create empty new consultation; if initialPrompt provided, force a new case.
  const handleStartConsultation = (initialPrompt?: string) => {
    pendingBlockedCaseRef.current = null;
    setActiveCaseId(null);
    setCurrentChatHistory([]);
    setActiveTab("conversar");
    if (initialPrompt) {
      triggerToast("Analise de caso iniciada...");
      handleSendMessage(initialPrompt, { forceNewCase: true });
    }
  };

  // Update preferences; if responseStyle changes and a real case is active, PATCH it.
  const handleUpdatePreferences = async (updated: Partial<AppPreferences>) => {
    setPreferences((prev) => ({ ...prev, ...updated }));
    if (updated.responseStyle && activeCase && !isDemoCase(activeCase)) {
      try {
        const synced = await apiClient.updateCaseMeta(activeCase.id, {
          response_style: updated.responseStyle,
        });
        setCases((prev) => prev.map((c) => (c.id === synced.id ? synced : c)));
        triggerToast("Configuracoes atualizadas!");
      } catch (err) {
        console.error("Failed to sync response style to case", err);
        triggerToast("Atualizado localmente.");
      }
    } else {
      triggerToast("Configuracoes atualizadas!");
    }
  };

  // Explicit user-triggered "save this generated result" from the tool card.
  // Does NOT create cases (the first successful message already auto-created one).
  const handleSaveCaseFromChat = async (deadline?: Deadline) => {
    if (!activeCase || isDemoCase(activeCase)) return;
    const firstUserMsg = currentChatHistory.find((m) => m.sender === "user")?.text || "";
    const meta = deriveCaseMeta(firstUserMsg);
    try {
      const updated = await apiClient.updateCaseMeta(activeCase.id, {
        title: meta.title,
        icon_name: meta.icon_name,
      });
      setCases((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      triggerToast("Caso e calculo persistidos com sucesso!");
    } catch (err) {
      console.error("Failed to save case from chat", err);
      triggerToast("Falha ao persistir o caso.", "info");
    }
  };

  // Message dispatcher with blocked-retry ref + auto-create metadata.
  const handleSendMessage = async (text: string, options?: SendOptions) => {
    const forceNewCase = options?.forceNewCase === true;
    const demoActive = isDemoCase(activeCase);

    let sessionId: string | null;
    let firstCreateMeta: { title: string; iconName: IconName; responseStyle: ResponseStyle } | null = null;

    if (forceNewCase || demoActive) {
      pendingBlockedCaseRef.current = null;
      sessionId = null;
    } else if (pendingBlockedCaseRef.current) {
      const p = pendingBlockedCaseRef.current;
      sessionId = p.sessionId;
      firstCreateMeta = { title: p.title, iconName: p.iconName, responseStyle: p.responseStyle };
    } else if (activeCaseId && !demoActive) {
      sessionId = activeCaseId;
    } else {
      sessionId = null;
    }

    if (sessionId === null && !firstCreateMeta) {
      const meta = deriveCaseMeta(text);
      firstCreateMeta = {
        title: meta.title,
        iconName: meta.icon_name,
        responseStyle: preferences.responseStyle,
      };
    }

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text,
      timestamp: Date.now(),
    };
    // NEX-002: a quick-guide send (forceNewCase) or a demo-active send starts a brand new
    // consultation - do not let the previous case's history leak into the optimistic view.
    const optimisticHistory =
      forceNewCase || demoActive ? [userMsg] : [...currentChatHistory, userMsg];
    setCurrentChatHistory(optimisticHistory);
    setIsSendingMessage(true);

    // NEX-003: when sending to an existing real case, prefer the case's persisted
    // response_style over the global preference so we do not override a per-case setting.
    const activeRealCase = activeCaseId ? cases.find((c) => c.id === activeCaseId) : null;
    const caseResponseStyle =
      activeRealCase && !isDemoCase(activeRealCase) ? activeRealCase.responseStyle : null;
    const wirePayload: WireStructuredChatRequest = {
      message: text,
      session_id: sessionId,
      response_style: firstCreateMeta?.responseStyle ?? caseResponseStyle ?? preferences.responseStyle,
    };
    if (firstCreateMeta) {
      wirePayload.title = firstCreateMeta.title;
      wirePayload.icon_name = firstCreateMeta.iconName;
    }

    let response: Response;
    try {
      response = await apiClient.chatStructured(wirePayload);
    } catch (err) {
      console.error("Network error", err);
      setCurrentChatHistory((prev) => [
        ...prev,
        {
          id: `bot-err-${Date.now()}`,
          sender: "assistant",
          text: "Desculpe pelo contratempo. Ocorreu um problema no gateway de IA. Tente novamente em instantes.",
          timestamp: Date.now(),
        },
      ]);
      setIsSendingMessage(false);
      return;
    }

    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }

    if (!response.ok) {
      const obj = (body || {}) as {
        blocked?: boolean;
        blocked_message?: string;
        session_id?: string;
        chat_history?: WireStructuredChatRequest extends never ? never : unknown[];
      };
      if (obj.blocked) {
        const blockedMessage = obj.blocked_message || "Resposta bloqueada pelo revisor.";
        if (sessionId === null && firstCreateMeta && obj.session_id) {
          pendingBlockedCaseRef.current = {
            sessionId: obj.session_id,
            title: firstCreateMeta.title,
            iconName: firstCreateMeta.iconName,
            responseStyle: firstCreateMeta.responseStyle,
          };
        }
        setCurrentChatHistory((prev) => [
          ...prev,
          {
            id: `bot-blocked-${Date.now()}`,
            sender: "assistant",
            text: blockedMessage,
            timestamp: Date.now(),
          },
        ]);
        setIsSendingMessage(false);
        return;
      }
      pendingBlockedCaseRef.current = null;
      setCurrentChatHistory((prev) => [
        ...prev,
        {
          id: `bot-err-${Date.now()}`,
          sender: "assistant",
          text: "Nao foi possivel processar a mensagem agora. Tente novamente.",
          timestamp: Date.now(),
        },
      ]);
      setIsSendingMessage(false);
      return;
    }

    // NEX-004: guard the adapter - a 200 with malformed JSON / missing fields can throw
    // and leave isSendingMessage stuck. Reset state and surface a generic assistant error.
    let mapped: ReturnType<typeof mapStructuredResponse> | null = null;
    try {
      mapped = mapStructuredResponse(body as Parameters<typeof mapStructuredResponse>[0]);
    } catch (err) {
      console.error("Failed to map structured response", err);
      setCurrentChatHistory((prev) => [
        ...prev,
        {
          id: `bot-err-${Date.now()}`,
          sender: "assistant",
          text: "Nao foi possivel processar a resposta do servidor.",
          timestamp: Date.now(),
        },
      ]);
      setIsSendingMessage(false);
      return;
    }
    setCurrentChatHistory(mapped.chatHistory);
    setActiveCaseId(mapped.sessionId);

    const assistantMsg =
      [...mapped.chatHistory].reverse().find((m) => m.sender === "assistant") || null;

    if (firstCreateMeta) {
      const isFirstReal = cases.filter((c) => !c.is_demo).length === 0;
      const newCase: Case = {
        id: mapped.sessionId,
        title: firstCreateMeta.title,
        date: formatCaseDate(mapped.updatedAt),
        lastMessage: deriveLastMessage(mapped.chatHistory),
        tagText: deriveTagText(mapped.chatHistory) || (assistantMsg?.deadline ? "Prazo calculado" : assistantMsg?.templateLetter ? "Mensagem pronta" : undefined),
        iconName: firstCreateMeta.iconName,
        timestamp: Date.parse(mapped.updatedAt) || Date.now(),
        responseStyle: firstCreateMeta.responseStyle,
        is_demo: false,
        chatHistory: mapped.chatHistory,
      };
      setCases((prev) => {
        const withoutDemos = isFirstReal ? prev.filter((c) => !c.is_demo) : prev;
        return [newCase, ...withoutDemos.filter((c) => c.id !== newCase.id)];
      });
      pendingBlockedCaseRef.current = null;
    } else if (activeCaseId) {
      setCases((prev) =>
        prev.map((c) => {
          if (c.id !== activeCaseId) return c;
          return {
            ...c,
            date: formatCaseDate(mapped.updatedAt),
            lastMessage: deriveLastMessage(mapped.chatHistory),
            tagText: deriveTagText(mapped.chatHistory) || c.tagText,
            timestamp: Date.parse(mapped.updatedAt) || c.timestamp,
            chatHistory: mapped.chatHistory,
          };
        }),
      );
    }

    setIsSendingMessage(false);
  };

  return (
    <div className="bg-[#fbf9f8] min-h-screen text-slate-900 font-sans flex flex-col antialiased">
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

        <nav className="hidden md:flex items-center gap-2">
          {[
            { id: "inicio", label: "Inicio", icon: HomeIcon },
            { id: "conversar", label: "Conversar", icon: MessageSquare },
            { id: "casos", label: "Meus Casos", icon: FolderLock },
            { id: "perfil", label: "Preferencias", icon: SettingsIcon },
          ].map((tab) => {
            const Icon = tab.icon;
            const isSel = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
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

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => triggerToast("Sem notificacoes no momento.", "info")}
            className="text-slate-400 hover:text-[#002147] bg-slate-50 hover:bg-slate-100 p-2 rounded-xl transition-all relative"
            title="Notificacoes"
          >
            <Bell className="w-4.5 h-4.5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#aec7f6] rounded-full"></span>
          </button>
        </div>
      </header>

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
              isSendingMessage={isSendingMessage}
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
              onUpdatePreferences={(p) => {
                void handleUpdatePreferences(p);
              }}
            />
          )}

          {isLoadingCases && activeTab === "casos" && (
            <div className="p-6 text-center text-xs text-slate-500">Carregando casos...</div>
          )}
        </div>
      </main>

      <nav className="md:hidden fixed bottom-0 left-0 w-full h-14 bg-white border-t border-slate-200 z-50 flex justify-around items-center px-4 shadow-[0px_-2px_12px_rgba(0,33,71,0.03)]" id="mobile-nav-bar">
        {[
          { id: "inicio", label: "Inicio", icon: HomeIcon },
          { id: "conversar", label: "Conversar", icon: MessageSquare },
          { id: "casos", label: "Casos", icon: FolderLock },
          { id: "perfil", label: "Preferencias", icon: SettingsIcon },
        ].map((tab) => {
          const Icon = tab.icon;
          const isSel = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
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

      {toast.show && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 bg-[#002147]/95 backdrop-blur-xs text-white text-xs font-bold py-2 px-4 rounded-xl flex items-center gap-2 shadow-lg border border-slate-800 animate-in fade-in slide-in-from-bottom duration-200" id="in-app-safe-toast">
          <CheckCircle className="w-4 h-4 text-[#aec7f6]" />
          <span>{toast.msg}</span>
          <button
            onClick={() => setToast((t) => ({ ...t, show: false }))}
            className="p-1 hover:text-[#aec7f6] transition-colors ml-2"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  );
}
