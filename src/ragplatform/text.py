import re
import unicodedata

_DIACRITICS = re.compile(r"[\u064B-\u0652\u0640]")  # tashkeel + tatweel
_TOKEN = re.compile(r"\w+", re.UNICODE)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = _DIACRITICS.sub("", text)
    text = re.sub("[إأآ]", "ا", text)
    return text.replace("ى", "ي").replace("ة", "ه")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))
