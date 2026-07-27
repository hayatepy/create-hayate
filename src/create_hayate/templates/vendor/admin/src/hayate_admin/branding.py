"""Bounded branding and color contracts with no raw HTML or CSS injection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

ThemeDensity = Literal["comfortable", "compact"]
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]


def _luminance(color: str) -> float:
    channels = []
    for value in _rgb(color):
        normalized = value / 255
        channels.append(
            normalized / 12.92 if normalized <= 0.04045 else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@dataclass(frozen=True, slots=True)
class AdminTheme:
    """A small color-token theme that must satisfy WCAG contrast thresholds."""

    accent: str = "#005EA8"
    background: str = "#F5F7FB"
    surface: str = "#FFFFFF"
    text: str = "#172033"
    muted: str = "#4B5563"
    focus: str = "#A23B00"
    density: ThemeDensity = "comfortable"

    def __post_init__(self) -> None:
        for name in ("accent", "background", "surface", "text", "muted", "focus"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _HEX_COLOR.fullmatch(value):
                raise ValueError(f"admin theme {name} must be a six-digit hex color")
            object.__setattr__(self, name, value.upper())
        if self.density not in ("comfortable", "compact"):
            raise ValueError("admin theme density must be 'comfortable' or 'compact'")
        pairs = (
            ("text", self.text, "background", self.background, 4.5),
            ("text", self.text, "surface", self.surface, 4.5),
            ("muted", self.muted, "background", self.background, 4.5),
            ("muted", self.muted, "surface", self.surface, 4.5),
            ("accent", self.accent, "background", self.background, 4.5),
            ("accent", self.accent, "surface", self.surface, 4.5),
            ("focus", self.focus, "background", self.background, 3.0),
            ("focus", self.focus, "surface", self.surface, 3.0),
        )
        for first_name, first, second_name, second, minimum in pairs:
            if _contrast(first, second) < minimum:
                raise ValueError(
                    f"admin theme {first_name}/{second_name} contrast must be at least {minimum}:1"
                )

    @property
    def on_accent(self) -> str:
        """Choose a readable button label without accepting another untrusted token."""
        return "#000000" if _contrast(self.accent, "#000000") >= 4.5 else "#FFFFFF"


@dataclass(frozen=True, slots=True)
class AdminBranding:
    """Plain-text wordmark and validated theme tokens for one AdminSite."""

    wordmark: str | None = None
    theme: AdminTheme = field(default_factory=AdminTheme)

    def __post_init__(self) -> None:
        if self.wordmark is not None:
            if not isinstance(self.wordmark, str) or not self.wordmark or len(self.wordmark) > 80:
                raise ValueError("admin branding wordmark must be 1-80 characters")
            if any(unicodedata.category(character) == "Cc" for character in self.wordmark):
                raise ValueError("admin branding wordmark must not contain control characters")
        if not isinstance(self.theme, AdminTheme):
            raise ValueError("admin branding theme must be an AdminTheme")
