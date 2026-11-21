#!/usr/bin/env python3
"""Make the Baudfather say a sentence built from its vocabulary (tools/vocab.txt).

Stdlib only; sends over Bluetooth with the system's bluetoothctl, like mailbell.py (the laptop must be paired).

    python3 -I tools/say.py backup done
    python3 -I tools/say.py 3 new messages            # numbers are spelled out: 42 -> forty two, 3.5, -7, 80%
    python3 -I tools/say.py meeting in 5 minutes
    long_job; python3 -I tools/say.py job finished || python3 -I tools/say.py job failed
    python3 -I tools/say.py --list                    # the words
    python3 -I tools/say.py --print 3 new messages    # the line for the USB console (":say 4 72 49"), sends nothing
    python3 -I tools/say.py --wav /tmp/x.wav 3 new messages   # the sentence as a WAV to listen to here, sends nothing

At most 16 words per sentence. "," is a short pause. The box queues it like a message: said after a running ring.
"""
import argparse
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # python3 -I drops the script's folder
import mailbell
import vocab

SAY = 0x40                 # BLE_CMD_SAY in firmware/main/ble.h
WORD_GAP_MS = 60           # T_WORD_GAP in firmware/main/config.h
CLIPS = Path(__file__).resolve().parent.parent / "firmware" / "sounds" / "vocab"


def to_wav(path, numbers, words):
    """Roughly what the box plays (before the 8 kHz conversion and the modem speaker)."""
    out, rate = b"", None
    for k, n in enumerate(numbers):
        name, text = words[n]
        if text == "-":
            out += b"\0\0" * int((rate or 22050) * 0.25)
            continue
        with wave.open(str(CLIPS / f"{name}.wav"), "rb") as w:
            rate = w.getframerate()
            if k:
                out += b"\0\0" * int(rate * WORD_GAP_MS / 1000)
            out += w.readframes(w.getnframes())
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate or 22050)
        w.writeframes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words", nargs="*", help="words from the vocabulary, and numbers")
    ap.add_argument("--list", action="store_true", help="show the vocabulary and exit")
    ap.add_argument("--print", action="store_true", dest="show", help="print the console line, send nothing")
    ap.add_argument("--wav", type=Path, help="write the sentence to this WAV, send nothing")
    ap.add_argument("--box", help="the box's BLE address (default: the paired device named \"%s\")" % mailbell.BOX_NAME)
    a = ap.parse_args()
    words = vocab.load()
    if a.list:
        print(" ".join(name for name, _ in words))
        return
    if not a.words:
        ap.error("nothing to say")
    numbers = vocab.sentence(a.words, words)
    line = " ".join(words[n][0] for n in numbers)
    if a.show:
        print(":say " + " ".join(str(n) for n in numbers) + "    # " + line)
        return
    if a.wav:
        to_wav(a.wav, numbers, words)
        print(f"{a.wav}: {line}")
        return
    box = a.box or mailbell.find_box()
    if not box:
        sys.exit(f"no paired Bluetooth device named {mailbell.BOX_NAME!r}: pair the laptop with the box first, or pass --box")
    ok = mailbell.write([SAY] + numbers, box)
    print(f"{line}: {'sent' if ok else 'FAILED (box out of range, or not paired)'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
