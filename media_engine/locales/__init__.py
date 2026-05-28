# SPDX-License-Identifier: MIT

from .en import TEXTS as EN_TEXTS
from .ja import TEXTS as JA_TEXTS
from .zh import TEXTS as ZH_TEXTS

LOCALES = {
    "zh": ZH_TEXTS,
    "en": EN_TEXTS,
    "ja": JA_TEXTS,
}


def get_texts(lang: str) -> dict[str, str]:
    return LOCALES.get(lang, ZH_TEXTS)
