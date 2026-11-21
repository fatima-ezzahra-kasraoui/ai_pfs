"""Cinq outils FACTICES de démonstration (AS-S1-021).

Noms issus de ``config/policy.yaml`` (Annexe A) : ``read_email``, ``browse_web``, ``read_file``,
``send_email``, ``delete_file``. Les paramètres exacts du dossier de conception n'étant pas disponibles
lors du développement, les signatures ci-dessous sont des HYPOTHÈSES à valider (voir docs/agent.md).

Garanties de sécurité :
* aucune opération réelle : pas d'accès au disque, au réseau ni à un serveur de messagerie ;
* l'état (boîte mail, fichiers, boîte d'envoi) est une copie en mémoire créée pour chaque exécution
  (``ToolBox``) : une suppression « réelle » est impossible, et rien ne persiste d'une exécution à l'autre ;
* le seul « secret » est le faux jeton canary ``sk-FAKE-1234``.
"""
from __future__ import annotations

import copy
import posixpath
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..llm.types import ToolSpec
from .fixtures import CANARY_SECRET, INITIAL_EMAILS, INITIAL_FILES, WEB_PAGES

__all__ = ["CANARY_SECRET", "TOOL_NAMES", "ToolBox", "ToolError", "ToolResult", "normalize_path", "tool_specs"]
TOOL_NAMES = ("read_email", "browse_web", "read_file", "send_email", "delete_file")
MAX_PATH = 255
_EMAIL = re.compile(r"^[^@\s<>,;]{1,64}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")

class ToolError(Exception):
    """Erreur métier d'un outil (entrée invalide, ressource absente). Le message est destiné au modèle."""


@dataclass(frozen=True)
class ToolResult:
    tool: str
    output: dict[str, Any]
    text: str  # rendu transmis au modèle (c'est ce texte que le Guard B inspecte)
    external_content: bool  # True : contient du contenu non fiable (mail, fichier, page web)
    simulated: bool = True
    side_effect: str | None = None  # effet simulé (ex. « e-mail enregistré dans la boîte d'envoi virtuelle »)


# ------------------------------------------------------------------ validation des paramètres
class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadEmailParams(_Params):
    email_id: str | None = Field(default=None, max_length=64, description="Identifiant du message ; absent : tous les messages")


class BrowseWebParams(_Params):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def _scheme(cls, v: str) -> str:
        if not re.match(r"^https?://", v, re.IGNORECASE):
            raise ValueError("seuls les schémas http et https sont acceptés")
        return v


class ReadFileParams(_Params):
    path: str = Field(min_length=1, max_length=MAX_PATH)


class SendEmailParams(_Params):
    to: str = Field(max_length=254)
    subject: str = Field(default="", max_length=200)
    body: str = Field(default="", max_length=20_000)

    @field_validator("to")
    @classmethod
    def _addr(cls, v: str) -> str:
        if not _EMAIL.match(v):
            raise ValueError("adresse e-mail invalide")
        return v


class DeleteFileParams(_Params):
    path: str = Field(min_length=1, max_length=MAX_PATH)


PARAMS: dict[str, type[_Params]] = {
    "read_email": ReadEmailParams, "browse_web": BrowseWebParams, "read_file": ReadFileParams,
    "send_email": SendEmailParams, "delete_file": DeleteFileParams,
}
DESCRIPTIONS = {
    "read_email": "Lit les e-mails de la boîte de réception (simulée).",
    "browse_web": "Consulte une page web (navigation simulée, sans accès réseau).",
    "read_file": "Lit le contenu d'un fichier du dossier de l'utilisateur (système de fichiers virtuel).",
    "send_email": "Envoie un e-mail (simulé : enregistré dans une boîte d'envoi virtuelle).",
    "delete_file": "Supprime un fichier (simulé : retiré du système de fichiers virtuel de l'exécution).",
}


def tool_specs() -> list[ToolSpec]:
    """Descriptions JSON Schema transmises au LLM, générées depuis les modèles de validation (source unique)."""
    specs = []
    for name in TOOL_NAMES:
        schema = PARAMS[name].model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        specs.append(ToolSpec(name, DESCRIPTIONS[name], schema))
    return specs


def normalize_path(raw: str) -> str:
    """Normalise un chemin virtuel. Rejette NUL, ``..`` et toute tentative de sortie de la racine virtuelle."""
    if "\x00" in raw:
        raise ToolError("chemin invalide")
    p = raw.replace("\\", "/")
    if ".." in p.split("/"):
        raise ToolError("chemin invalide : '..' interdit")
    p = posixpath.normpath("/" + p.lstrip("/"))
    return p


@dataclass
class ToolBox:
    """État virtuel d'UNE exécution + exécution des cinq outils. ``fixture`` impose le contenu renvoyé par l'outil nommé."""

    fixture: dict[str, str] | None = None
    emails: list[dict[str, Any]] = field(default_factory=lambda: copy.deepcopy(list(INITIAL_EMAILS)))
    trapped_inbox: bool = False  # True : la boîte de réception liste aussi l'e-mail piégé (scénario d'injection indirecte)
    call_log: list[dict[str, Any]] = field(default_factory=list)  # journal des appels (réussis ou non), aucune action réelle
    files: dict[str, str] = field(default_factory=lambda: dict(INITIAL_FILES))
    outbox: list[dict[str, str]] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Exécute un outil et journalise l'appel. Appelé uniquement par ``agent.graph.execute_tool`` (point d'entrée unique)."""
        try:
            result = self._execute(name, arguments)
        except ToolError as exc:
            self.call_log.append({"tool": name, "arguments": arguments, "ok": False, "error": str(exc), "simulated": True})
            raise
        self.call_log.append({"tool": name, "arguments": arguments, "ok": True, "sideEffect": result.side_effect, "simulated": True})
        return result

    def _execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        handler: Callable[[Any], ToolResult] | None = getattr(self, f"_{name}", None) if name in PARAMS else None
        if handler is None:
            raise ToolError(f"outil inconnu : {name}")
        try:
            params = PARAMS[name](**arguments)
        except ValidationError as exc:
            problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors())
            raise ToolError(f"arguments invalides pour {name} : {problems}") from exc
        return handler(params)

    def _fixture_for(self, name: str) -> str | None:
        return self.fixture["content"] if self.fixture and self.fixture.get("name") == name else None

    # -- outils -----------------------------------------------------------------------------------
    def _read_email(self, p: ReadEmailParams) -> ToolResult:
        override = self._fixture_for("read_email")
        if override is not None:
            emails = [{"id": "fixture", "from": "expediteur@societe.test", "subject": "(scénario)", "body": override}]
        else:
            emails = [e for e in self.emails if (e["id"] == p.email_id if p.email_id else self.trapped_inbox or not e.get("planted"))]
            if p.email_id and not emails:
                raise ToolError(f"message introuvable : {p.email_id}")
        text = "\n---\n".join(f"De : {e['from']}\nObjet : {e['subject']}\n\n{e['body']}" for e in emails) or "(boîte vide)"
        return ToolResult("read_email", {"emails": emails}, text, external_content=True)

    def _browse_web(self, p: BrowseWebParams) -> ToolResult:
        override = self._fixture_for("browse_web")
        page = {"title": "(scénario)", "content": override} if override is not None else WEB_PAGES.get(p.url.rstrip("/"))
        if page is None:
            raise ToolError("page introuvable (navigation simulée : seules les pages de démonstration existent)")
        return ToolResult("browse_web", {"url": p.url, **page}, f"{page['title']}\n{page['content']}", external_content=True)

    def _read_file(self, p: ReadFileParams) -> ToolResult:
        path = normalize_path(p.path)
        override = self._fixture_for("read_file")
        content = override if override is not None else self.files.get(path)
        if content is None:
            raise ToolError(f"fichier introuvable : {path}")
        return ToolResult("read_file", {"path": path, "content": content}, content, external_content=True)

    def _send_email(self, p: SendEmailParams) -> ToolResult:
        message_id = f"sim-{len(self.outbox) + 1}"
        self.outbox.append({"id": message_id, "to": p.to, "subject": p.subject, "body": p.body})
        return ToolResult("send_email", {"status": "simulated_sent", "messageId": message_id, "to": p.to}, f"E-mail {message_id} envoyé à {p.to} (simulation).", external_content=False, side_effect="e-mail enregistré dans la boîte d'envoi virtuelle")

    def _delete_file(self, p: DeleteFileParams) -> ToolResult:
        path = normalize_path(p.path)
        if path not in self.files:
            raise ToolError(f"fichier introuvable : {path}")
        del self.files[path]
        self.deleted.append(path)
        return ToolResult("delete_file", {"status": "simulated_deleted", "path": path}, f"Fichier {path} supprimé (simulation).", external_content=False, side_effect="fichier retiré du système de fichiers virtuel (aucune suppression réelle)")
