import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CollapsibleSources from "./CollapsibleSources";

describe("CollapsibleSources", () => {
  it("renders the default label", () => {
    render(<CollapsibleSources content="Trecho de lei" />);
    expect(screen.getByText("Pesquisando Documentos")).toBeInTheDocument();
  });

  it("accepts a custom label", () => {
    render(<CollapsibleSources content="x" label="Documentos" />);
    expect(screen.getByText("Documentos")).toBeInTheDocument();
  });

  it("hides the content by default", () => {
    render(<CollapsibleSources content="Trecho de lei" />);
    expect(screen.queryByText("Trecho de lei")).not.toBeInTheDocument();
  });

  it("expands the content when the label is clicked", () => {
    render(<CollapsibleSources content="Trecho de lei" />);
    fireEvent.click(screen.getByRole("button", { name: /Pesquisando Documentos/i }));
    expect(screen.getByText("Trecho de lei")).toBeInTheDocument();
  });

  it("collapses the content when clicked a second time", () => {
    render(<CollapsibleSources content="Trecho de lei" />);
    const toggle = screen.getByRole("button", { name: /Pesquisando Documentos/i });
    fireEvent.click(toggle);
    expect(screen.getByText("Trecho de lei")).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.queryByText("Trecho de lei")).not.toBeInTheDocument();
  });

  it("parses **bold** inside the expanded content", () => {
    render(<CollapsibleSources content="texto **em destaque** aqui" />);
    fireEvent.click(screen.getByRole("button", { name: /Pesquisando Documentos/i }));
    expect(screen.getByText("em destaque").tagName).toBe("STRONG");
  });

  it("updates aria-expanded when toggled", () => {
    render(<CollapsibleSources content="x" />);
    const button = screen.getByRole("button", { name: /Pesquisando Documentos/i });
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
  });
});
