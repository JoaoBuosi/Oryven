from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, re, unicodedata


def _normalize(value: str) -> str:
    value = ''.join(c for c in unicodedata.normalize('NFD', value.casefold()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', value).strip()


def _safe_name(value: str) -> str:
    value = re.sub(r'[^\wÀ-ÿ ._-]', '', value, flags=re.UNICODE).strip()
    if not (2 <= len(value) <= 32):
        raise ValueError('O nome do assistente deve ter entre 2 e 32 caracteres.')
    return value

@dataclass
class VoiceProfile:
    assistant_name: str = 'Oryven'
    language: str = 'pt-BR'
    background_listening_enabled: bool = False
    speak_on_startup: bool = True
    wake_enabled: bool = True

    @classmethod
    def load(cls, path: Path) -> 'VoiceProfile':
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return cls(
                assistant_name=_safe_name(str(data.get('assistant_name','Oryven'))),
                language=str(data.get('language','pt-BR'))[:16] or 'pt-BR',
                background_listening_enabled=bool(data.get('background_listening_enabled',False)),
                speak_on_startup=bool(data.get('speak_on_startup',True)),
                wake_enabled=bool(data.get('wake_enabled',True)),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)

    def update(self, **values) -> 'VoiceProfile':
        current = asdict(self)
        if 'assistant_name' in values and values['assistant_name'] is not None:
            current['assistant_name'] = _safe_name(str(values['assistant_name']))
        for key in ('background_listening_enabled','speak_on_startup','wake_enabled'):
            if key in values and values[key] is not None:
                current[key] = bool(values[key])
        if values.get('language') is not None:
            current['language'] = str(values['language'])[:16] or 'pt-BR'
        return VoiceProfile(**current)

    def match_wake(self, text: str) -> tuple[bool, str]:
        if not self.wake_enabled:
            return False, text.strip()
        normalized = _normalize(text)
        names = {_normalize(self.assistant_name)}
        if _normalize(self.assistant_name) == 'oryven':
            names.update({'oriven','ori ven'})
        for name in sorted(names, key=len, reverse=True):
            pattern = re.compile(rf'\b{re.escape(name)}\s*[,!. ]*\s*acord(?:ar|a)\b', re.I)
            match = pattern.search(normalized)
            if match:
                return True, normalized[match.end():].strip(' ,.!?;:')
        return False, text.strip()
