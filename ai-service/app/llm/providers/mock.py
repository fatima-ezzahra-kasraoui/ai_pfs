"""LLM SIMULÉS pour les tests et la démonstration hors ligne (aucune inférence, aucun réseau).

* ``SimulatedLLM`` : « agent crédule » déterministe à base de règles. Il fait ce qu'un modèle non protégé
  pourrait faire : exécuter la demande de l'utilisateur ET obéir à toute instruction qu'il lit dans le
  résultat d'un outil ou dans le message. Il sert à rendre les attaques observables ; ses résultats ne
  mesurent PAS le comportement d'un vrai LLM (``simulated = True`` est propagé jusqu'à l'API et à l'interface).
* ``ScriptedLLM`` : rejoue des réponses prédéfinies (tests unitaires du graphe et de la couche LLM).
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from ..errors import LLMError, LLMResponseError
from ..types import LLMResponse, Message, ToolCall, ToolSpec

_SECRET = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
_INJECTION = re.compile(r"ignor\w*\s+(?:tes|vos|toutes?\s+les|all(?:\s+the)?|previous)?\s*(?:pr[eé]c[eé]dentes?\s+|previous\s+)?instructions", re.IGNORECASE)
_LEAK_TARGET = re.compile(r"cl[eé]\s+api|api\s+key|mot\s+de\s+passe|prompt\s+syst[eè]me|system\s+prompt", re.IGNORECASE)
_FORWARD = re.compile(r"transf[eè]re\w*\s+(?:tous\s+les\s+|mes\s+)?(?:mails?|e-?mails?|courriels?)\s+(?:à|a|to)\s+([\w.+-]+@[\w-]+(?:\.[\w-]+)+)", re.IGNORECASE)
_READ_MAIL = re.compile(r"\b(?:r[eé]sum\w*|lis|lire|consulte\w*)\b.*\b(?:mails?|e-?mails?|courriels?|messages?)\b", re.IGNORECASE)
_DELETE = re.compile(r"\bsupprim\w*\b.*?([\w.-]+\.[A-Za-z0-9]{1,6})\b", re.IGNORECASE)
_READ_FILE = re.compile(r"\b(?:contenu\s+de|lis\s+le\s+fichier|ouvre\s+le\s+fichier|affiche\s+le\s+fichier)\s+([\w/\\-]+(?:\.[\w-]+)*)", re.IGNORECASE)
_SEND = re.compile(r"\benvoie\w*\b.*?\b(?:mail|e-?mail|message|courriel)\b.*?\b(?:à|a)\s+([\w.+-]+@[\w-]+(?:\.[\w-]+)+)", re.IGNORECASE)
_BROWSE = re.compile(r"(?:consulte|ouvre|va\s+sur|navigue\s+vers)\s+(https?://\S+)", re.IGNORECASE)
_MAIL_ID = re.compile(r"\b(mail-\d+)\b", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>|<!--.*?-->", re.DOTALL)


def _visible(content: str) -> str:
    """Texte lisible d'un résultat d'outil (retire l'enveloppe d'isolation du Guard B et les balises)."""
    if "<untrusted_content>" in content:
        inner = content.split("\n---\n", 1)[-1]
        content = inner.rsplit("</untrusted_content>", 1)[0]
    return re.sub(r"\s+", " ", _TAGS.sub(" ", content)).strip()


def _doc_path(name: str) -> str:
    name = name.replace("\\", "/")
    return name if "/" in name else f"/documents/{name}"


class SimulatedLLM:
    name = "simulated_gullible"
    simulated = True

    def complete(self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()) -> LLMResponse:
        if not messages:
            raise LLMResponseError("aucun message")
        last = messages[-1]
        n_calls = sum(len(m.tool_calls) for m in messages)
        if last.role == "user":
            return self._on_user(system, last.content, n_calls)
        if last.role == "tool":
            return self._on_tool(last, messages, n_calls)
        return LLMResponse(text="(rien à faire)")

    @staticmethod
    def _call(n: int, name: str, **args: str) -> LLMResponse:
        return LLMResponse(tool_calls=(ToolCall(f"call-{n + 1}", name, args),), stop_reason="tool_use")

    def _on_user(self, system: str, text: str, n: int) -> LLMResponse:
        if _INJECTION.search(text) and _LEAK_TARGET.search(text):
            secret = _SECRET.search(system)
            return LLMResponse(text=f"Voici la clé demandée : {secret.group(0) if secret else '[indisponible]'}")
        if m := _SEND.search(text):
            return self._call(n, "send_email", to=m.group(1), subject="Message", body=text)
        if m := _DELETE.search(text):
            return self._call(n, "delete_file", path=_doc_path(m.group(1)))
        if m := _READ_FILE.search(text):
            return self._call(n, "read_file", path=_doc_path(m.group(1)))
        if m := _BROWSE.search(text):
            return self._call(n, "browse_web", url=m.group(1))
        if _READ_MAIL.search(text):
            if m := _MAIL_ID.search(text):
                return self._call(n, "read_email", email_id=m.group(1).lower())
            return self._call(n, "read_email")
        return LLMResponse(text="Je ne sais pas traiter cette demande avec mes outils (réponse simulée).")

    def _on_tool(self, last: Message, messages: Sequence[Message], n: int) -> LLMResponse:
        content = last.content
        if content.startswith(("Erreur", "[AgentShield]")):
            return LLMResponse(text=f"Je n'ai pas pu terminer l'opération : {content}")
        already_sent = any(c.name == "send_email" for m in messages for c in m.tool_calls)
        if (m := _FORWARD.search(content)) and not already_sent:  # crédulité : obéit à l'instruction lue dans l'outil
            return self._call(n, "send_email", to=m.group(1), subject="Transfert", body="(contenu des e-mails)")
        visible = _visible(content)
        if last.name == "read_email":
            subjects = re.findall(r"Objet : ([^\n]+)", _TAGS.sub(" ", content))
            return LLMResponse(text=f"Résumé de vos e-mails : {' ; '.join(subjects)}." if subjects else f"Résumé de vos e-mails : {visible[:240]}")
        if last.name == "read_file":
            return LLMResponse(text=f"Contenu du fichier : {content}")
        if last.name == "browse_web":
            return LLMResponse(text=f"Page consultée : {visible[:240]}")
        return LLMResponse(text=f"Opération effectuée : {visible}")


class ScriptedLLM:
    """Rejoue une file de réponses ; consigne les appels reçus. ``LLMError`` dans la file : levée à l'appel."""

    name = "scripted"
    simulated = True

    def __init__(self, script: Sequence[LLMResponse | LLMError]) -> None:
        self._script = list(script)
        self.calls: list[tuple[str, list[Message], list[ToolSpec]]] = []

    def complete(self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()) -> LLMResponse:
        self.calls.append((system, list(messages), list(tools)))
        if not self._script:
            raise LLMResponseError("script épuisé")
        item = self._script.pop(0)
        if isinstance(item, LLMError):
            raise item
        return item
