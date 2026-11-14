"""Pitch over time of a WAV (stdlib); used 2026-11-09 to measure the clips/tone from a phone video.  python3 -I tools/pitch.py file.wav"""
import wave,sys,math,struct
w=wave.open(sys.argv[1]);n=w.getnframes();r=w.getframerate()
x=struct.unpack('<%dh'%n,w.readframes(n))
print("length %.1f s"%(n/r))
win=2048
for start in range(0,n-win,r//4):
    seg=x[start:start+win]
    rms=math.sqrt(sum(v*v for v in seg)/win)
    if rms<300: continue
    best=(0,0)
    for f in range(200,2000,5):
        c=s=0.0
        for i,v in enumerate(seg):
            a=2*math.pi*f*i/r; c+=v*math.cos(a); s+=v*math.sin(a)
        p=c*c+s*s
        if p>best[0]: best=(p,f)
    print("%5.2f s  rms %5d  peak %d Hz"%(start/r,rms,best[1]))
