import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderApp } from "../../test/utils";
import { NAV_ITEMS } from "./navigation";

describe("MainLayout", () => {
  it("expose 7 routes protégées", () => {
    expect(NAV_ITEMS).toHaveLength(7);
  });

  // « /lab » n'est plus un placeholder (AS-S1-024) : voir pages/AttackSimulation.test.tsx.
  it.each([
    ["/threats", "Threat Monitoring"],
    ["/approvals", "Approval Center"],
  ])("la route %s est accessible", async (path, title) => {
    renderApp(path, {});
    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Cette page sera disponible");
  });

  it("la Sidebar liste chaque section et le lien actif est marqué", async () => {
    renderApp("/lab", {});
    const nav = await screen.findByRole("navigation", { name: "Navigation principale" });
    for (const item of NAV_ITEMS) expect(within(nav).getByRole("link", { name: item.label })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Attack Simulation Lab" })).toHaveAttribute("aria-current", "page");
  });

  it("la Sidebar est réductible sans perdre les libellés (accessibles)", async () => {
    const user = userEvent.setup();
    renderApp("/lab", {});
    const toggle = await screen.findByRole("button", { name: "Réduire le menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await user.click(toggle);
    const reopen = screen.getByRole("button", { name: "Développer le menu" });
    expect(reopen).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("link", { name: "Threat Monitoring" })).toBeInTheDocument();
  });

  it("le Header montre l'identité de la session", async () => {
    renderApp("/lab", {});
    expect(await screen.findByText("analyste")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Déconnexion/ })).toBeInTheDocument();
  });
});
