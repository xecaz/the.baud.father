#!/usr/bin/env python3
"""Build the sound bank for the "sounds" flash partition (firmware/main/audio.c).

Stdlib only. Clips: a few synthesized test sounds, plus every WAV in firmware/sounds/
(or the files given on the command line). Each clip is converted to 8 kHz, 8-bit unsigned
mono, low-pass filtered for the telephone band, and normalized.

    python3 -I tools/mksounds.py                 # builtins + firmware/sounds/*.wav
    python3 -I tools/mksounds.py --list          # show what would go in, and the size
    cd firmware && idf.py flash                  # flashes the app and firmware/sounds/bank.bin

The clip name is the file name without extension (max 23 characters); config.h picks clips by name.
Vocabulary words (tools/vocab.txt, clips from firmware/sounds/vocab/, made by mkspeech.py --vocab) go in as
"wNNN.name", NNN = the word's number; the firmware finds them by that prefix. Not with WAVs on the command line.
WAV input: PCM 8/16/24/32-bit, any rate, mono or stereo. Other formats: convert first, e.g.
    ffmpeg -i in.mp3 -ac 1 -ar 8000 out.wav      or      sox in.flac -c 1 -r 8000 out.wav

Bank layout (little endian; keep in sync with audio.c):
    header: "SNDB", u16 version=1, u16 count, u32 rate, u32 data_end
    entries: char name[24], u32 offset, u32 length   (offsets from the partition start)
    data: u8 PCM, 128 = silence
"""
import argparse
import math
import random
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # tools/vocab.py (python3 -I drops the script's folder)
import vocab

RATE = 8000
PARTITION_SIZE = 0x270000          # firmware/partitions.csv "sounds"
NAME_LEN = 24
HEADER = struct.Struct("<4sHHII")
ENTRY = struct.Struct("<24sII")
ROOT = Path(__file__).resolve().parent.parent
SOUND_DIR = ROOT / "firmware" / "sounds"


# ---------------- builtin test sounds (generated at RATE, floats in -1..1) ----------------

def bell(freq, dur, amp=1.0):
    """Struck bell: inharmonic partials, each decaying at its own rate."""
    partials = ((1.0, 1.0, 1.6), (2.0, 0.5, 2.5), (2.76, 0.35, 3.5), (5.4, 0.15, 6.0))
    n = int(dur * RATE)
    out = []
    for i in range(n):
        t = i / RATE
        attack = min(1.0, t / 0.004)
        v = sum(a * math.exp(-d * t) * math.sin(2 * math.pi * freq * m * t) for m, a, d in partials)
        out.append(amp * attack * v / 2.0)
    return out


def mix_at(dst, src, start_s):
    i0 = int(start_s * RATE)
    need = i0 + len(src)
    if len(dst) < need:
        dst.extend([0.0] * (need - len(dst)))
    for i, v in enumerate(src):
        dst[i0 + i] += v
    return dst


def dingdong():
    out = []
    mix_at(out, bell(659.25, 1.2), 0.0)    # E5
    mix_at(out, bell(523.25, 1.8), 0.55)   # C5
    return out


def phone_ring():
    """Old electromechanical bell: two gongs hit ~20 times a second, 2 s on, 1 s off, twice."""
    out = []
    for burst in (0.0, 3.0):
        n = int(2.0 * RATE)
        for i in range(n):
            t = i / RATE
            hit = (t * 20.0) % 1.0                      # time since the last strike, in strikes
            env = math.exp(-hit * 4.0) * min(1.0, t / 0.01) * min(1.0, (2.0 - t) / 0.05)
            v = 0.6 * math.sin(2 * math.pi * 1150 * t) + 0.4 * math.sin(2 * math.pi * 1450 * t)
            mix_at(out, [v * env * 0.9], burst + t)
    return out


def sweep():
    """300 -> 3400 Hz exponential sweep, 2 s: checks the whole telephone band."""
    n = int(2.0 * RATE)
    f0, f1 = 300.0, 3400.0
    k = math.log(f1 / f0) / 2.0
    out = []
    for i in range(n):
        t = i / RATE
        phase = 2 * math.pi * f0 * (math.exp(k * t) - 1) / k
        fade = min(1.0, t / 0.02, (2.0 - t) / 0.02)
        out.append(0.8 * fade * math.sin(phase))
    return out


def beep():
    n = int(0.3 * RATE)
    return [0.8 * min(1.0, i / 80, (n - i) / 80) * math.sin(2 * math.pi * 1000 * i / RATE) for i in range(n)]


BUILTINS = {"dingdong": dingdong, "ring": phone_ring, "sweep": sweep, "beep": beep}


# ---------------- WAV input ----------------

def read_wav(path):
    try:
        w = wave.open(str(path), "rb")
    except wave.Error as e:
        sys.exit(f"{path}: {e} (only PCM WAV; convert with ffmpeg/sox, see --help)")
    with w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 1:
        vals = [(b - 128) / 128.0 for b in raw]
    elif width in (2, 3, 4):
        full = float(1 << (8 * width - 1))
        vals = [int.from_bytes(raw[i:i + width], "little", signed=True) / full
                for i in range(0, len(raw), width)]
    else:
        sys.exit(f"{path}: {width * 8}-bit samples not supported")
    mono = [sum(vals[i:i + ch]) / ch for i in range(0, len(vals), ch)]
    return mono, rate


def resample(x, rate_in, rate_out=RATE, half_taps=16):
    """Windowed-sinc resampler; the cutoff sits just under the lower Nyquist (anti-aliasing)."""
    if rate_in == rate_out:
        return list(x)
    ratio = rate_in / rate_out
    cutoff = 0.45 * min(1.0, 1.0 / ratio)          # in cycles per input sample
    width = half_taps * max(1.0, ratio)            # input samples each side
    n_out = int(len(x) / ratio)
    out = []
    for j in range(n_out):
        c = j * ratio
        i0, i1 = max(0, int(c - width)), min(len(x) - 1, int(c + width))
        acc = 0.0
        for i in range(i0, i1 + 1):
            d = i - c
            win = 0.5 + 0.5 * math.cos(math.pi * d / width)       # Hann
            s = 2 * cutoff if d == 0 else math.sin(2 * math.pi * cutoff * d) / (math.pi * d)
            acc += x[i] * s * win
        out.append(acc)
    return out


# ---------------- output ----------------

def normalize(x, peak=0.9):
    m = max((abs(v) for v in x), default=0.0)
    return [v * peak / m for v in x] if m > 0 else x


def to_u8(x, rng):
    out = bytearray(len(x))
    for i, v in enumerate(x):
        d = (rng.random() - rng.random()) / 128.0              # TPDF dither, 1 LSB
        out[i] = max(0, min(255, int(round(128 + 127 * (v + d)))))
    return bytes(out)


def build(clips):
    count = len(clips)
    pos = HEADER.size + count * ENTRY.size
    entries, data = [], bytearray()
    for name, pcm in clips:
        entries.append(ENTRY.pack(name.encode()[:NAME_LEN - 1], pos + len(data), len(pcm)))
        data += pcm
    data_end = pos + len(data)
    return HEADER.pack(b"SNDB", 1, count, RATE, data_end) + b"".join(entries) + bytes(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wavs", nargs="*", type=Path, help=f"WAV files (default: {SOUND_DIR}/*.wav)")
    ap.add_argument("-o", "--out", type=Path, default=SOUND_DIR / "bank.bin")
    ap.add_argument("--no-builtin", action="store_true", help="leave out the synthesized test sounds")
    ap.add_argument("--no-normalize", action="store_true")
    ap.add_argument("--list", action="store_true", help="show the clips and sizes, write nothing")
    args = ap.parse_args()

    wavs = args.wavs or sorted(SOUND_DIR.glob("*.wav"))
    rng = random.Random(1)                     # fixed seed: same input, same bank
    clips, names = [], set()

    def add(name, samples, peak=0.9):
        if len(name) > NAME_LEN - 1:
            sys.exit(f"clip name too long (max {NAME_LEN - 1}): {name}")
        if name in names:
            sys.exit(f"duplicate clip name: {name}")
        names.add(name)
        if not args.no_normalize:
            samples = normalize(samples, peak)
        clips.append((name, to_u8(samples, rng)))

    if not args.no_builtin:
        for name, fn in BUILTINS.items():
            add(name, fn())
    for p in wavs:
        x, rate = read_wav(p)
        add(p.stem, resample(x, rate))
    missing = []
    if not args.wavs:
        for i, (name, text) in enumerate(vocab.load()):
            p = SOUND_DIR / "vocab" / f"{name}.wav"
            if text == "-":
                add(vocab.clip_name(i, name), [0.0] * int(0.25 * RATE))
            elif p.exists():
                x, rate = read_wav(p)
                add(vocab.clip_name(i, name), resample(x, rate))
            else:
                missing.append(name)

    bank = build(clips)
    for name, pcm in clips:
        print(f"  {name:<23} {len(pcm) / RATE:6.2f} s  {len(pcm) / 1024:7.1f} KB")
    if missing:
        print(f"vocabulary words without a clip (run tools/mkspeech.py --vocab): {', '.join(missing)}")
    if len(clips) > 256:
        sys.exit(f"{len(clips)} clips, the firmware takes 256 (BANK_MAX_CLIPS in audio.c)")
    print(f"bank: {len(clips)} clips, {len(bank) / 1024:.1f} KB of {PARTITION_SIZE // 1024} KB")
    if len(bank) > PARTITION_SIZE:
        sys.exit("too big for the sounds partition")
    if args.list:
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(bank)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
