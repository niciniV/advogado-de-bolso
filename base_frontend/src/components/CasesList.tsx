import React, { useState } from "react";
import { Search, ShoppingBag, Receipt, Truck, Gavel, Calendar, Mail, ChevronRight, Plus, Trash2, MoreHorizontal, Edit3, AlertTriangle } from "lucide-react";
import { Case } from "../types";

interface CasesListProps {
  cases: Case[];
  onSelectCase: (caseId: string) => void;
  onNewConsultation: () => void;
  onDeleteCase: (caseId: string) => void;
  onRenameCase: (caseId: string, newTitle: string) => void;
}

export default function CasesList({
  cases,
  onSelectCase,
  onNewConsultation,
  onDeleteCase,
  onRenameCase
}: CasesListProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [renameCaseId, setRenameCaseId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");

  const filteredCases = cases.filter(c =>
    c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.lastMessage.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getIconElement = (iconName: Case["iconName"]) => {
    switch (iconName) {
      case "shopping_bag":
        return <ShoppingBag className="w-5 h-5 text-[#002147]" />;
      case "receipt_long":
        return <Receipt className="w-5 h-5 text-slate-600" />;
      case "local_shipping":
        return <Truck className="w-5 h-5 text-slate-600" />;
      default:
        return <Gavel className="w-5 h-5 text-slate-600" />;
    }
  };

  const getIconBg = (iconName: Case["iconName"]) => {
    return iconName === "shopping_bag" ? "bg-[#d9e3f1]" : "bg-[#e4e2e1]";
  };

  const handleApplyRename = () => {
    if (renameCaseId && renameTitle.trim()) {
      onRenameCase(renameCaseId, renameTitle.trim());
      setRenameCaseId(null);
    }
  };

  const handleApplyDelete = () => {
    if (deleteConfirmId) {
      onDeleteCase(deleteConfirmId);
      setDeleteConfirmId(null);
    }
  };

  return (
    <div className="flex flex-col gap-5" id="cases-list-view">
      {/* Click outside to close helper */}
      {openMenuId !== null && (
        <div 
          className="fixed inset-0 z-20 cursor-default bg-transparent" 
          onClick={() => setOpenMenuId(null)}
        />
      )}

      {/* Search Header layout matching mockup */}
      <div className="relative w-full" id="cases-search-container">
        <span className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
          <Search className="h-4 w-4 text-slate-400" />
        </span>
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Pesquisar nos seus casos e consultas..."
          className="w-full bg-white border border-slate-200 rounded-xl py-3 pl-11 pr-4 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-[#002147] transition-all"
        />
      </div>

      {/* Main List Grid */}
      <div className="flex flex-col gap-3" id="cases-container-list">
        {filteredCases.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl border border-dotted border-slate-200" id="no-cases-state">
            <p className="text-slate-400 text-sm">Nenhum caso ou consulta cadastrado.</p>
            <button
              onClick={onNewConsultation}
              className="mt-3 text-xs font-semibold text-[#002147] bg-[#E7F1FF] px-4 py-2 rounded-lg"
            >
              Iniciar primeira consulta
            </button>
          </div>
        ) : (
          filteredCases.map((c) => (
            <div
              key={c.id}
              className="group relative flex flex-row items-center justify-between p-4 bg-white rounded-xl hover:bg-slate-50 border border-slate-100 shadow-[0px_2px_4px_rgba(0,33,71,0.02)] transition-all overflow-visible"
              id={`case-card-${c.id}`}
            >
              {/* Clicking case details */}
              <div 
                onClick={() => onSelectCase(c.id)}
                className="flex flex-row items-start flex-1 cursor-pointer min-w-0 pr-4"
              >
                {/* Icon Circle */}
                <div className={`flex-shrink-0 w-12 h-12 rounded-full ${getIconBg(c.iconName)} flex items-center justify-center mr-4`}>
                  {getIconElement(c.iconName)}
                </div>

                {/* Text Snippets */}
                <div className="flex-grow min-w-0">
                  <h3 className="font-semibold text-slate-900 group-hover:text-[#002147] transition-colors truncate text-sm mb-1">
                    {c.title}
                  </h3>
                  <p className="text-xs text-slate-500 truncate mb-2">
                    {c.lastMessage}
                  </p>

                  {/* Badges calculated or ready templates */}
                  {c.tagText && (
                    <div className="inline-flex items-center px-2 py-1 rounded-full border border-[#002147] bg-white text-[#002147] font-semibold text-[10px]">
                      {c.tagText === "Prazo calculado" ? (
                        <>
                          <Calendar className="w-3 h-3 mr-1 text-[#002147]" />
                          Prazo estimado ativo
                        </>
                      ) : (
                        <>
                          <Mail className="w-3 h-3 mr-1 text-[#002147]" />
                          Mensagem pronta
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Action Buttons Container to prevent layout jumps or overlap */}
              <div className="flex items-center gap-2 md:gap-3 flex-shrink-0 relative">
                <span className="text-xs font-bold text-[#002147] block pr-1">
                  {c.date}
                </span>

                {/* 3-dots Menu trigger */}
                <div className="relative">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenMenuId(openMenuId === c.id ? null : c.id);
                    }}
                    className="p-1.5 hover:bg-slate-100 text-slate-500 hover:text-[#002147] rounded-lg transition-colors cursor-pointer"
                    title="Menu de ações"
                  >
                    <MoreHorizontal className="w-5 h-5" />
                  </button>

                  {/* Dropdown Menu matching the mockup perfectly */}
                  {openMenuId === c.id && (
                    <div className="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-[0px_4px_20px_rgba(0,33,71,0.12)] border border-slate-100 py-1.5 z-30 animate-in fade-in slide-in-from-top-2 duration-100">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuId(null);
                          onSelectCase(c.id);
                        }}
                        className="w-full text-left px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-[#002147] flex items-center justify-between"
                      >
                        <span>Abrir caso</span>
                      </button>
                      
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuId(null);
                          setRenameCaseId(c.id);
                          setRenameTitle(c.title);
                        }}
                        className="w-full text-left px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-[#002147] flex items-center justify-between border-t border-slate-100"
                      >
                        <span>Renomear</span>
                      </button>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuId(null);
                          setDeleteConfirmId(c.id);
                        }}
                        className="w-full text-left px-4 py-2.5 text-xs font-bold text-red-600 hover:bg-red-50 flex items-center justify-between border-t border-slate-100"
                      >
                        <span>Excluir consulta</span>
                      </button>
                    </div>
                  )}
                </div>

                {/* Direct Arrow element */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectCase(c.id);
                  }}
                  className="p-1 text-slate-400 group-hover:text-[#002147] hover:bg-slate-100 rounded-lg transition-all cursor-pointer"
                  title="Abrir detalhes"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>

            </div>
          ))
        )}
      </div>

      {/* Floating Action Button for mobile layout context */}
      <button
        onClick={onNewConsultation}
        className="fixed bottom-20 right-4 md:right-auto md:left-1/2 md:translate-x-[480px] md:bottom-8 z-40 bg-[#002147] text-white w-14 h-14 rounded-full shadow-[0px_8px_16px_rgba(0,33,71,0.15)] flex items-center justify-center hover:bg-[#2d476f] transition-all cursor-pointer hover:scale-105 active:scale-95"
        id="cases-fab-plus"
        title="Nova Consulta"
      >
        <Plus className="w-6 h-6" />
      </button>

      {/* Thematic Confirmation Modal: Excluir Consulta */}
      {deleteConfirmId && (
        <div className="fixed inset-0 bg-[#000a1e]/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl border border-slate-100 animate-in fade-in zoom-in duration-150">
            <div className="flex items-center gap-3 mb-4 text-red-600">
              <div className="bg-red-100 p-2.5 rounded-full">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <h4 className="font-bold text-slate-900 text-base leading-tight">
                Excluir Consulta de Forma Definitiva?
              </h4>
            </div>

            <div className="text-xs text-slate-600 space-y-3 leading-relaxed mb-6">
              <p>
                Esta ação é irreversível. O histórico de mensagens completo, além de todos os prazos calculados e contra-notificações estruturadas para o caso <strong className="text-slate-900">"{cases.find(c => c.id === deleteConfirmId)?.title}"</strong> serão apagados de maneira definitiva e segura do armazenamento local do sistema.
              </p>
              <p className="font-semibold text-red-600 bg-red-50 p-2.5 rounded-lg border border-red-100">
                Aviso: Uma vez excluído, você não poderá restaurar ou consultar a fundamentação legal sugerida para este caso novamente.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setDeleteConfirmId(null)}
                className="flex-1 text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors font-semibold text-xs py-3 rounded-xl cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleApplyDelete}
                className="flex-1 bg-red-600 text-white hover:bg-red-700 transition-colors font-semibold text-xs py-3 rounded-xl shadow-md cursor-pointer"
              >
                Sim, Excluir
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Thematic Rename Case Modal */}
      {renameCaseId && (
        <div className="fixed inset-0 bg-[#000a1e]/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl border border-slate-100 animate-in fade-in zoom-in duration-150">
            <div className="flex items-center gap-3 mb-4 text-[#002147]">
              <div className="bg-[#E7F1FF] p-2.5 rounded-full">
                <Edit3 className="w-5 h-5 text-[#002147]" />
              </div>
              <h4 className="font-bold text-[#002147] text-base">
                Renomear Caso ou Consulta
              </h4>
            </div>

            <div className="mb-5">
              <label className="block text-[10px] uppercase font-bold text-slate-400 tracking-wider mb-2">
                Título do Caso / Assunto
              </label>
              <input
                type="text"
                value={renameTitle}
                onChange={(e) => setRenameTitle(e.target.value)}
                className="w-full border border-slate-200 rounded-xl py-3 px-4 text-sm text-slate-800 focus:outline-none focus:border-[#002147] focus:ring-1 focus:ring-[#002147] transition-all bg-[#fbfbfb]"
                placeholder="Ex: Celular comprando online..."
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleApplyRename();
                  if (e.key === "Escape") setRenameCaseId(null);
                }}
              />
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setRenameCaseId(null)}
                className="flex-1 text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors font-semibold text-xs py-3 rounded-xl cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleApplyRename}
                className="flex-1 bg-[#002147] text-white hover:bg-[#1a385f] transition-colors font-semibold text-xs py-3 rounded-xl shadow-md cursor-pointer"
              >
                Salvar Alteração
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
