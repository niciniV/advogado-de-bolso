import { useState } from "react";
import { ChevronRight, HelpCircle } from "lucide-react";
import { parseInlineMarkdown } from "../markdown";

interface CollapsibleSourcesProps {
  content: string;
  label?: string;
}

export default function CollapsibleSources({
  content,
  label = "Pesquisando Documentos",
}: CollapsibleSourcesProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-t border-slate-100 pt-3" id="collapsible-sources">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-controls="collapsible-sources-content"
        className="flex items-center gap-1.5 text-[#002147] text-xs font-bold hover:underline focus:outline-none focus:ring-2 focus:ring-[#E7F1FF] rounded transition-colors"
      >
        <ChevronRight
          className={`w-3.5 h-3.5 transition-transform duration-200 ${
            open ? "rotate-90" : ""
          }`}
        />
        <HelpCircle className="w-4 h-4" />
        <span>{label}</span>
      </button>
      {open && (
        <p
          id="collapsible-sources-content"
          className="text-xs text-slate-600 leading-relaxed mt-2 whitespace-pre-wrap"
        >
          {parseInlineMarkdown(content)}
        </p>
      )}
    </div>
  );
}
