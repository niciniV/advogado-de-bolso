import { render, screen } from "@testing-library/react";
import { Fragment, type ReactElement, type ReactNode, isValidElement } from "react";
import { describe, expect, it } from "vitest";
import { fixUnclosedBold, parseInlineMarkdown } from "./markdown";

describe("fixUnclosedBold", () => {
  it("returns the input unchanged when there are no ** markers", () => {
    expect(fixUnclosedBold("plain text with no markers")).toBe("plain text with no markers");
  });

  it("returns the input unchanged when markers are balanced (even count)", () => {
    expect(fixUnclosedBold("**bold** and **more bold**")).toBe("**bold** and **more bold**");
  });

  it("removes a single trailing ** when the count is odd", () => {
    expect(fixUnclosedBold("**bold but never closed")).toBe("bold but never closed");
  });

  it("removes only the last ** when there is an odd count of markers", () => {
    expect(fixUnclosedBold("**first** and **second")).toBe("**first** and second");
  });

  it("removes a lonely ** at the end of the string", () => {
    expect(fixUnclosedBold("trailing text**")).toBe("trailing text");
  });

  it("removes a lonely ** at the start of the string", () => {
    expect(fixUnclosedBold("**leading text")).toBe("leading text");
  });

  it("removes a lone ** when the whole string is just **", () => {
    expect(fixUnclosedBold("**")).toBe("");
  });

  it("handles empty strings", () => {
    expect(fixUnclosedBold("")).toBe("");
  });
});

function renderToText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(renderToText).join("");
  if (isValidElement(node)) {
    const element = node as ReactElement<{ children?: ReactNode }>;
    if (element.type === "strong") return `<strong>${renderToText(element.props.children)}</strong>`;
    if (element.type === Fragment) return renderToText(element.props.children);
    return renderToText(element.props.children);
  }
  return "";
}

describe("parseInlineMarkdown", () => {
  it("renders a single bold segment wrapped in <strong>", () => {
    expect(renderToText(parseInlineMarkdown("Hello **world**!"))).toBe("Hello <strong>world</strong>!");
  });

  it("renders multiple bold segments", () => {
    expect(renderToText(parseInlineMarkdown("**a** and **b** end"))).toBe(
      "<strong>a</strong> and <strong>b</strong> end",
    );
  });

  it("strips an unclosed trailing ** and does not bold anything", () => {
    expect(renderToText(parseInlineMarkdown("this is **unclosed"))).toBe("this is unclosed");
  });

  it("only bolds the closed pair when one of two markers is unclosed", () => {
    expect(renderToText(parseInlineMarkdown("**first** then **unclosed"))).toBe(
      "<strong>first</strong> then unclosed",
    );
  });

  it("leaves plain text untouched", () => {
    expect(renderToText(parseInlineMarkdown("no markers here"))).toBe("no markers here");
  });

  it("returns null for an empty string", () => {
    expect(parseInlineMarkdown("")).toBeNull();
  });

  it("parses the example LLM response (mixed bold + paragraphs)", () => {
    const sample =
      "Voce tem direito de devolver o aparelho. Como a compra foi feita online (fora do estabelecimento comercial), voce esta protegido pelo **Direito de Arrependimento**, previsto no **Artigo 49 do Codigo de Defesa do Consumidor (CDC)**.\n\nDe acordo com a lei, voce tem o prazo de **7 dias corridos**, a contar do recebimento do produto, para desistir da compra.";
    const out = renderToText(parseInlineMarkdown(sample));
    expect(out).toContain("<strong>Direito de Arrependimento</strong>");
    expect(out).toContain("<strong>Artigo 49 do Codigo de Defesa do Consumidor (CDC)</strong>");
    expect(out).toContain("<strong>7 dias corridos</strong>");
    expect(screen.queryByText("Direito de Arrependimento")).toBeNull();
  });

  it("actually mounts <strong> in the DOM (smoke check)", () => {
    render(<p data-testid="host">{parseInlineMarkdown("texto **em destaque** aqui")}</p>);
    expect(screen.getByText("em destaque").tagName).toBe("STRONG");
    expect(screen.getByTestId("host").textContent).toBe("texto em destaque aqui");
  });
});
