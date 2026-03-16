import unicodedata


def normalize_text(s: str) -> str:
    if s is None:
        return None
    nkfd_form = unicodedata.normalize('NFKD', s)
    only_ascii = ''.join([c for c in nkfd_form if not unicodedata.combining(c)])
    return only_ascii.lower().strip()
