"""Builds JOY Media export test fixtures with ffmpeg. Output: a NEW folder given as argv[1].
Patches are flat colours with known sRGB values; a 12-bit frame counter strip sits at the bottom."""
import hashlib
import json
import os
import subprocess
import sys

import numpy as np

FX = sys.argv[1]
if os.path.exists(FX) and os.listdir(FX):
    raise SystemExit('refusing: output folder is not empty')
os.makedirs(FX, exist_ok=True)

PA = [(235, 235, 235), (16, 16, 16), (180, 40, 40), (40, 160, 60), (50, 60, 200), (200, 180, 40),
      (40, 180, 190), (190, 60, 170), (128, 128, 128), (90, 50, 20), (240, 140, 40), (30, 90, 60)]
PB = [(30, 100, 220), (220, 60, 60), (60, 200, 120), (240, 220, 60), (150, 50, 150), (20, 20, 20),
      (230, 230, 230), (100, 100, 40), (40, 200, 200), (200, 100, 160), (80, 80, 240), (160, 200, 40)]
FRAMES = 180
FPS = 30
COLS, ROWS, BITS = 3, 4, 12


def geometry(w, h):
    strip = h // 16
    return strip, h - strip


def base_image(w, h, patches):
    strip, area = geometry(w, h)
    img = np.zeros((h, w, 3), np.uint8)
    for r in range(ROWS):
        for c in range(COLS):
            img[r * area // ROWS:(r + 1) * area // ROWS, c * w // COLS:(c + 1) * w // COLS] = patches[r * COLS + c]
    return img


def write_frames(proc, w, h, patches, nframes):
    img = base_image(w, h, patches)
    strip, area = geometry(w, h)
    for n in range(nframes):
        for i in range(BITS):
            img[area:h, i * w // BITS:(i + 1) * w // BITS] = 235 if (n >> i) & 1 else 16
        proc.stdin.write(img.tobytes())
    proc.stdin.close()


def run_ffmpeg(name, w, h, patches, vf, vcodec_args, tag_args, audio=None, container='mp4', nframes=FRAMES, extra_out=None):
    out = os.path.join(FX, name)
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{w}x{h}', '-r', str(FPS), '-i', '-']
    if audio:
        cmd += ['-f', 'lavfi', '-i', f"sine=frequency={audio[0]}:sample_rate={audio[1]}:duration=6"]
    cmd += ['-vf', vf, '-map', '0:v:0']
    if audio:
        cmd += ['-map', '1:a:0', '-c:a', 'aac', '-b:a', '128k', '-ar', str(audio[1]), '-t', '6']
    cmd += vcodec_args + tag_args + (extra_out or []) + [out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    write_frames(proc, w, h, patches, nframes)
    rc = proc.wait()
    if rc != 0:
        raise SystemExit(f'ffmpeg failed for {name}: {rc}')
    print('built', name, flush=True)
    return out


def conv(matrix, rng, pix='yuv420p', untag=False):
    s = (f'scale=in_range=full:out_range={rng}:out_color_matrix={matrix}:flags=accurate_rnd+full_chroma_int,'
         f'format={pix}')
    if untag:
        s += ',setparams=colorspace=unknown:color_primaries=unknown:color_trc=unknown:range=unknown'
    return s


X264 = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-g', '60', '-bf', '2', '-profile:v', 'high']
T709 = ['-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv']
T601 = ['-colorspace', 'smpte170m', '-color_primaries', 'smpte170m', '-color_trc', 'smpte170m', '-color_range', 'tv']
T709F = ['-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'pc']

cases = {}  # name -> info for the manifest


def reg(name, **kw):
    cases[name] = kw


W, H = 1080, 1920
run_ffmpeg('c0-control-bt709.mp4', W, H, PA, conv('bt709', 'tv'), X264, T709, audio=(440, 48000))
reg('c0-control-bt709.mp4', w=W, h=H, patches='A', matrix='bt709', range='tv', audio='440Hz/48000')

run_ffmpeg('c1-sd-bt601-tagged.mp4', 360, 640, PA, conv('bt601', 'tv'), X264, T601)
reg('c1-sd-bt601-tagged.mp4', w=360, h=640, patches='A', matrix='bt601', range='tv', note='tagged smpte170m')
run_ffmpeg('c2-sd-bt601-untagged.mp4', 360, 640, PA, conv('bt601', 'tv', untag=True), X264, [])
reg('c2-sd-bt601-untagged.mp4', w=360, h=640, patches='A', matrix='bt601', range='tv', note='no colour tags; data is BT.601')

run_ffmpeg('c3-fullrange-bt709.mp4', W, H, PA, conv('bt709', 'pc'), X264, T709F)
reg('c3-fullrange-bt709.mp4', w=W, h=H, patches='A', matrix='bt709', range='pc')

# rotated: stored landscape, display rotation in the container
for angle, tr in ((90, 'transpose=1'), (270, 'transpose=2')):
    stored = f'c4-stored-for-rot{angle}.mp4'
    run_ffmpeg(stored, W, H, PA, tr + ',' + conv('bt709', 'tv'), X264, T709)
    final = os.path.join(FX, f'c4-rot{angle}.mp4')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-display_rotation', str(angle),
                    '-i', os.path.join(FX, stored), '-c', 'copy', final], check=True)
    print('built', f'c4-rot{angle}.mp4', flush=True)
    reg(f'c4-rot{angle}.mp4', w=W, h=H, patches='A', matrix='bt709', range='tv', note=f'stored 1920x1080, display rotation {angle} ccw; expected display 1080x1920')

# variable frame rate: 30 fps for the first 3 s, then every second frame (15 fps)
run_ffmpeg('c5-vfr.mp4', W, H, PA, "select='lt(n,90)+not(mod(n,2))'," + conv('bt709', 'tv'), X264, T709,
           extra_out=['-fps_mode', 'vfr'])
reg('c5-vfr.mp4', w=W, h=H, patches='A', matrix='bt709', range='tv', note='counter strip shows original frame numbers; frames kept: n<90 and even n after')

run_ffmpeg('c6-h264-10bit.mp4', W, H, PA, conv('bt709', 'tv', pix='yuv420p10le'),
           ['-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-g', '60', '-profile:v', 'high10'], T709)
reg('c6-h264-10bit.mp4', w=W, h=H, patches='A', matrix='bt709', range='tv')

run_ffmpeg('c7-hevc.mp4', W, H, PA, conv('bt709', 'tv'),
           ['-c:v', 'libx265', '-crf', '18', '-preset', 'medium', '-tag:v', 'hvc1', '-x265-params', 'log-level=error:keyint=60'], T709)
reg('c7-hevc.mp4', w=W, h=H, patches='A', matrix='bt709', range='tv')

run_ffmpeg('c8-vp9.webm', W, H, PA, conv('bt709', 'tv'),
           ['-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '28', '-row-mt', '1', '-g', '60'], T709)
reg('c8-vp9.webm', w=W, h=H, patches='A', matrix='bt709', range='tv')

run_ffmpeg('c9-av1.webm', W, H, PA, conv('bt709', 'tv'),
           ['-c:v', 'libsvtav1', '-crf', '28', '-preset', '8', '-g', '60'], T709)
reg('c9-av1.webm', w=W, h=H, patches='A', matrix='bt709', range='tv')

run_ffmpeg('c10-interlaced-tff.mp4', W, H, PA, conv('bt709', 'tv') + ',interlace=scan=tff',
           ['-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-g', '60', '-profile:v', 'high',
            '-flags', '+ilme+ildct', '-top', '1'], T709)
reg('c10-interlaced-tff.mp4', w=W, h=H, patches='A', matrix='bt709', range='tv', note='interlaced tff; 15 fps frames of two fields (counter strip shows combing)')

# two-clip transition fixtures
run_ffmpeg('c11-clipA.mp4', W, H, PA, conv('bt709', 'tv'), X264, T709, audio=(440, 48000))
reg('c11-clipA.mp4', w=W, h=H, patches='A', matrix='bt709', range='tv', audio='440Hz/48000')
run_ffmpeg('c11-clipB.mp4', W, H, PB, conv('bt709', 'tv'), X264, T709, audio=(880, 48000))
reg('c11-clipB.mp4', w=W, h=H, patches='B', matrix='bt709', range='tv', audio='880Hz/48000')

# audio sample-rate pair
run_ffmpeg('c13-sine1k-44100.mp4', W, H, PA, conv('bt709', 'tv'), X264, T709, audio=(1000, 44100))
reg('c13-sine1k-44100.mp4', w=W, h=H, patches='A', matrix='bt709', range='tv', audio='1000Hz/44100')
run_ffmpeg('c13-sine1k-48000.mp4', W, H, PA, conv('bt709', 'tv'), X264, T709, audio=(1000, 48000))
reg('c13-sine1k-48000.mp4', w=W, h=H, patches='A', matrix='bt709', range='tv', audio='1000Hz/48000')

manifest = {
    'patchesA': PA, 'patchesB': PB, 'cols': COLS, 'rows': ROWS, 'counterBits': BITS, 'frames': FRAMES, 'fps': FPS,
    'geometry': 'strip_h = h//16; patch area = h - strip_h; 3 columns x 4 rows row-major; counter = 12 squares across the bottom strip, bit i = n>>i, 235 = 1, 16 = 0',
    'cases': {},
}
for n, info in cases.items():
    p = os.path.join(FX, n)
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    info['sha256'] = h.hexdigest()
    info['bytes'] = os.path.getsize(p)
    manifest['cases'][n] = info
with open(os.path.join(FX, 'manifest.json'), 'w') as f:
    json.dump(manifest, f, indent=1)
print('manifest written', flush=True)
