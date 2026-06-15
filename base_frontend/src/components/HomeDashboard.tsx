import { Gavel, MessageSquare, ShieldAlert, Sparkles, ChevronRight, CheckCircle } from "lucide-react";
import { Case } from "../types";

interface HomeDashboardProps {
  cases: Case[];
  onStartConsultation: (initialPrompt?: string) => void;
  onSelectCase: (caseId: string) => void;
}

export default function HomeDashboard({
  cases,
  onStartConsultation,
  onSelectCase
}: HomeDashboardProps) {
  const activeCalculatedCases = cases.filter(c => c.tagText === "Prazo calculado" || c.tagText === "Mensagem pronta");

  const quickGuides = [
    {
      title: "Celular comprado online de que me arrependi",
      desc: "Calcule os 7 dias limites do seu direito de desistência.",
      prompt: "Comprei um celular online e me arrependi. Recebi ontem, mas a loja disse que não aceita devolução."
    },
    {
      title: "Cobrança duplicada no cartão",
      desc: "Recupere o valor pago indevidamente em dobro nos termos da lei.",
      prompt: "Fui cobrado duas vezes pelo mesmo produto na fatura do meu cartão."
    },
    {
      title: "Atraso injustificável na entrega",
      desc: "Exija cumprimento forçado ou cancelamento imediato do pedido.",
      prompt: "Minha compra online está com a entrega muito atrasada e a loja não dá respostas."
    }
  ];

  return (
    <div className="flex flex-col gap-6" id="dashboard-container">
      {/* Welcome Banner */}
      <div className="bg-radial from-[#001735] to-[#002147] text-white p-6 rounded-2xl shadow-sm relative overflow-hidden" id="welcome-banner">
        <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full blur-2xl pointer-events-none"></div>
        <div className="flex items-start gap-4">
          <div className="bg-white/10 p-3 rounded-xl backdrop-blur-md">
            <Gavel className="w-8 h-8 text-[#aec7f6]" />
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Advogado de Bolso</h2>
            <p className="text-sm text-slate-300 mt-1 max-w-md">
              Seu assistente de inteligência artificial de confiança especialista no Código de Defesa do Consumidor brasileiro.
            </p>
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => onStartConsultation()}
            className="bg-[#aec7f6] text-[#001b3d] text-sm font-semibold hover:bg-white transition-all px-4 py-2 rounded-xl flex items-center gap-2 shadow-sm"
          >
            <Sparkles className="w-4 h-4" /> Nova Consulta Inteligente
          </button>
        </div>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-2 gap-4" id="stats-grid">
        <div className="bg-white p-4 rounded-xl border border-slate-100 shadow-[0px_2px_4px_rgba(0,33,71,0.02)]">
          <span className="text-xs text-slate-500 font-medium uppercase tracking-wider block">Total de Casos</span>
          <span className="text-3xl font-bold text-[#002147] mt-1 block">{cases.length}</span>
          <div className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium mt-2">
            <CheckCircle className="w-3.5 h-3.5" /> Salvos com segurança
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-100 shadow-[0px_2px_4px_rgba(0,33,71,0.02)]">
          <span className="text-xs text-slate-500 font-medium uppercase tracking-wider block">Prazos Calculados</span>
          <span className="text-3xl font-bold text-[#002147] mt-1 block">{activeCalculatedCases.length}</span>
          <span className="text-xs text-amber-600 font-medium block mt-2">
            Prazos monitorados ativos
          </span>
        </div>
      </div>

      {/* Quick Launch Shortcuts */}
      <div>
        <h3 className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-3 px-2">Guias Rápidos e Dúvidas Comuns</h3>
        <div className="flex flex-col gap-3">
          {quickGuides.map((guide, idx) => (
            <button
              key={idx}
              onClick={() => onStartConsultation(guide.prompt)}
              className="w-full text-left bg-white p-4 rounded-xl border border-slate-100 hover:border-[#aec7f6] hover:shadow-[0px_4px_12px_rgba(0,33,71,0.04)] hover:bg-[#fcfdfe] transition-all flex items-center justify-between group"
            >
              <div className="flex-1 min-w-0 pr-4">
                <h4 className="font-semibold text-slate-800 text-sm group-hover:text-[#002147] truncate">{guide.title}</h4>
                <p className="text-xs text-slate-500 mt-0.5">{guide.desc}</p>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-[#002147] group-hover:translate-x-1 transition-all" />
            </button>
          ))}
        </div>
      </div>

      {/* Recent Activity */}
      {cases.length > 0 && (
        <div>
          <h3 className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-3 px-2">Atividade Recente</h3>
          <div className="bg-white rounded-xl shadow-[0px_2px_4px_rgba(0,33,71,0.02)] border border-slate-100 overflow-hidden">
            {cases.slice(0, 2).map((c) => (
              <button
                key={c.id}
                onClick={() => onSelectCase(c.id)}
                className="w-full text-left p-4 hover:bg-slate-50 flex items-center justify-between border-b last:border-b-0 border-slate-100 transition-colors"
              >
                <div className="flex-1 min-w-0 pr-4">
                  <h4 className="font-semibold text-[#002147] text-sm truncate">{c.title}</h4>
                  <p className="text-xs text-slate-500 mt-1 truncate">{c.lastMessage}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">{c.date}</span>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
