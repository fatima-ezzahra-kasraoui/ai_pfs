import { describe, expect, it } from "vitest";
import { DASH, formatCount, formatDateTime, formatMs, formatNumber, formatPercent } from "./format";

describe("format", () => {
  it("une valeur absente s'affiche « — », jamais 0", () => {
    for (const f of [formatCount, formatPercent, formatNumber, formatMs]) {
      expect(f(null)).toBe(DASH);
      expect(f(undefined)).toBe(DASH);
    }
  });
  it("zéro est une vraie valeur", () => {
    expect(formatPercent(0)).toBe("0,0 %");
    expect(formatNumber(0)).toBe("0,000");
    expect(formatMs(0)).toBe("0,00 ms");
    expect(formatCount(0)).toBe("0");
  });
  it("formate à la française", () => {
    expect(formatPercent(0.285)).toMatch(/^28,[45] %$/);
    expect(formatNumber(0.9876, 2)).toBe("0,99");
    expect(formatMs(1.234)).toBe("1,23 ms");
    expect(formatCount(1234).replace(/\s/g, "")).toBe("1234");
  });
  it("une date invalide est renvoyée telle quelle", () => {
    expect(formatDateTime("pas une date")).toBe("pas une date");
    expect(formatDateTime("2026-11-11T10:00:00Z")).not.toBe("2026-11-11T10:00:00Z");
  });
});
