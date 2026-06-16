import { useState } from "react";
import { Clipboard, Check } from "lucide-react";
import { parseInlineMarkdown } from "../markdown";

interface TemplateLetterCardProps {
  letter: string;
  assunto?: string;
  label?: string;
}

export default function TemplateLetterCard({
  letter,
  assunto,
  label = "Mensagem Formal Pronta",
}: TemplateLetterCardProps) {
  const [copiedAssunto, setCopiedAssunto] = useState(false);
  const [copiedBody, setCopiedBody] = useState(false);

  const trimmedAssunto = assunto?.trim() ?? "";
  const hasAssunto = trimmedAssunto.length > 0;

  const handleCopy = async (text: string, kind: "assunto" | "body") => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard API can throw in non-secure contexts; the user can still
      // select and copy the text manually.
    }
    if (kind === "assunto") {
      setCopiedAssunto(true);
      setTimeout(() => setCopiedAssunto(false), 2000);
    } else {
      setCopiedBody(true);
      setTimeout(() => setCopiedBody(false), 2000);
    }
  };

  return (
    <div
      className="bg-[#f0f4f8] rounded-xl border border-slate-200 p-4 mt-2"
      id="template-letter-card"
    >
      <div className="flex justify-between items-center mb-3">
        <span className="text-[10px] font-bold uppercase tracking-wider text-[#002147]">
          {label}
        </span>
      </div>

      {hasAssunto && (
        <div
          className="bg-[#002147] text-white rounded-lg p-3 mb-3 flex justify-between items-center gap-3"
          id="template-letter-assunto"
          data-testid="template-letter-assunto"
        >
          <div className="flex-1 min-w-0">
            <div className="text-[10px] uppercase tracking-wider opacity-70 mb-1">
              Assunto
            </div>
            <div className="text-sm font-semibold break-words">
              {trimmedAssunto}
            </div>
          </div>
          <button
            type="button"
            onClick={() => handleCopy(trimmedAssunto, "assunto")}
            aria-label="Copiar assunto da mensagem formal"
            className="text-[11px] font-semibold text-[#002147] bg-white hover:bg-slate-100 px-2.5 py-1 rounded border border-slate-200 shadow-sm transition-colors flex items-center gap-1 flex-shrink-0"
          >
            {copiedAssunto ? (
              <>
                <Check className="w-3 h-3 text-emerald-600" /> Copiado
              </>
            ) : (
              <>
                <Clipboard className="w-3 h-3" /> Copiar
              </>
            )}
          </button>
        </div>
      )}

      <div className="relative">
        <button
          type="button"
          onClick={() => handleCopy(letter, "body")}
          aria-label="Copiar corpo da mensagem formal"
          className="absolute top-2 right-2 z-10 text-[10px] font-semibold text-[#002147] bg-white hover:bg-slate-100 px-2 py-1 rounded border border-slate-200 shadow-sm transition-colors flex items-center gap-1"
        >
          {copiedBody ? (
            <>
              <Check className="w-3 h-3 text-emerald-600" /> Copiado
            </>
          ) : (
            <>
              <Clipboard className="w-3 h-3" /> Copiar Texto
            </>
          )}
        </button>
        <pre
          id="template-letter-content"
          className="text-slate-700 text-xs leading-relaxed whitespace-pre-wrap font-sans bg-white border border-slate-100 p-3 pr-24 rounded-lg max-h-60 overflow-y-auto"
        >
          {parseInlineMarkdown(letter)}
        </pre>
      </div>
    </div>
  );
}
