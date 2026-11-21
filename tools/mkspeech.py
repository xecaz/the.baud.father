#!/usr/bin/env python3
"""Spoken clips for the sound bank, in the style of the Amiga's narrator (flat, robotic formant voice).

Stdlib only: drives the system's libespeak-ng.so.1 (Debian package libespeak-ng1, already on the laptop as a
dependency of speech-dispatcher) through ctypes. No espeak-ng command needed, nothing is played.

    python3 -I tools/mkspeech.py                          # the default phrases -> firmware/sounds/<name>.wav
    python3 -I tools/mkspeech.py door="Someone is at the door"
    python3 -I tools/mkspeech.py --style klatt --out /tmp/x whatsapp="Whats app message"
    python3 -I tools/mkspeech.py --list                   # styles
    python3 -I tools/mkspeech.py --vocab                  # every word in tools/vocab.txt -> firmware/sounds/vocab/<name>.wav

Then: python3 -I tools/mksounds.py  (converts to 8 kHz for the bank), and flash.
Output: 16-bit mono WAV at the synthesizer's rate (22050 Hz), 150 ms of silence before and after.
Vocabulary words are cut tight instead (20 ms each side): the box strings them together (T_WORD_GAP in config.h).
"""
import argparse
import ctypes
import math
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # tools/vocab.py (python3 -I drops the script's folder)
import vocab

PHRASES = {"whatsapp": "Whats app message", "signal": "Signal message", "email": "Incoming e-mail", "food": "Food update"}

# name: (voice, rate wpm, pitch 0-99, pitch range 0-99 (0 = monotone), 8-bit crunch)
STYLES = {
    "amiga":   ("en-us",           140, 35, 0, True),    # monotone, slow, low: narrator.device "robotic"
    "amiga2":  ("en-us",           150, 45, 12, True),   # a little melody: narrator "natural"
    "klatt":   ("en-us+klatt",     140, 35, 0, True),    # Klatt synthesizer variant (buzzier)
    "klatt4":  ("en-us+klatt4",    140, 35, 0, True),
    "robot":   ("en-us+robosoft",  140, 40, 0, True),    # the default (picked by ear, 2026-11-14)
    "plain":   ("en-us",           160, 50, 50, False),  # espeak as it comes, for comparison
}

RATE, VOLUME, PITCH, RANGE = 1, 2, 3, 4       # espeak_PARAMETER
AUDIO_OUTPUT_SYNCHRONOUS = 2
POS_CHARACTER = 1
CHARS_UTF8 = 1


def synth(lib, text):
    chunks = []
    CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)

    def cb(wav, n, events):
        if wav and n > 0:
            chunks.append(ctypes.string_at(wav, n * 2))
        return 0

    keep = CB(cb)
    lib.espeak_SetSynthCallback(keep)
    data = text.encode() + b"\0"
    err = lib.espeak_Synth(data, len(data), 0, POS_CHARACTER, 0, CHARS_UTF8, None, None)
    if err:
        sys.exit(f"espeak_Synth failed ({err})")
    lib.espeak_Synchronize()
    raw = b"".join(chunks)
    return list(struct.unpack(f"<{len(raw) // 2}h", raw))


# Phrases that came out too quiet on the box: name -> (high-pass Hz before the clipper, drive). "Food update" is
# mostly "oo"/"u": its energy sits below ~500 Hz, which the line transformer and the modem speaker barely pass, so it
# was "barely hearable" (user, 2026-11-15). The high-pass moves the level to the harmonics the speaker does play.
LOUD = {"food": (700, 10.0)}

DRIVE = 4.0   # loudness: soft-clip gain before the 8-bit step (1 = none). 4 is roughly +9 dB louder at the same peak.


def highpass(x, hz, rate):
    """First-order high-pass, applied twice (12 dB/octave)."""
    a = 1 / (1 + 2 * math.pi * hz / rate)
    for _ in range(2):
        y, px, py = [], 0.0, 0.0
        for v in x:
            py = a * (py + v - px)
            px = v
            y.append(py)
        x = y
    return x


def trim(x, rate, keep_ms=20, floor=0.02):
    """Cut the silence off both ends, leaving keep_ms."""
    lim = max(abs(v) for v in x) * floor
    loud = [i for i, v in enumerate(x) if abs(v) > lim]
    k = int(rate * keep_ms / 1000)
    return x[max(0, loud[0] - k):loud[-1] + 1 + k]


def rms(x):
    return math.sqrt(sum(v * v for v in x) / max(1, len(x)))


# Vocabulary words are levelled by a rough measure of what the modem speaker plays: the RMS above SPEAKER_HP Hz of the
# finished clip ("Food update", the phrase that was too quiet by ear, also measures lowest of the phrases). A word
# below QUIET_RATIO of the list's median is redone with the high-pass/drive pair from QUIET_FIXES that lands closest
# to the median. LOUD is for whole phrases (tuned by ear) and is not used here.
SPEAKER_HP = 600
QUIET_RATIO = 0.75
QUIET_FIXES = [(hp, drive) for hp in (300, 500, 700) for drive in (4.0, 6.0, 10.0)]


def speaker_level(x, rate):
    return rms(highpass(x, SPEAKER_HP, rate))


def make_vocab(lib, rate, out):
    """Every word of tools/vocab.txt -> out/vocab/<name>.wav."""
    out = out / "vocab"
    out.mkdir(parents=True, exist_ok=True)
    words = [(n, t) for n, t in vocab.load() if t != "-"]
    raw = {n: trim(synth(lib, t), rate) for n, t in words}
    clips = {n: crunch(raw[n]) for n, _ in words}
    levels = {n: speaker_level(c, rate) for n, c in clips.items()}
    median = sorted(levels.values())[len(levels) // 2]
    fixed = []
    for n, _ in words:
        if levels[n] >= QUIET_RATIO * median:
            continue
        tries = [(crunch(highpass(raw[n], hp, rate), drive), hp, drive) for hp, drive in QUIET_FIXES]
        best = min(tries, key=lambda t: abs(speaker_level(t[0], rate) - median))
        clips[n] = best[0]
        fixed.append(f"{n} {levels[n] / median:.2f} -> {speaker_level(best[0], rate) / median:.2f} "
                     f"(high-pass {best[1]} Hz, drive {best[2]:g})")
    total = 0.0
    for n, _ in words:
        write_wav(out / f"{n}.wav", clips[n], rate)
        total += len(clips[n]) / rate
    print(f"{out}: {len(words)} words, {total:.1f} s")
    print("quiet words raised (speaker level against the median):" + ("".join("\n  " + f for f in fixed) or " none"))


def write_wav(path, x, rate):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{len(x)}h", *x))


def crunch(x, drive=DRIVE):
    """Normalize, push into a soft clipper (louder at the same peak: the DAC is already at full scale), then
    8-bit quantize like the Amiga's DAC."""
    peak = max(1, max(abs(v) for v in x))
    norm = math.tanh(drive)
    out = []
    for v in x:
        q = round(math.tanh(v / peak * drive) / norm * 120)   # -120..120
        out.append(int(q * 32767 / 127))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phrases", nargs="*", help='name="text" pairs (default: %s)' % ", ".join(PHRASES))
    ap.add_argument("--style", default="robot", choices=sorted(STYLES))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "firmware" / "sounds"))
    ap.add_argument("--suffix", default="", help="appended to each file name (for comparing styles)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--vocab", action="store_true", help="make the vocabulary words (tools/vocab.txt) instead of phrases")
    a = ap.parse_args()
    if a.list:
        for k, v in STYLES.items():
            print(f"{k:8} voice {v[0]}, {v[1]} wpm, pitch {v[2]}, range {v[3]}")
        return
    phrases = dict(PHRASES)
    if a.phrases:
        phrases = {}
        for p in a.phrases:
            if "=" not in p:
                sys.exit(f'expected name="text", got {p!r}')
            k, t = p.split("=", 1)
            phrases[k] = t

    lib = ctypes.CDLL("libespeak-ng.so.1")
    lib.espeak_Synth.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int, ctypes.c_uint,
                                 ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    rate = lib.espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS, 0, None, 0)
    if rate <= 0:
        sys.exit("espeak_Initialize failed")
    voice, wpm, pitch, rng, do_crunch = STYLES[a.style]
    if lib.espeak_SetVoiceByName(voice.encode()):
        sys.exit(f"voice {voice} not found")
    for param, val in ((RATE, wpm), (PITCH, pitch), (RANGE, rng), (VOLUME, 100)):
        lib.espeak_SetParameter(param, val, 0)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.vocab:
        make_vocab(lib, rate, out)
        lib.espeak_Terminate()
        return
    pad = [0] * int(rate * 0.15)
    for name, text in phrases.items():
        x = synth(lib, text)
        if not x:
            sys.exit(f"no audio for {text!r}")
        hp, drive = LOUD.get(name, (0, DRIVE))
        if hp:
            x = highpass(x, hp, rate)
        if do_crunch:
            x = crunch(x, drive)
        x = pad + x + pad
        path = out / f"{name}{a.suffix}.wav"
        write_wav(path, x, rate)
        print(f"{path}: {text!r}, {len(x) / rate:.2f} s, style {a.style}")
    lib.espeak_Terminate()


if __name__ == "__main__":
    main()
