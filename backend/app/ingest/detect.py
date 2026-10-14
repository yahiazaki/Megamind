"""Detect whether a piece of text is Arabic script or Egyptian Franco-Arabic (Arabizi)."""
import re

ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
WORD_RE = re.compile(r"[^\W_]+")
# Arabizi uses digits as letters inside words: 3=ع, 2=ء, 7=ح, 5=خ, 8=غ, 6=ط, 9=ص
ARABIZI_DIGIT_RE = re.compile(r"^[a-z]*[235678][a-z][a-z0-9]*$", re.I)  # digit used as a letter: 3yz, ha2y2a, b3d

FRANCO_WORDS = {
    "l", "el", "w", "fl", "fel", "bl", "bel", "lel", "ll", "fy", "fe", "fi", "da", "de", "dol", "dah",
    "keda", "kda", "msh", "mesh", "mish", "bta3", "bt3", "btaa", "3shan", "ashan", "ya3ny", "yaany", "enta",
    "enty", "ana", "ehna", "homa", "howa", "hwa", "hya", "heya", "momken", "lazem", "lazm", "lw", "ama",
    "lama", "b3d", "ba3d", "abl", "2abl", "3la", "3ala", "ala", "mn", "m3", "ma3", "eh", "ezay", "leh",
    "fein", "feen", "ba2a", "bas", "kaman", "tab3n", "aw", "walla", "wala", "zy", "zay", "zyy", "gowa",
    "barra", "kol", "kolo", "kolha", "haga", "hagat", "awel", "akher", "tany", "talet", "3yz", "3ayez", "3ayz",
    "3amtan", "dlwa2ty", "delwa2ty", "fa", "ya", "y3ny", "hena", "henak", "mfysh", "mafeesh", "fyh", "feeh",
    "byb2a", "bt3ml", "bey", "beta", "maslan", "masalan", "khalas", "5alas", "3l", "3nd", "3and", "lyh",
    "leeh", "brdo", "bardo", "ely", "elly", "eli", "ly", "mabein", "bein", "akeno", "aken", "keman",
}
_SHORT_AMBIGUOUS = {"a", "an", "i", "is", "it", "in", "on", "to", "of", "or", "be", "so", "do", "go"}


def franco_score(text: str) -> float:
    """Share of words that look like Arabizi (0..1)."""
    words = [w.lower() for w in WORD_RE.findall(text)]
    if not words:
        return 0.0
    hits = 0
    for w in words:
        if w in _SHORT_AMBIGUOUS or w.isdigit():
            continue
        if w in FRANCO_WORDS or ARABIZI_DIGIT_RE.match(w):
            hits += 1
    return hits / len(words)


def needs_translation(text: str) -> bool:
    t = text.strip()
    if len(t) < 2:
        return False
    if ARABIC_RE.search(t):
        return True
    words = WORD_RE.findall(t)
    if len(words) <= 3:
        # Very short lines (code, labels): translate only if almost every word is Franco
        return len(words) >= 2 and franco_score(t) >= 0.67
    return franco_score(t) >= 0.12


def language_profile(text: str) -> dict:
    words = WORD_RE.findall(text)
    return {
        "words": len(words),
        "arabic_chars": len(ARABIC_RE.findall(text)),
        "franco_score": round(franco_score(text), 3),
    }
