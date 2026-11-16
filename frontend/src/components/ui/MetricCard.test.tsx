import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MetricCard } from "./MetricCard";
import { StatusBadge } from "./StatusBadge";

describe("MetricCard", () => {
  it("affiche libellé et valeur", () => {
    render(<MetricCard label="Attaques détectées" value="12" />);
    expect(screen.getByRole("article", { name: "Attaques détectées" })).toHaveTextContent("12");
  });

  it("n'invente jamais 0 pour une valeur absente", () => {
    render(<MetricCard label="ASR" value={null} placeholder="Évaluation à venir" />);
    expect(screen.getByText("Évaluation à venir")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("affiche un tiret par défaut quand la valeur est absente", () => {
    render(<MetricCard label="ASR" value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("accompagne un statut de son libellé", () => {
    render(<MetricCard label="Service IA" value="OK" badge={<StatusBadge status="UP" />} />);
    expect(screen.getByText("Opérationnel")).toBeInTheDocument();
  });
});
