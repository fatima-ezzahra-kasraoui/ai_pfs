import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { STATUS, StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each(Object.entries(STATUS))("%s affiche toujours un libellé texte", (code, def) => {
    render(<StatusBadge status={code} />);
    expect(screen.getByText(def.label)).toBeInTheDocument();
  });

  it("n'est pas porté par la couleur seule : le texte est dans le DOM, l'icône est décorative", () => {
    const { container } = render(<StatusBadge status="BLOCK" />);
    expect(container).toHaveTextContent("Bloqué");
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("accepte la casse minuscule", () => {
    render(<StatusBadge status="allow" />);
    expect(screen.getByText("Autorisé")).toBeInTheDocument();
  });

  it("affiche un code inconnu tel quel", () => {
    render(<StatusBadge status="QUARANTINE" />);
    expect(screen.getByText("QUARANTINE")).toBeInTheDocument();
  });

  it.each([null, undefined])("affiche « Inconnu » quand le statut est %s", (status) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText("Inconnu")).toBeInTheDocument();
  });
});
