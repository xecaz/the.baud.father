#!/usr/bin/env python3
"""Synthesize firmware/sounds/tada.wav (stdlib): a short chord, a gap, a long C-major chord with brassy harmonics,
kept under 3.4 kHz for the telephone band. 8 kHz 16-bit mono. Then: python3 -I tools/mksounds.py and flash."""
import math, os, struct, wave
R = 8000
def chord(freqs, dur, attack=0.01, decay=3.0):
    out = []
    for i in range(int(R * dur)):
        t = i / R
        env = min(1, t / attack) * math.exp(-decay * t)
        s = sum(a * math.sin(2 * math.pi * f * h * t) for f in freqs
                for h, a in ((1, 1.0), (2, 0.45), (3, 0.25), (4, 0.12)) if f * h < 3400)
        out.append(env * s)
    return out
C5, E5, G5, C6 = 523.25, 659.25, 783.99, 1046.5
sig = chord([G5 / 1.5, C5, E5], 0.14, decay=6) + [0.0] * int(R * 0.05) + chord([C5, E5, G5, C6], 1.3, decay=2.2)
peak = max(abs(v) for v in sig)
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "firmware", "sounds", "tada.wav")
w = wave.open(p, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(R)
w.writeframes(b"".join(struct.pack("<h", int(v / peak * 30000)) for v in sig)); w.close()
print("wrote", os.path.normpath(p), round(len(sig) / R, 2), "s")
