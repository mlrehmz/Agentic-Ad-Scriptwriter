"""Advertising brief aggregate and input invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _strings(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of text.")
    if len(value) > 8:
        raise ValueError(f"{field_name} supports at most 8 entries.")
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"Every {field_name} entry must be text.")
    return [item.strip() for item in value if item.strip()]


@dataclass
class AdBrief:
    product_name: str
    description: str
    audience: str
    benefit: str
    tone: str = "Warm and clear"
    platform: str = "Social video"
    duration: int = 15
    cta: str = "Learn more"
    required_points: list[str] = field(default_factory=list)
    prohibited_claims: list[str] = field(default_factory=list)
    brand_voice: str = ""

    @classmethod
    def from_json(cls, data: Any) -> "AdBrief":
        if not isinstance(data, dict):
            raise ValueError("Brief must be a JSON object.")
        text_fields = ("product_name", "description", "audience", "benefit", "tone", "platform", "cta", "brand_voice")
        for key in text_fields:
            if key in data and not isinstance(data[key], str):
                raise ValueError(f"{key} must be text.")

        def value(key: str, default: str = "") -> str:
            item = data.get(key, default)
            return item.strip()

        duration = data.get("duration", 15)
        if isinstance(duration, bool) or not isinstance(duration, int):
            raise ValueError("Duration must be a whole number of seconds.")
        brief = cls(
            product_name=value("product_name"), description=value("description"),
            audience=value("audience"), benefit=value("benefit"),
            tone=value("tone", "Warm and clear") or "Warm and clear",
            platform=value("platform", "Social video") or "Social video",
            duration=duration, cta=value("cta", "Learn more") or "Learn more",
            required_points=_strings(data.get("required_points", []), "required_points"),
            prohibited_claims=_strings(data.get("prohibited_claims", []), "prohibited_claims"),
            brand_voice=value("brand_voice"),
        )
        errors = brief.errors()
        if errors:
            raise ValueError(" ".join(errors))
        return brief

    def errors(self) -> list[str]:
        errors = [f"Add {label}." for key, label in (
            ("product_name", "a product or service name"), ("description", "a factual description"),
            ("audience", "a target audience"), ("benefit", "a main benefit"),
        ) if not getattr(self, key)]
        if not 5 <= self.duration <= 120:
            errors.append("Duration must be between 5 and 120 seconds.")
        return errors
