"""Rule-based flashcard generation from pasted study material.

Formats understood (one card per pair):
  Q: question        A: answer
  question ?         answer
  term : definition
  term - definition
If no material is given, returns a seed card with a hint for the caller.
"""

from __future__ import annotations

import re

MAX_CARDS = 12


def generate_flashcards(topic: str, material: str | None = None, count: int = 6) -> list[dict]:
    cards = _from_material(material) if material else []
    if not cards:
        cards = [{"q": f"Write one key fact about: {topic}",
                  "a": "(Paste study notes as `material` to generate real flashcards.)"}]
    return cards[: max(1, min(count, MAX_CARDS))]


def _from_material(material: str) -> list[dict]:
    lines = [l.strip() for l in material.splitlines() if l.strip()]
    cards: list[dict] = []

    # Pattern 1: explicit Q:/A: pairs (separate lines, or inline "Q: ... A: ...")
    i = 0
    while i < len(lines):
        qm = re.match(r"^q[:\-]\s*(.+)$", lines[i], re.I)
        if qm:
            question = qm.group(1)
            inline = re.split(r"\s+a[:\-]\s+", question, maxsplit=1, flags=re.I)
            if len(inline) == 2:
                cards.append({"q": inline[0].strip(), "a": inline[1].strip()})
                i += 1
                continue
            if i + 1 < len(lines):
                am = re.match(r"^a[:\-]\s*(.+)$", lines[i + 1], re.I)
                if am:
                    cards.append({"q": question, "a": am.group(1)})
                    i += 2
                    continue
            cards.append({"q": question, "a": ""})
        i += 1

    # Pattern 2: "term : definition" or "term - definition"
    for line in lines:
        if len(cards) >= MAX_CARDS:
            break
        m = re.match(r"^(.+?)\s*[:：\-—]\s*(.+)$", line)
        if m and not line.lower().startswith(("q:", "a:")):
            q, a = m.group(1).strip(), m.group(2).strip()
            if 2 <= len(q) <= 80 and 2 <= len(a) <= 200:
                cards.append({"q": q, "a": a})

    # Pattern 3: sentence ending with '?' — next line is the answer
    i = 0
    while i < len(lines) - 1:
        if lines[i].endswith("?") and not lines[i].lower().startswith(("q:", "a:")):
            cards.append({"q": lines[i], "a": lines[i + 1]})
            i += 2
            continue
        i += 1

    seen, unique = set(), []
    for c in cards:
        if c["q"] not in seen:
            seen.add(c["q"])
            unique.append(c)
    return unique