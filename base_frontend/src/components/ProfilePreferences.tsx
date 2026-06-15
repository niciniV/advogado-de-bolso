import React, { useState } from "react";
import { Shield, CheckCircle, Database, Lock, Gavel, ChevronRight, Settings, Sliders, Check } from "lucide-react";
import { AppPreferences, SystemStatus } from "../types";

interface ProfilePreferencesProps {
  preferences: AppPreferences;
  onUpdatePreferences: (updated: Partial<AppPreferences>) => void;
}

export default function ProfilePreferences({
  preferences,
  onUpdatePreferences
}: ProfilePreferencesProps) {
  const [activeModal, setActiveModal] = useState<"privacy" | "legal" | null>(null);

  const handleStyleChange = (style: 'simples' | 'detalhado' | 'firme') => {
    onUpdatePreferences({ responseStyle: style });
  };

  return (
    <div className="flex flex-col gap-6" id="profile-preferences-view">
      {/* Response Style Radio Settings */}
      <div>
        <h3 className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-2 px-2 flex items-center gap-1">
          <Sliders className="w-3.5 h-3.5" /> Preferências do Assistente
        </h3>
        <div className="bg-white rounded-xl shadow-[0px_2px_4px_rgba(0,33,71,0.05)] border border-slate-100 p-4 space-y-3" id="preferences-style-group">
          {/* Radio items */}
          {[
            { id: "simples", title: "Simples", subtitle: "Linguagem acessível e direta" },
            { id: "detalhado", title: "Detalhado", subtitle: "Análises completas com citações" },
            { id: "firme", title: "Mais firme", subtitle: "Tom assertivo para negociações" }
          ].map((style) => {
            const isSelected = preferences.responseStyle === style.id;
            return (
              <label
                key={style.id}
                onClick={() => handleStyleChange(style.id as any)}
                className={`relative flex items-center p-3.5 rounded-xl cursor-pointer transition-all border ${
                  isSelected
                    ? "border-2 border-[#002147] bg-[#fbfbfb] shadow-sm"
                    : "border-slate-200 hover:bg-slate-50"
                }`}
              >
                <div className="flex-grow pr-4">
                  <span className="block font-semibold text-slate-800 text-sm">{style.title}</span>
                  <span className="block text-xs text-slate-400 mt-0.5">{style.subtitle}</span>
                </div>
                <div
                  className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all ${
                    isSelected ? "border-[#002147]" : "border-slate-300"
                  }`}
                >
                  {isSelected && <div className="w-2.5 h-2.5 rounded-full bg-[#002147]" />}
                </div>
              </label>
            );
          })}
        </div>
      </div>

      {/* System status layout exactly reflecting mockup */}
      <div>
        <h3 className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-2 px-2">Status do Sistema</h3>
        <div className="bg-white rounded-xl shadow-[0px_2px_4px_rgba(0,33,71,0.05)] border border-slate-100 p-4 space-y-3" id="system-status-indicator">
          
          <div className="flex items-center gap-3 bg-[#d0e9d6] border border-[#b4ccba] rounded-lg p-2.5">
            <Database className="w-5 h-5 text-[#0b2014]" />
            <span className="text-xs text-[#0b2014] flex-grow font-semibold">Base de conhecimento ativa</span>
            <div className="w-2.5 h-2.5 rounded-full bg-[#002147] animate-pulse"></div>
          </div>

          <div className="flex items-center gap-3 bg-[#d0e9d6] border border-[#b4ccba] rounded-lg p-2.5">
            <span className="font-bold text-center text-sm w-5 h-5 leading-none text-[#0b2014]">“ ”</span>
            <span className="text-xs text-[#0b2014] flex-grow font-semibold">Citações e Fundamentação ativada</span>
            <div className="w-2.5 h-2.5 rounded-full bg-[#002147] animate-pulse" style={{ animationDelay: "300ms" }}></div>
          </div>

          <div className="flex items-center gap-3 bg-[#d0e9d6] border border-[#b4ccba] rounded-lg p-2.5">
            <Shield className="w-5 h-5 text-[#0b2014]" />
            <span className="text-xs text-[#0b2014] flex-grow font-semibold">Revisão de segurança ativa</span>
            <div className="w-2.5 h-2.5 rounded-full bg-[#002147] animate-pulse" style={{ animationDelay: "600ms" }}></div>
          </div>

        </div>
      </div>

      {/* Interactive Information Disclosure link bars */}
      <div className="bg-white rounded-xl shadow-[0px_2px_4px_rgba(0,33,71,0.05)] border border-slate-100 overflow-hidden" id="disclosure-links-container">
        
        <button
          onClick={() => setActiveModal("privacy")}
          className="w-full flex items-center justify-between p-4 border-b border-slate-100 hover:bg-slate-50 transition-colors text-left group"
        >
          <div className="flex items-center gap-3">
            <Lock className="w-4 h-4 text-slate-400 group-hover:text-[#002147] transition-colors" />
            <span className="text-xs font-semibold text-slate-700 group-hover:text-[#002147]">Aviso de Privacidade</span>
          </div>
          <ChevronRight className="w-4 h-4 text-slate-400" />
        </button>

        <button
          onClick={() => setActiveModal("legal")}
          className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors text-left group"
        >
          <div className="flex items-center gap-3">
            <Gavel className="w-4 h-4 text-slate-400 group-hover:text-[#002147] transition-colors" />
            <span className="text-xs font-semibold text-slate-700 group-hover:text-[#002147]">Aviso Legal</span>
          </div>
          <ChevronRight className="w-4 h-4 text-slate-400" />
        </button>

      </div>

      {/* Disclosure overlays inside standard DOM overlays to circumvent iframe limitations */}
      {activeModal && (
        <div className="fixed inset-0 bg-[#000a1e]/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-lg border border-slate-100 animate-in fade-in zoom-in duration-150">
            <div className="flex items-center gap-2 mb-4 text-[#002147]">
              {activeModal === "privacy" ? <Lock className="w-5 h-5" /> : <Gavel className="w-5 h-5" />}
              <h4 className="font-bold text-[#002147] text-base">
                {activeModal === "privacy" ? "Aviso de Privacidade" : "Aviso Legal de Uso"}
              </h4>
            </div>

            <div className="text-xs text-slate-600 space-y-3 leading-relaxed max-h-60 overflow-y-auto">
              {activeModal === "privacy" ? (
                <>
                  <p><strong>Privacidade e Sigilo:</strong> O Advogado de Bolso coleta as informações relatadas em suas consultas apenas para aprimoramento local com a inteligência artificial, não compartilhando dados sensíveis com terceiros.</p>
                  <p>Nenhuma informação como nome completo, CPF, números de cartão de crédito ou links bancários é exigida. Evite digitar dados estritamente confidenciais nas conversas.</p>
                  <p>Você pode excluir suas consultas salvas a qualquer momento na tabela de casos clicando no botão de exclusão lixeira, removendo definitivamente todo o histórico registrado localmente.</p>
                </>
              ) : (
                <>
                  <p><strong>Isenção de Responsabilidade Jurídica Primária:</strong> O Advogado de Bolso é um consultor demonstrativo de inteligência artificial automatizado baseado no Código de Defesa do Consumidor brasileiro.</p>
                  <p>Os cálculos de prazos, notificações pré-confeccionadas e análises geradas consistem em meras sugestões informativas aproximadas. Eles não dispensam e de forma nenhuma substituem a assessoria jurídica formal e atendimento de um advogado profissional devidamente inscrito na OAB ou da Defensoria Pública.</p>
                  <p>Ao utilizar os modelos de contra-notificação e sugestões, o usuário do sistema declara-se ciente que a responsabilidade final pelo envio, veracidade de fatos relatados e termos pactuados é integralmente de si mesmo.</p>
                </>
              )}
            </div>

            <button
              onClick={() => setActiveModal(null)}
              className="mt-6 w-full bg-[#002147] text-white hover:bg-opacity-90 font-bold text-xs py-2.5 rounded-xl"
            >
              Entendido e Aceito
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
