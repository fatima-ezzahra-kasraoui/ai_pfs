interface Props {
  title: string;
  /** Sprint où la page sera réellement développée. */
  availableIn: string;
}

/** Page vide : la route existe et est navigable, le contenu arrive plus tard. Aucune donnée simulée. */
export function PagePlaceholder({ title, availableIn }: Props) {
  return (
    <section>
      <h1>{title}</h1>
      <p className="muted" role="status">
        Cette page sera disponible au {availableIn}.
      </p>
    </section>
  );
}
