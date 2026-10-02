"""Language router: detects ar (MSA), darija (Arabic script or Arabizi), fr, en.
Darija markers cover Algerian first; shared Maghrebi words are kept so any Darija input is routed correctly.

Heuristic on purpose: fast, dependency-free, and easy to test. Replace with a
fine-tuned classifier later (good first issue!).
"""
import re

ARABIC = re.compile(r"[\u0600-\u06FF]")
LATIN = re.compile(r"[A-Za-z]")
WORD = re.compile(r"[\w']+", re.UNICODE)

DARIJA_AR = {
    "ديال", "ديالي", "كيفاش", "علاش", "واش", "فين", "بغيت", "شنو", "دابا", "مزيان",
    "خاصني", "عافاك", "كاين", "ماكاينش", "بزاف", "شحال", "امتى", "وقتاش",
    "راه", "غادي", "نقدر", "كيدير", "هاد", "هادي", "علاه", "كاش", "باش", "مانيش",
    # Algerian
    "وين", "ماكانش", "راني", "راك", "رانا", "تاع", "متاع", "نتاع", "درك", "ياسر", "برك",
    "نحب", "حاب", "باه", "خاطر", "كيما", "واه", "ندير", "نروح", "وقتاه", "ماشي",
}
DARIJA_LATIN = {
    "kifach", "kifash", "wach", "bghit", "bghite", "chno", "chnou", "shno", "dyal",
    "diyal", "3lach", "3afak", "mzyan", "daba", "kayn", "makaynch", "bzaf",
    "9dar", "nqdar", "wakha", "mchi", "chhal", "imta", "wqtach", "ghadi",
    "hna", "machi", "khasni",
    # Algerian
    "wesh", "kayen", "makanch", "rani", "rak", "rana", "nheb", "hab", "derk", "bezzaf",
    "yasser", "berk", "ta3", "tae", "mta3", "nta3", "bah", "khater", "kifah", "wakteh", "ndir",
}
FRENCH = {
    "le", "la", "les", "des", "du", "un", "une", "et", "est", "pour", "dans", "que",
    "qui", "quelle", "quel", "comment", "quand", "où", "je", "ai", "au", "aux",
    "sur", "avec", "pas", "puis", "peut", "faut", "doit", "ce", "cette", "mon", "ma",
}
ENGLISH = {"the", "is", "are", "what", "how", "when", "where", "can", "do", "does", "to", "of", "and", "for"}
# Arabizi: Latin letters mixed with digits standing for Arabic sounds (3, 7, 9, 5, 2)
ARABIZI_DIGITS = re.compile(r"\b(?=\w*[a-z])(?=\w*[23579])\w+\b", re.IGNORECASE)


def detect_language(text: str) -> str:
    """Return one of: 'ar', 'darija', 'fr', 'en'."""
    n_ar = len(ARABIC.findall(text))
    n_lat = len(LATIN.findall(text))
    words = [w.lower() for w in WORD.findall(text)]

    if n_ar > n_lat:
        hits = sum(w in DARIJA_AR for w in words)
        return "darija" if hits >= 1 else "ar"

    darija_hits = sum(w in DARIJA_LATIN for w in words) + len(ARABIZI_DIGITS.findall(text))
    fr_hits = sum(w in FRENCH for w in words)
    en_hits = sum(w in ENGLISH for w in words)
    if darija_hits >= 1 and darija_hits >= fr_hits:
        return "darija"
    if fr_hits >= en_hits and fr_hits > 0:
        return "fr"
    if en_hits > 0:
        return "en"
    return "fr"  # default for a francophone corpus
