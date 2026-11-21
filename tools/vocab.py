"""The box's vocabulary (tools/vocab.txt): loader and sentence -> word numbers. Stdlib only.

Used by mkspeech.py (makes the clips), mksounds.py (puts them in the bank as "wNNN.name") and say.py (sends them).
"""
import re
from pathlib import Path

VOCAB_FILE = Path(__file__).resolve().parent / "vocab.txt"
MAX_WORDS = 16          # words per sentence: SAY_MAX_WORDS in firmware/main/config.h
MAX_VOCAB = 240         # word numbers are one byte, and the bank holds 256 clips in all

ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen").split()
TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
ALIASES = {"%": "percent", "e-mail": "email", "o'clock": "oclock", "okay": "ok", ",": "pause", "-": "minus"}


def load(path=VOCAB_FILE):
    """[(name, text)] in file order; a word's number is its index."""
    words, seen = [], set()
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, sep, text = (p.strip() for p in line.partition("="))
        if not sep or not text or not re.fullmatch(r"[a-z0-9]+", name):
            raise SystemExit(f"{path}:{n}: expected 'name = text' (name: a-z, 0-9), got {line!r}")
        if name in seen:
            raise SystemExit(f"{path}:{n}: {name!r} is in the list twice")
        seen.add(name)
        words.append((name, text))
    if len(words) > MAX_VOCAB:
        raise SystemExit(f"{path}: {len(words)} words, the limit is {MAX_VOCAB}")
    return words


def clip_name(index, name):
    """Name of a word's clip in the sound bank; the firmware finds it by the "wNNN." prefix."""
    return f"w{index:03d}.{name}"[:23]


def number_words(n):
    """0..999999 as vocabulary names: 42 -> ['forty', 'two']."""
    if n < 20:
        return [ONES[n]]
    if n < 100:
        return [TENS[n // 10 - 2]] + ([ONES[n % 10]] if n % 10 else [])
    if n < 1000:
        return [ONES[n // 100], "hundred"] + (number_words(n % 100) if n % 100 else [])
    return number_words(n // 1000) + ["thousand"] + (number_words(n % 1000) if n % 1000 else [])


def sentence(tokens, words=None):
    """Words, numbers ("42", "3.5", "-7", "80%") -> list of word numbers. Exits on a word that is not in the list."""
    words = words or load()
    index = {name: i for i, (name, _) in enumerate(words)}
    names = []
    for tok in " ".join(tokens).lower().replace(",", " , ").split():
        tok = ALIASES.get(tok, tok)
        m = re.fullmatch(r"(-?)(\d{1,6})(?:\.(\d+))?(%?)", tok)
        if m:
            names += (["minus"] if m.group(1) else []) + number_words(int(m.group(2)))
            if m.group(3):
                names += ["point"] + [ONES[int(d)] for d in m.group(3)]
            names += ["percent"] if m.group(4) else []
        else:
            names.append(tok.strip(".!?"))
    missing = sorted({n for n in names if n not in index})
    if missing:
        raise SystemExit(f"not in the vocabulary: {', '.join(missing)} (add to {VOCAB_FILE.name}, at the end)")
    if len(names) > MAX_WORDS:
        raise SystemExit(f"{len(names)} words, the box takes {MAX_WORDS} per sentence: {' '.join(names)}")
    return [index[n] for n in names]
