"""Display filtering only: never infer, correct, or insert a vowel."""
import re
import unicodedata

HARAKAT = frozenset('\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0670')
WORD = re.compile(r'[\u0621-\u063a\u0641-\u064a\u066e-\u06d3\u064b-\u065f\u0670]+')


def clusters(word: str) -> list[list[str]]:
    result = []
    for char in unicodedata.normalize('NFC', word):
        if unicodedata.combining(char) and result:
            result[-1][1] += char
        else:
            result.append([char, ''])
    return result


def final_only_word(word: str) -> str:
    parts = clusters(word)
    if not parts:
        return word
    # FatHatan may be encoded on the consonant preceding a supporting alif.
    # For this UI's literal last-letter convention, move the existing mark only.
    if len(parts) > 1 and parts[-1][0] == 'ا' and '\u064b' in parts[-2][1]:
        if not any(c in HARAKAT for c in parts[-1][1]):
            parts[-1][1] += '\u064b'
    return ''.join(base + ''.join(c for c in marks if i == len(parts)-1 or c not in HARAKAT)
                   for i, (base, marks) in enumerate(parts))


def final_only(text: str) -> str:
    return WORD.sub(lambda m: final_only_word(m.group()), unicodedata.normalize('NFC', text))


def tokens(text: str) -> list[str]:
    return [final_only_word(m.group()) for m in WORD.finditer(unicodedata.normalize('NFC', text))]


def skeleton(word: str) -> str:
    return ''.join(c for c in word if c not in HARAKAT)


def ending(word: str) -> str:
    parts = clusters(final_only_word(word))
    return ''.join(sorted(c for c in parts[-1][1] if c in HARAKAT)) if parts else ''
