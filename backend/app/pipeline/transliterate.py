"""Write Hindi (Devanagari) in English letters, the way people type Hinglish — same words, same language.

    "हाँ बोलिए"                 → "haan boliye"
    "साहब के नंबर से"           → "saahab ke nambar se"
    "गुड इवनिंग"                → "gud ivning"   (English words the transcriber wrote in Devanagari)

This is a mechanical script change — it never translates. It's deterministic (no AI), so it is instant
and can't invent or drop words. Text that is already in English letters is left as it is.

How it works, per word:
  1. Split the word into syllables: consonant (+ vowel sign / inherent "a" / no vowel after ्).
  2. Drop the silent inherent "a" (Hindi "schwa deletion"): at the end of a word, and in the middle
     when the syllables around it are full syllables  (बोलना → "bol·na", not "bo·la·na").
  3. Write each syllable in letters; long vowels at the end of a word are shortened, as in normal
     Hinglish ("tha", "ki", "tu").
"""

import re

VOWELS = {
    "अ": "a",
    "आ": "aa",
    "इ": "i",
    "ई": "ee",
    "उ": "u",
    "ऊ": "oo",
    "ऋ": "ri",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
    "ऑ": "o",
    "ऍ": "e",
    "ऎ": "e",
    "ऒ": "o",
}
MATRAS = {
    "ा": "aa",
    "ि": "i",
    "ी": "ee",
    "ु": "u",
    "ू": "oo",
    "ृ": "ri",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
    "ॉ": "o",
    "ॅ": "e",
    "ॆ": "e",
    "ॊ": "o",
}
CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh",
    "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d",
    "ध": "dh", "न": "n", "प": "p", "फ": "f", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r",
    "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
    # letters with a nukta dot (precomposed)
    "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f", "य़": "y",
}  # fmt: skip
NUKTA_FORM = {"क": "q", "ख": "kh", "ग": "g", "ज": "z", "ड": "r", "ढ": "rh", "फ": "f", "य": "y"}
DIGITS = {chr(0x0966 + d): str(d) for d in range(10)}
VIRAMA, NUKTA = "्", "़"
NASALS = {"ं", "ँ"}
VISARGA = "ः"
LIPS = ("p", "b", "m")  # anusvara before these sounds like "m": नंबर → "nambar"

_DEVANAGARI = re.compile(r"[ऀ-ॿ]+")


class _Syl:
    __slots__ = ("cons", "vowel", "kind", "nasal")

    def __init__(self, cons: str, vowel: str, kind: str):
        self.cons = cons  # "" for a vowel letter on its own
        self.vowel = vowel  # "" when the consonant has a virama (no vowel)
        self.kind = kind  # "inherent" | "sign" | "letter" | "none"
        self.nasal = ""


def _syllables(word: str) -> list[_Syl]:
    out: list[_Syl] = []
    i = 0
    while i < len(word):
        ch = word[i]
        if ch in CONSONANTS:
            cons = CONSONANTS[ch]
            i += 1
            if i < len(word) and word[i] == NUKTA:
                cons = NUKTA_FORM.get(ch, cons)
                i += 1
            nxt = word[i] if i < len(word) else ""
            if nxt == VIRAMA:
                out.append(_Syl(cons, "", "none"))
                i += 1
            elif nxt in MATRAS:
                out.append(_Syl(cons, MATRAS[nxt], "sign"))
                i += 1
            else:
                out.append(_Syl(cons, "a", "inherent"))
        elif ch in VOWELS:
            out.append(_Syl("", VOWELS[ch], "letter"))
            i += 1
        elif ch in NASALS:
            if out:
                out[-1].nasal = "n"
            i += 1
        elif ch == VISARGA:
            if out:
                out[-1].nasal += "h"
            i += 1
        else:
            i += 1  # zero-width joiners, stray marks
    # ज्ञ is said "gy" (gyaan), not "jn"
    for a, b in zip(out, out[1:], strict=False):
        if a.cons == "j" and a.kind == "none" and b.cons == "n" and b.kind != "letter":
            a.cons, b.cons = "g", "y"
    return out


def _drop_silent_a(syl: list[_Syl]) -> None:
    def full(s: _Syl) -> bool:
        return bool(s.cons) and bool(s.vowel)

    if len(syl) > 1 and syl[-1].kind == "inherent" and not syl[-1].nasal:
        syl[-1].vowel = ""
    for i in range(len(syl) - 2, 0, -1):
        s = syl[i]
        if s.kind == "inherent" and s.vowel and not s.nasal and syl[i - 1].vowel and full(syl[i + 1]):
            s.vowel = ""


def _word(word: str) -> str:
    syl = _syllables(word)
    if not syl:
        return ""
    _drop_silent_a(syl)
    parts = []
    for n, s in enumerate(syl):
        vowel = s.vowel
        at_end = n == len(syl) - 1
        # Long vowels at the end of a word are written short, as in normal Hinglish: tha, ki, thi, tu, hui.
        if at_end and s.kind in ("sign", "letter") and not s.nasal and (len(syl) > 1 or s.kind == "sign"):
            vowel = {"aa": "a", "ee": "i", "oo": "u"}.get(vowel, vowel)
        # A vowel letter right after another vowel glides: बोलिए → "boliye", गए → "gaye".
        if s.kind == "letter" and vowel in ("e", "ai") and n > 0 and syl[n - 1].vowel:
            vowel = "y" + vowel
        nasal = s.nasal
        if at_end and nasal == "n" and vowel in ("e", "ee"):  # में → "mein", नहीं → "nahin"
            vowel = {"e": "ei", "ee": "i"}[vowel]
        if nasal.startswith("n") and n + 1 < len(syl) and syl[n + 1].cons.startswith(LIPS):
            nasal = "m" + nasal[1:]
        parts.append(s.cons + vowel + nasal)
    return "".join(parts)


def to_roman(text: str) -> str:
    """Devanagari parts → English letters; everything else (English, digits, punctuation) unchanged."""
    text = text.replace("।", ".").replace("॥", ".")
    text = "".join(DIGITS.get(c, c) for c in text)
    return _DEVANAGARI.sub(lambda m: _word(m.group(0)), text)


def has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI.search(text))
