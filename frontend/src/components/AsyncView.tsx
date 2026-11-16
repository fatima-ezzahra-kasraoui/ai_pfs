import type { ReactNode } from "react";
import type { AsyncState } from "../hooks";

interface Props<T> {
  state: AsyncState<T>;
  /** Retourne `true` si les données sont vides (affiche l'état Empty). */
  isEmpty?: (data: T) => boolean;
  emptyMessage?: string;
  onRetry?: () => void;
  children: (data: T) => ReactNode;
}

/** Gère uniformément les trois états : Loading, Empty, Error. */
export function AsyncView<T>({ state, isEmpty, emptyMessage = "Aucune donnée à afficher.", onRetry, children }: Props<T>) {
  if (state.status === "loading") {
    return (
      <p role="status" aria-live="polite" className="state state-loading">
        Chargement…
      </p>
    );
  }
  if (state.status === "error") {
    return (
      <div role="alert" className="state state-error">
        <p>Impossible de charger les données.</p>
        {onRetry && (
          <button type="button" onClick={onRetry}>
            Réessayer
          </button>
        )}
      </div>
    );
  }
  if (isEmpty?.(state.data)) {
    return (
      <p role="status" className="state state-empty">
        {emptyMessage}
      </p>
    );
  }
  return <>{children(state.data)}</>;
}
