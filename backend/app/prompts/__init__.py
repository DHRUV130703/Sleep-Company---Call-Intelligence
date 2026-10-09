"""Prompt templates live next to this file as Markdown. Edit the .md files — no code changes needed.

Each file starts with a `version: X` line (stored with every analysis, so you can re-analyse calls
made with an older prompt). Placeholders look like {{name}}.
"""

import re
from pathlib import Path

DIR = Path(__file__).parent
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render(name: str, **values: object) -> tuple[str, str]:
    """Return (prompt text, version) for prompts/<name>.md with placeholders filled in."""
    raw = (DIR / f"{name}.md").read_text(encoding="utf-8")
    first, _, body = raw.partition("\n")
    version = first.removeprefix("version:").strip() if first.startswith("version:") else "0"

    def fill(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in values:
            raise KeyError(f"prompt {name}.md needs a value for {{{{{key}}}}}")
        return str(values[key])

    return _PLACEHOLDER.sub(fill, body.strip()), f"{name}@{version}"


def current_version(name: str) -> str:
    """The version stored with results made by prompts/<name>.md today, e.g. "analyze_call@3"."""
    first = (DIR / f"{name}.md").read_text(encoding="utf-8").partition("\n")[0]
    return f"{name}@{first.removeprefix('version:').strip() if first.startswith('version:') else '0'}"
