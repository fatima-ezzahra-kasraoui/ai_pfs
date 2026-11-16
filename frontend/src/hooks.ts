import { useCallback, useEffect, useState } from "react";

export type AsyncState<T> = { status: "loading" } | { status: "error"; error: unknown } | { status: "ready"; data: T };

/**
 * Charge une ressource, annule la requête au démontage et à chaque changement de dépendance, expose `reload`.
 * L'état « chargement » est dérivé (le résultat mémorisé ne vaut que pour la clé courante) : aucun setState synchrone.
 * Les dépendances doivent être sérialisables en JSON.
 */
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, deps: readonly unknown[] = []): { state: AsyncState<T>; reload: () => void } {
  const [tick, setTick] = useState(0);
  const key = JSON.stringify([tick, ...deps]);
  const [result, setResult] = useState<{ key: string; value: AsyncState<T> } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).then(
      (data) => !controller.signal.aborted && setResult({ key, value: { status: "ready", data } }),
      (error: unknown) => !controller.signal.aborted && setResult({ key, value: { status: "error", error } }),
    );
    return () => controller.abort();
    // `load` change à chaque rendu : seule la clé (tick + dépendances) déclenche un rechargement.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const state: AsyncState<T> = result && result.key === key ? result.value : { status: "loading" };
  return { state, reload };
}
