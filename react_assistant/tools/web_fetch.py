from __future__ import annotations

import html
import re
from urllib import error, parse, request

MAX_DOWNLOAD_BYTES = 300_000
MAX_OUTPUT_CHARS = 4000

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_BLANK_RE = re.compile(r"\n\s*\n+")


def _strip_html(html_text: str) -> str:
    text = _TAG_RE.sub(" ", html_text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    cleaned = _BLANK_RE.sub("\n\n", cleaned)
    return cleaned.strip()


class WebFetchTool:
    name = "web_fetch"
    description = (
        "Fetch a URL and return its text content (HTML stripped, truncated). "
        "Input: a full http(s) URL, e.g. 'https://example.com'.")
    aliases = {"fetch", "web", "url"}

    def run(self, url: str) -> str:
        url = (url or "").strip().strip("`\"'").strip()
        if not url:
            raise ValueError("A URL is required, e.g. 'https://example.com'.")
        if len(url) > 2000:
            raise ValueError("URL too long.")
        parsed = parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Only absolute http(s) URLs are allowed.")
        # Block local / private targets to avoid SSRF against dev machines.
        host = (parsed.hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
            raise ValueError("Local URLs are not allowed.")
        try:
            req = request.Request(
                url, headers={"User-Agent": "react_assistant/0.2.0"}, method="GET")
            with request.urlopen(req, timeout=20) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read(MAX_DOWNLOAD_BYTES + 1)
        except error.HTTPError as exc:
            raise ValueError(f"Fetch failed: HTTP {exc.code} {exc.reason}") from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise ValueError(f"Fetch failed (network): {exc}") from exc
        if len(raw) > MAX_DOWNLOAD_BYTES:
            truncated_note = True
            raw = raw[:MAX_DOWNLOAD_BYTES]
        else:
            truncated_note = False
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = raw.decode("latin-1", errors="replace")
        if "html" in content_type.lower() or "<html" in text[:2000].lower():
            text = _strip_html(text)
        text = text.strip()
        if not text:
            return "Fetched page but found no readable text."
        if len(text) > MAX_OUTPUT_CHARS:
            text = text[: MAX_OUTPUT_CHARS - 20] + "...[truncated]"
        elif truncated_note:
            text += "...[truncated]"
        return f"[{url}]\n{text}"
