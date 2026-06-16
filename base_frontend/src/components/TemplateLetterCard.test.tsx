import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TemplateLetterCard from "./TemplateLetterCard";

describe("TemplateLetterCard", () => {
  const letter = "Prezados,\n\nSolicito a devolucao do produto conforme CDC Art. 49.";

  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
  });

  it("renders the default title", () => {
    render(<TemplateLetterCard letter={letter} />);
    expect(screen.getByText("Mensagem Formal Pronta")).toBeInTheDocument();
  });

  it("renders the letter body expanded (not collapsed) by default", () => {
    render(<TemplateLetterCard letter={letter} />);
    expect(screen.getByText(/Solicito a devolucao/)).toBeInTheDocument();
  });

  it("renders the assunto in a separate, darker-blue box when provided", () => {
    render(
      <TemplateLetterCard
        letter={letter}
        assunto="Notificacao de Desistencia de Compra"
      />,
    );
    const assuntoBox = screen.getByTestId("template-letter-assunto");
    expect(assuntoBox).toBeInTheDocument();
    expect(assuntoBox).toHaveTextContent("Notificacao de Desistencia de Compra");
    expect(assuntoBox).toHaveTextContent("Assunto");
  });

  it("hides the assunto box when no subject is provided", () => {
    render(<TemplateLetterCard letter={letter} />);
    expect(screen.queryByTestId("template-letter-assunto")).not.toBeInTheDocument();
  });

  it("hides the assunto box when the subject is an empty string", () => {
    render(<TemplateLetterCard letter={letter} assunto="" />);
    expect(screen.queryByTestId("template-letter-assunto")).not.toBeInTheDocument();
  });

  it("hides the assunto box when the subject is only whitespace", () => {
    render(<TemplateLetterCard letter={letter} assunto="   " />);
    expect(screen.queryByTestId("template-letter-assunto")).not.toBeInTheDocument();
  });

  it("copies just the subject (no 'Assunto:' prefix) when the subject copy button is clicked", () => {
    render(
      <TemplateLetterCard
        letter={letter}
        assunto="Notificacao de Desistencia de Compra"
      />,
    );
    const copyAssunto = screen.getByRole("button", {
      name: /Copiar assunto da mensagem formal/i,
    });
    fireEvent.click(copyAssunto);
    expect(writeText).toHaveBeenCalledWith("Notificacao de Desistencia de Compra");
  });

  it("copies the body when the body copy button is clicked", () => {
    render(<TemplateLetterCard letter={letter} />);
    const copyBody = screen.getByRole("button", {
      name: /Copiar corpo da mensagem formal/i,
    });
    fireEvent.click(copyBody);
    expect(writeText).toHaveBeenCalledWith(letter);
  });

  it("shows the Copiado confirmation on the subject button after copying", async () => {
    render(
      <TemplateLetterCard
        letter={letter}
        assunto="Notificacao de Desistencia de Compra"
      />,
    );
    const copyAssunto = screen.getByRole("button", {
      name: /Copiar assunto da mensagem formal/i,
    });
    fireEvent.click(copyAssunto);
    expect(await screen.findByText("Copiado")).toBeInTheDocument();
  });

  it("parses **bold** inside the letter body", () => {
    render(
      <TemplateLetterCard letter="Obrigado, **cliente**, pela preferencia." />,
    );
    expect(screen.getByText("cliente").tagName).toBe("STRONG");
  });

  it("accepts a custom card title", () => {
    render(<TemplateLetterCard letter={letter} label="Carta para a loja" />);
    expect(screen.getByText("Carta para a loja")).toBeInTheDocument();
  });
});
