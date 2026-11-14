"""Dominant frequencies every 0.5 s of a 16-bit mono WAV (stdlib). Used 2026-11-14 to find the 2100 Hz answer tone in the
dial-up recording.  python3 -I tools/peaks.py file.wav   (convert first: ffmpeg -i in -ac 1 -ar 8000 out.wav)"""
import wave, sys, math, cmath
w = wave.open(sys.argv[1]); n = w.getnframes(); fr = w.getframerate()
raw = w.readframes(n); x = [int.from_bytes(raw[i:i+2], 'little', signed=True) for i in range(0, len(raw), 2)]
N = 1024
for k0 in range(0, len(x) - N, fr // 2):
    seg = x[k0:k0 + N]
    rms = math.sqrt(sum(v * v for v in seg) / N)
    if rms < 300: print(f"{k0/fr:5.1f}s  quiet"); continue
    mags = []
    for b in range(4, 500):   # 31 Hz .. 3.9 kHz
        f = b * fr / N
        s = sum(seg[i] * cmath.exp(-2j * math.pi * b * i / N) for i in range(0, N, 1))
        mags.append((abs(s), f))
    mags.sort(reverse=True)
    top = sorted({round(f / 10) * 10 for _, f in mags[:4]})
    print(f"{k0/fr:5.1f}s  rms {rms:6.0f}  peaks {top}")
