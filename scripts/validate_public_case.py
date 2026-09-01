#!/usr/bin/env python3
"""Fail closed on common public-case-study hygiene mistakes."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = {
    "README.md",
    "docs/architecture.md",
    "docs/authorization-and-tenancy.md",
    "docs/engineering-decisions.md",
    "docs/mcp-design.md",
    "docs/testing.md",
    "examples/mcp-interaction.md",
}

FORBIDDEN_LITERALS = {
    "github.com/selvalabs/circulo",
    "selvalabs/circulo.git",
    "ponto-comum",
    "ponto_comum",
    "arca.localhost",
    "outro.localhost",
    "agents.soberania.cloud",
}

FORBIDDEN_PATTERNS = {
    "IPv4 address": re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
    "private filesystem path": re.compile(r"(?:/opt/|/home/|/var/lib/|[A-Za-z]:\\(?:Users|ProgramData)\\)"),
    "common secret token": re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})\b"),
    "literal secret assignment": re.compile(
        r"(?i)(?:api[_-]?key|client[_-]?secret|access[_-]?token|password)\s*[:=]\s*[\"'](?![<$])[A-Za-z0-9_./+=-]{8,}[\"']"
    ),
}

LOCAL_LINK = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)")


def markdown_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*.md") if ".git" not in path.parts)


def validate_required_files(errors: list[str]) -> None:
    for relative in sorted(REQUIRED_FILES):
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")


def validate_markdown(path: Path, errors: list[str]) -> None:
    relative = path.relative_to(ROOT)
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()

    for literal in sorted(FORBIDDEN_LITERALS):
        if literal.lower() in lowered:
            errors.append(f"{relative}: forbidden private marker: {literal}")

    for label, pattern in FORBIDDEN_PATTERNS.items():
        match = pattern.search(text)
        if match:
            errors.append(f"{relative}: detected {label}: {match.group(0)!r}")

    if text.count("```") % 2:
        errors.append(f"{relative}: unbalanced fenced code block")

    for raw_target in LOCAL_LINK.findall(text):
        target = raw_target.split("#", 1)[0].strip()
        if not target:
            continue
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(ROOT)
        except ValueError:
            errors.append(f"{relative}: local link escapes repository: {raw_target}")
            continue
        if not resolved.exists():
            errors.append(f"{relative}: broken local link: {raw_target}")


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)

    files = markdown_files()
    if not files:
        errors.append("no Markdown files found")

    for path in files:
        validate_markdown(path, errors)

    if errors:
        print("Public case-study validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Public case-study validation passed for {len(files)} Markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
