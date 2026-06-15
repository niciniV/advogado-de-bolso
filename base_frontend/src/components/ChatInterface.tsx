import React, { useState, useRef, useEffect } from "react";
import { Send, Paperclip, ChevronRight, CheckCircle, HelpCircle, Calendar, MessageSquare, Clipboard, Check, RefreshCw } from "lucide-react";
import { ChatMessage, Deadline, Case } from "../types";

interface ChatInterfaceProps {
  chatHistory: ChatMessage[];
  isLoading: boolean;
  onSendMessage: (text: string) => void;
  onSaveCase: (deadline?: Deadline) => void;
}

export default function ChatInterface({
  chatHistory,
  isLoading,
  onSendMessage,
  onSaveCase
}: ChatInterfaceProps) {
  const [inputText, setInputText] = useState("");
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  
  // Recalculating state simulation
  const [recalculatingIdx, setRecalculatingIdx] = useState<number | null>(null);
  const [customDate, setCustomDate] = useState("");
  const [editingDeadlineIdx, setEditingDeadlineIdx] = useState<number | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, isLoading]);

  const handleSend = () => {
    if (!inputText.trim() || isLoading) return;
    onSendMessage(inputText);
    setInputText("");
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSend();
  };

  const copyToClipboard = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleRecalculate = (idx: number, originalDeadline: Deadline) => {
    setEditingDeadlineIdx(idx);
    setCustomDate("2026-06-13"); // Default preset
  };

  const submitRecalculation = (idx: number, originalDeadline: Deadline) => {
    if (!customDate) {
      setEditingDeadlineIdx(null);
      return;
    }
    
    // Parse customDate back to localized format DD/MM/YYYY
    const parts = customDate.split("-");
    const d = parts[2] ? `${parts[2]}/${parts[1]}/${parts[0]}` : customDate;
    
    // Add logic to advance 7 days for Direito de arrependimento
    const isArrependimento = originalDeadline.type.toLowerCase().includes("desistência") || originalDeadline.type.toLowerCase().includes("arrependimento");
    let endDateStr = originalDeadline.endDate;

    if (isArrependimento && parts.length === 3) {
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      const limitDate = new Date(year, month, day);
      limitDate.setDate(limitDate.getDate() + 7);
      
      const resD = String(limitDate.getDate()).padStart(2, '0');
      const resM = String(limitDate.getMonth() + 1).padStart(2, '0');
      const resY = limitDate.getFullYear();
      endDateStr = `${resD}/${resM}/${resY}`;
    }

    // Trigger fake live recalculation feedback
    setRecalculatingIdx(idx);
    setTimeout(() => {
      originalDeadline.startDate = `${d} (Atualizado)`;
      originalDeadline.endDate = endDateStr;
      setRecalculatingIdx(null);
      setEditingDeadlineIdx(null);
    }, 800);
  };

  return (
    <div className="flex flex-col flex-grow h-full" id="chat-interface">
      {/* Scrollable Chat Canvas */}
      <div className="flex-1 overflow-y-auto space-y-6 pb-28 pt-2" id="chat-messages-scroll">
        {chatHistory.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center" id="empty-state">
            <div className="w-14 h-14 bg-slate-50 border border-slate-100 rounded-full flex items-center justify-center mb-4 shadow-[0px_2px_4px_rgba(0,33,71,0.02)]">
              <MessageSquare className="w-6 h-6 text-[#002147]" />
            </div>
            <h4 className="font-semibold text-slate-800 text-base">Inicie sua Consulta de Consumo</h4>
            <p className="text-slate-500 text-xs max-w-xs mt-1">
              Descreva seu problema com compras, cobranças ou produtos para que o Advogado de Bolso possa te orientar estruturadamente.
            </p>
          </div>
        ) : (
          chatHistory.map((msg, idx) => {
            const isUser = msg.sender === "user";
            return (
              <div
                key={msg.id || idx}
                className={`flex w-full ${isUser ? "justify-end pl-12" : "justify-start pr-12"}`}
              >
                {/* Message Bubble Container */}
                <div
                  className={`max-w-[100%] rounded-2xl shadow-[0px_2px_4px_rgba(0,33,71,0.02)] p-4 ${
                    isUser
                      ? "bg-[#002147] text-white rounded-tr-[4px]"
                      : "bg-[#ffffff] border border-slate-200 text-slate-800 rounded-tl-[4px]"
                  }`}
                >
                  {/* Sender Headers / Structure */}
                  <div className="flex items-start gap-2.5">
                    {!isUser && (
                      <div className="bg-[#aec7f6]/20 p-1.5 rounded-lg text-[#002147] mt-0.5">
                        <GavelIcon className="w-4 h-4 text-[#002147]" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0 space-y-4">
                      {/* Subtitle / Entendi o caso (if assistant) */}
                      {!isUser && msg.stepTitle && (
                        <div>
                          <h4 className="font-bold text-[#002147] text-sm flex items-center gap-1.5 mb-1">
                            <CheckCircle className="w-4 h-4 text-emerald-600" /> {msg.stepTitle}
                          </h4>
                          <p className="text-xs text-slate-600 leading-relaxed">{msg.stepContent || msg.text}</p>
                        </div>
                      )}

                      {/* Main Message Content */}
                      {(isUser || (!msg.stepTitle && msg.text)) && (
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                      )}

                      {/* Relevant legal context box */}
                      {!isUser && msg.relevantTitle && (
                        <div className="border-t border-slate-100 pt-3">
                          <h4 className="font-bold text-[#002147] text-sm flex items-center gap-1.5 mb-1">
                            <HelpCircle className="w-4 h-4 text-[#002147]" /> {msg.relevantTitle}
                          </h4>
                          <p className="text-xs text-slate-600 leading-relaxed">{msg.relevantContent}</p>
                        </div>
                      )}

                      {/* PRAZO CALCULADO IMMERSIVE CARD */}
                      {!isUser && msg.deadline && (
                        <div className="bg-[#F8F9FA] rounded-xl border border-slate-200 p-4 mt-2 relative overflow-hidden shadow-sm" id={`deadline-card-${idx}`}>
                          {/* Colored left strip */}
                          <div className="absolute top-0 left-0 w-1 h-full bg-[#aec7f6]"></div>
                          
                          <h5 className="font-bold text-xs text-[#002147] flex justify-between items-center mb-3">
                            {msg.deadline.title}
                            <Calendar className="w-4 h-4 text-[#002147] opacity-80" />
                          </h5>

                          <ul className="text-xs text-slate-600 space-y-1.5 mb-3">
                            <li className="flex justify-between">
                              <span className="font-medium text-slate-500">Tipo:</span>
                              <span className="text-slate-800 font-semibold">{msg.deadline.type}</span>
                            </li>
                            <li className="flex justify-between">
                              <span className="font-medium text-slate-500">Data inicial:</span>
                              <span className="text-slate-800 font-semibold">{msg.deadline.startDate}</span>
                            </li>
                            <li className="flex justify-between items-baseline">
                              <span className="font-medium text-slate-500">Data limite estimada:</span>
                              <span className="text-red-600 font-bold bg-red-50 px-1.5 py-0.5 rounded">{msg.deadline.endDate}</span>
                            </li>
                            <li className="flex justify-between">
                              <span className="font-medium text-slate-500">Base legal:</span>
                              <span className="text-[#002147] bg-[#d6e3ff] px-1.5 py-0.5 rounded font-bold">{msg.deadline.base}</span>
                            </li>
                          </ul>

                          {msg.deadline.note && (
                            <p className="text-[10px] text-slate-400 italic border-t border-slate-100 pt-2 font-medium">
                              Nota: {msg.deadline.note}
                            </p>
                          )}

                          {/* Recalculate Date selector inline */}
                          {editingDeadlineIdx === idx && (
                            <div className="mt-3 p-2 bg-white rounded-lg border border-slate-100 flex flex-col gap-2 shadow-sm">
                              <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Início da Compra / Recebimento</label>
                              <div className="flex gap-2">
                                <input 
                                  type="date" 
                                  value={customDate}
                                  onChange={(e) => setCustomDate(e.target.value)}
                                  className="border border-slate-200 text-xs rounded p-1 w-full focus:ring-1 focus:ring-[#002147] outline-none" 
                                />
                                <button 
                                  onClick={() => submitRecalculation(idx, msg.deadline!)}
                                  className="bg-[#002147] text-white text-[10px] font-semibold px-2.5 rounded hover:bg-opacity-90"
                                >
                                  Gravar
                                </button>
                              </div>
                            </div>
                          )}

                          {/* Tool box action buttons */}
                          <div className="flex gap-2 mt-4 flex-wrap">
                            <button 
                              onClick={() => handleRecalculate(idx, msg.deadline!)}
                              className="text-[11px] font-semibold text-[#002147] bg-[#E7F1FF] hover:bg-opacity-80 px-2.5 py-1 rounded-lg transition-colors border border-transparent inline-flex items-center gap-1"
                            >
                              {recalculatingIdx === idx ? (
                                <RefreshCw className="w-3 h-3 animate-spin" />
                              ) : (
                                "Corrigir data"
                              )}
                            </button>
                            <button
                              onClick={() => onSaveCase(msg.deadline)}
                              className="text-[11px] font-semibold text-[#002147] bg-[#E7F1FF] hover:bg-opacity-80 px-2.5 py-1 rounded-lg transition-colors border border-transparent"
                            >
                              Salvar na lista
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Clarifying information lists */}
                      {!isUser && msg.questions && msg.questions.length > 0 && (
                        <div className="border-t border-slate-100 pt-3">
                          <h4 className="font-bold text-[#002147] text-xs mb-2">Preciso confirmar algumas informações para continuarmos:</h4>
                          <ul className="list-disc pl-4 space-y-1 text-[#002147] text-xs font-semibold">
                            {msg.questions.map((quest, qidx) => (
                              <li key={qidx}>{quest}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Concluding suggestion text */}
                      {!isUser && msg.stepTitle && (
                        <p className="text-xs text-slate-500 italic mt-2">{msg.suggestiveText}</p>
                      )}

                      {/* TEMPLATE NOTIFICATION CONTEST LETTER CARD */}
                      {!isUser && msg.templateLetter && (
                        <div className="bg-[#f0f4f8] rounded-xl border border-slate-200 p-4 mt-2">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-[#002147]">Mensagem Formal Pronta</span>
                            <button
                              onClick={() => copyToClipboard(msg.templateLetter || "", idx)}
                              className="text-xs font-semibold text-[#002147] hover:text-slate-600 inline-flex items-center gap-1 bg-white px-2 py-1 rounded border border-slate-200 shadow-sm"
                            >
                              {copiedIndex === idx ? (
                                <><Check className="w-3 h-3 text-emerald-600" /> Copiado</>
                              ) : (
                                <><Clipboard className="w-3 h-3" /> Copiar Texto</>
                              )}
                            </button>
                          </div>
                          <pre className="text-slate-700 text-xs leading-relaxed whitespace-pre-wrap font-sans bg-white border border-slate-100 p-3 rounded-lg max-h-60 overflow-y-auto">
                            {msg.templateLetter}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}

        {/* Loading Spinner bubble */}
        {isLoading && (
          <div className="flex w-full justify-start pr-12">
            <div className="bg-[#ffffff] border border-slate-200 text-slate-800 rounded-2xl rounded-tl-[4px] p-4 shadow-[0px_2px_4px_rgba(0,33,71,0.02)]">
              <div className="flex items-center gap-3">
                <div className="bg-[#aec7f6]/20 p-1.5 rounded-lg text-[#002147]">
                  <GavelIcon className="w-4 h-4 animate-bounce text-[#002147]" />
                </div>
                <div className="space-y-1">
                  <span className="text-xs text-slate-600 font-medium block">Advogado de Bolso analisando CDC...</span>
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-[#001b3d] rounded-full animate-bounce"></span>
                    <span className="w-1.5 h-1.5 bg-[#001b3d] rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                    <span className="w-1.5 h-1.5 bg-[#001b3d] rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef}></div>
      </div>

      {/* Suggested Quick Reply Action Chips (Bottom) */}
      {chatHistory.length > 0 && !isLoading && (
        <div className="fixed bottom-20 left-0 w-full px-4 z-30" id="chat-quick-replies">
          <div className="max-w-[1100px] mx-auto flex flex-wrap justify-end gap-2 pr-2" id="chips-row">
            {/* Contextual replies matching the last assistant message */}
            {(() => {
              const lastAsst = [...chatHistory].reverse().find(m => m.sender === "assistant");
              const replies = lastAsst?.quickReplies && lastAsst.quickReplies.length > 0
                ? lastAsst.quickReplies 
                : ["Preparar mensagem", "Continuar orientação", "Fazer outra pergunta"];
              
              return replies.map((chip, cidx) => (
                <button
                  key={cidx}
                  onClick={() => onSendMessage(chip)}
                  className="bg-white hover:bg-[#E7F1FF] text-xs font-semibold text-[#002147] border border-[#002147] rounded-full px-3 py-1.5 shadow-[0px_2px_4px_rgba(0,33,71,0.02)] transition-all cursor-pointer"
                >
                  {chip}
                </button>
              ));
            })()}
          </div>
        </div>
      )}

      {/* Main chat entry input bar */}
      <div className="fixed bottom-14 left-0 w-full bg-[#fbf9f8] border-t border-slate-200 p-3 z-40" id="chat-input-bar">
        <div className="max-w-[1100px] mx-auto flex items-center gap-2" id="input-row">
          <div className="relative flex-1 bg-white rounded-full border border-slate-300 flex items-center overflow-hidden focus-within:border-[#002147] focus-within:ring-2 focus-within:ring-[#E7F1FF] transition-all">
            <button 
              onClick={() => alert("Simulação: Envie faturas ou fotos de defeitos para analisar.")}
              className="p-3 text-slate-500 hover:text-[#002147] transition-colors"
              title="Anexar arquivos"
            >
              <Paperclip className="w-5 h-5" />
            </button>
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Digite sua dúvida ou responda ao advogado..."
              className="w-full bg-transparent border-none py-3 px-1 text-sm text-slate-800 placeholder-slate-400 focus:outline-none outline-none focus:ring-0"
              disabled={isLoading}
              id="chat-text-input-box"
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !inputText.trim()}
              className={`p-2.5 rounded-full mr-1.5 focus:outline-none transition-all flex items-center justify-center ${
                inputText.trim() && !isLoading 
                  ? "bg-[#002147] text-[#aec7f6] hover:scale-105" 
                  : "bg-slate-50 text-slate-300"
              }`}
              id="send-button-click"
            >
              <Send className="w-4 h-4 fill-current" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Inline mini helper svg component representing a gavel
function GavelIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      viewBox="0 0 24 24"
      {...props}
    >
      <path d="m14 13-1.5-1.5" />
      <path d="m18 17-1.5-1.5" />
      <path d="m11 10-6.6 6.6a1 1 0 0 0 0 1.4l2.1 2.1a1 1 0 0 0 1.4 0l6.6-6.6" />
      <path d="M12.5 5.5 13 6" />
      <path d="m15 3 6.5 6.5L16 15l-6.5-6.5z" />
    </svg>
  );
}
