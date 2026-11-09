"""Explicit, deterministic intents. No LLM-generated commands are executable."""
import re
import unicodedata
from .models import AppLaunchIntent, SearchIntent, ExecutableIntent


def normalize(text: str) -> str:
    no_accents = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", no_accents.casefold()).strip()


_WAKE = re.compile(r"\b(?:oryven|oriven|ori ven)\s*[,!. ]*\s*acord(?:ar|a)\b", re.I)
_SEARCH = re.compile(r"\bpesquis(?:e|ar|a)\b\s*(?:por\s+|sobre\s+)?(.+)$", re.I)
_APP_ALIASES = {
    "bloco de notas": "notepad", "notepad": "notepad",
    "calculadora": "calculator", "calculator": "calculator",
    "explorador de arquivos": "explorer", "explorador": "explorer", "explorer": "explorer",
}
_APP = re.compile(r"^(?:por favor[, ]*)?(?:abra|abrir|inicie|iniciar)\s+(?:o|a|os|as)?\s*(.+?)\s*$", re.I)


def strip_wake(text: str) -> tuple[bool, str]:
    normalized = normalize(text)
    match = _WAKE.search(normalized)
    if not match:
        return False, text.strip()
    return True, normalized[match.end():].strip(" ,.!?;:")


def parse_search(text: str) -> SearchIntent | None:
    normalized = normalize(text).strip(" ,.!?;:")
    match = _SEARCH.search(normalized)
    if not match:
        return None
    query = match.group(1).strip(" ,.!?;:")
    if not query or len(query) > 180:
        return None
    return SearchIntent(query=query)


def parse_app_launch(text: str) -> AppLaunchIntent | None:
    normalized = normalize(text).strip(" ,.!?;:")
    match = _APP.fullmatch(normalized)
    if not match:
        return None
    app_id = _APP_ALIASES.get(match.group(1))
    if app_id is None:
        return None
    return AppLaunchIntent(app_id=app_id)


_DYNAMIC_APP = re.compile(r"^(?:por favor[, ]*)?(?:abra|abrir|inicie|iniciar)\s+(?:o|a|os|as)?\s*(.+?)\s*$", re.I)

def parse_dynamic_app_name(text: str) -> str | None:
    normalized = normalize(text).strip(" ,.!?;:")
    match = _DYNAMIC_APP.fullmatch(normalized)
    if not match:
        return None
    name = match.group(1).strip(" ,.!?;:")
    if not name or len(name) > 120:
        return None
    return name

def parse_intent(text: str) -> ExecutableIntent | None:
    return parse_search(text) or parse_app_launch(text)
