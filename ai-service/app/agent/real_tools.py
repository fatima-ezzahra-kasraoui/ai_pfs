"""Opt-in lab adapters. No external SMTP relay or destructive operations."""

import json
import os
import re
import smtplib
import stat
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

import httpx

from ..llm.types import ToolSpec
from .tools import ToolBox, ToolError, ToolResult, tool_specs

ROOT = Path("/srv/real-files")
MAX = 256_000
MAIL = "http://mailpit:8025"
RECIPIENT = "demo@societe.test"
WEB = {"https://example.com/": "https://example.com/", "https://example.com": "https://example.com/"}


class RealToolBox(ToolBox):
    real = True

    def execute(self, name, arguments):
        try:
            return self._execute(name, arguments)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError("Integration failed: " + type(exc).__name__) from exc

    def _result(self, name, text, external=True, effect=None):
        return ToolResult(name, {"status": "ok"}, text[:MAX], external, False, effect)

    def _read_email(self, p):
        with httpx.Client(timeout=10, trust_env=False) as c:
            ident = p.email_id
            if not ident or ident == "latest":
                r = c.get(MAIL + "/api/v1/messages", params={"limit": 1})
                r.raise_for_status()
                messages = r.json().get("messages") or []
                if not messages:
                    return self._result("read_email", "Inbox empty")
                ident = messages[0]["ID"]
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ident):
                raise ToolError("Invalid message ID")
            r = c.get(MAIL + "/api/v1/message/" + quote(ident, safe=""))
            r.raise_for_status()
            m = r.json()
            return self._result(
                "read_email", json.dumps({k: m.get(k) for k in ("ID", "From", "To", "Subject", "Date", "Text")}, ensure_ascii=False)
            )

    def _send_email(self, p):
        if p.to.lower() != RECIPIENT:
            raise ToolError("Recipient not permitted")
        msg = EmailMessage()
        msg["From"] = "agent@societe.test"
        msg["To"] = RECIPIENT
        msg["Subject"] = p.subject
        msg.set_content(p.body)
        with smtplib.SMTP("mailpit", 1025, timeout=10) as smtp:
            if smtp.send_message(msg):
                raise ToolError("SMTP recipient refused")
        return self._result("send_email", "SMTP accepted message in local test inbox.", False, "SMTP accepted")

    def _read_file(self, p):
        name = p.path
        if name == "list":
            return self._result(
                "read_file",
                "\n".join(sorted(x.name for x in ROOT.iterdir() if x.is_file() and not x.is_symlink() and not x.name.startswith("."))),
            )
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name) or ".." in name:
            raise ToolError("Only simple file names permitted")
        if Path(name).suffix.lower() not in {".txt", ".csv", ".json", ".md", ".pdf"}:
            raise ToolError("Unsupported file format")
        fd = os.open(ROOT / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as f:
            info = os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX or info.st_nlink != 1:
                raise ToolError("Invalid file or size")
            if name.lower().endswith(".pdf"):
                from pypdf import PdfReader

                reader = PdfReader(f)
                if len(reader.pages) > 20:
                    raise ToolError("PDF page limit exceeded")
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            else:
                text = f.read(MAX + 1).decode("utf-8")
        return self._result("read_file", text)

    def _browse_web(self, p):
        if p.url not in WEB:
            raise ToolError("URL not permitted; use https://example.com/")
        # Dedicated fixed-destination proxy; no user URL reaches the network.
        with httpx.Client(timeout=15, trust_env=False) as c:
            with c.stream("GET", "http://real-web:8090/") as r:
                r.raise_for_status()
                data = bytearray()
                for chunk in r.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX:
                        raise ToolError("Response too large")
        return self._result("browse_web", data.decode("utf-8"))

    def _delete_file(self, p):
        raise ToolError("Real deletion disabled: secure approval unavailable")


def real_specs():
    descriptions = {
        "read_email": "Read latest local Mailpit email or message ID.",
        "read_file": "Read a file by simple filename; path=list lists files.",
        "send_email": "Send local test email only to demo@societe.test.",
        "browse_web": "Fetch https://example.com/ only.",
    }
    return [ToolSpec(s.name, descriptions[s.name], s.parameters) for s in tool_specs() if s.name in descriptions and s.name != "send_email"]
