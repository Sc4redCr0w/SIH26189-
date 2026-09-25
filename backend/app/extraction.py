from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedValue:
    candidate_type: str
    value: str
    normalized_value: str
    confidence: float
    source_span: str


PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s-]{8,}\d)(?!\w)")
VEHICLE_RE = re.compile(r"\b[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}\b", re.IGNORECASE)
DATE_RE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\b")
PERSON_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b")
ORG_RE = re.compile(r"\b[A-Z][A-Za-z&]+(?:\s+[A-Z][A-Za-z&]+){0,4}\s+(?:Logistics|Trading|Transport|Corporation|Ltd|Inc)\b")
RELATION_RE = re.compile(
    r"(?P<source>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?P<verb>met|called|contacted|works\s+for|uses|visited|transferred\s+to|associated\s+with)\s+(?P<target>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}|[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}|\+?\d[\d\s-]{8,}\d)",
    re.IGNORECASE,
)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .,;:()[]")


def extract_candidates(text: str, source_label: str = "document") -> list[ExtractedValue]:
    results: dict[tuple[str, str], ExtractedValue] = {}

    def add(candidate_type: str, value: str, confidence: float, span: str | None = None) -> None:
        cleaned = _clean(value)
        if not cleaned:
            return
        normalized = re.sub(r"\s+", " ", cleaned.casefold())
        key = (candidate_type, normalized)
        if key not in results:
            results[key] = ExtractedValue(candidate_type, cleaned, normalized, confidence, (span or cleaned)[:500])

    for match in PHONE_RE.finditer(text):
        add("PHONE", match.group(0), 0.96, match.group(0))
    for match in VEHICLE_RE.finditer(text):
        add("VEHICLE", match.group(0), 0.94, match.group(0))
    for match in DATE_RE.finditer(text):
        add("DATE", match.group(0), 0.9, match.group(0))
    for match in ORG_RE.finditer(text):
        add("ORGANIZATION", match.group(0), 0.82, match.group(0))
    for match in PERSON_RE.finditer(text):
        value = match.group(0)
        if value.lower() in {"synthetic demonstration", "case overview", "system limitations"}:
            continue
        add("PERSON", value, 0.72, value)
    for match in RELATION_RE.finditer(text):
        source = _clean(match.group("source"))
        target = _clean(match.group("target"))
        verb = re.sub(r"\s+", "_", match.group("verb").strip().upper())
        add("RELATIONSHIP", f"{source}|{verb}|{target}", 0.78, match.group(0))
    return list(results.values())
