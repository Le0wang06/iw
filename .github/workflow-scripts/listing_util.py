"""Shared listing helpers for board + ATS + Discord watchers."""

from __future__ import annotations

import re

WHITESPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^a-z0-9]+")
CORP_RE = re.compile(r"\b(inc|llc|ltd|corp|co|limited|incorporated)\b\.?", re.I)
EMOJI_RE = re.compile(r"[🎓🛂🇺🇸🔥🔒↳]")

TERM_RULES = [
    (re.compile(r"winter\s*2027|off[- ]season|off[- ]cycle", re.I), "Winter 2027"),
    (re.compile(r"fall\s*2026", re.I), "Fall 2026"),
    (re.compile(r"spring\s*2027", re.I), "Spring 2027"),
    (re.compile(r"summer\s*2027|\bsummer\b", re.I), "Summer 2027"),
    (re.compile(r"new[- ]?grad|university grad|early career", re.I), "New Grad"),
    (re.compile(r"co[- ]?op", re.I), "Co-op"),
    (re.compile(r"intern", re.I), "Internship"),
]

TRACK_RULES = [
    (re.compile(r"quant|trading|market maker|\bhft\b", re.I), "Quant"),
    (re.compile(r"machine learning|\bml\b|\bai\b|deep learning|\bllm\b|multimodal", re.I), "AI / ML"),
    (re.compile(r"data scien|data analy|data eng|analytics", re.I), "Data"),
    (re.compile(r"product manager|\bpm intern|\bpm\b", re.I), "PM"),
    (re.compile(r"hardware|firmware|asic|silicon|fpga|embedded", re.I), "Hardware"),
    (re.compile(r"security|infosec|appsec", re.I), "Security"),
    (re.compile(r"ios|android|mobile|frontend|front-end", re.I), "Frontend / Mobile"),
    (re.compile(r"backend|back-end|full[- ]?stack|software|swe|sde|engineer", re.I), "Software"),
]

PRIORITY_COMPANIES = {
    "anthropic",
    "openai",
    "google",
    "meta",
    "nvidia",
    "stripe",
    "databricks",
    "figma",
    "palantir",
    "jane street",
    "citadel",
    "two sigma",
    "jump trading",
    "hudson river",
    "hrt",
    "imc",
    "akuna",
    "optiver",
    "drw",
    "airbnb",
    "coinbase",
    "datadog",
    "snowflake",
    "tesla",
    "uber",
    "netflix",
    "apple",
    "amazon",
    "microsoft",
    "scale ai",
    "perplexity",
    "xai",
    "cursor",
    "notion",
    "linear",
    "vercel",
    "cloudflare",
    "anduril",
    "cognition",
    "brex",
    "robinhood",
}

EARLY_ROLE_RE = re.compile(
    r"intern|co[- ]?op|new[- ]?grad|university grad|early career|"
    r"entry[- ]level|graduate (software|engineer)|engineer i\b|"
    r"software engineer 1\b|associate software|junior software|"
    r"new graduate",
    re.I,
)


def clean_text(value: str) -> str:
    value = EMOJI_RE.sub("", value or "")
    return WHITESPACE_RE.sub(" ", value).strip()


def norm_company(value: str) -> str:
    value = CORP_RE.sub("", clean_text(value).lower())
    value = PUNCT_RE.sub(" ", value)
    return WHITESPACE_RE.sub(" ", value).strip()


def norm_role(value: str) -> str:
    return clean_text(value).lower()


def norm_location(value: str) -> str:
    value = clean_text(value).lower()
    value = re.sub(r",?\s*united states|\busa\b|\bu\.s\.a?\.?\b", "", value)
    return WHITESPACE_RE.sub(" ", value).strip()


def infer_term(*parts: str, kind: str = "boards") -> str:
    text = " ".join(p for p in parts if p)
    for rx, label in TERM_RULES:
        if rx.search(text):
            return label
    if kind == "ats":
        if re.search(r"new[- ]?grad|early career|university grad", text, re.I):
            return "New Grad"
        return "Internship"
    return "Internship / New Grad"


def infer_track(*parts: str) -> str:
    text = " ".join(p for p in parts if p)
    for rx, label in TRACK_RULES:
        if rx.search(text):
            return label
    return "Other"


def role_type(role: str, term: str) -> str:
    if re.search(r"new[- ]?grad|university grad|early career", role or "", re.I) or term == "New Grad":
        return "New Grad (full-time)"
    if re.search(r"co[- ]?op", role or "", re.I) or term == "Co-op":
        return "Co-op"
    if term in {"Summer 2027", "Winter 2027", "Fall 2026", "Spring 2027"}:
        return f"{term} internship"
    return "Internship"


def is_priority(company: str) -> bool:
    name = norm_company(company)
    return any(p in name for p in PRIORITY_COMPANIES)


def display_key(company: str, role: str, location: str) -> str:
    return "|".join((norm_company(company), norm_role(role), norm_location(location)))
