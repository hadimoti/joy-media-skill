"""Self-check of the fixtures: decode one frame per file with the right matrix and compare patch centres with the known colours."""
import json
import os
import subprocess
import sys

import numpy as np

FX = sys.argv[1]
M = json.load(open(os.path.join(FX, 'manifest.json')))
COLS, ROWS, BITS = M['cols'], M['rows'], M['counterBits']


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', path], capture_output=True, text=True).stdout
    d = json.loads(out)
    res = []
    for s in d['streams']:
        if s['codec_type'] == 'video':
            rot = None
            for sd in s.get('side_data_list', []):
                if 'rotation' in sd:
                    rot = sd['rotation']
            res.append(f"{s['codec_name']} {s.get('profile', '')} {s.get('pix_fmt')} {s['width']}x{s['height']} "
                       f"cs={s.get('color_space')} pri={s.get('color_primaries')} trc={s.get('color_transfer')} range={s.get('color_range')} "
                       f"rot={rot} fps={s.get('avg_frame_rate')} frames={s.get('nb_frames')} field={s.get('field_order')}")
        elif s['codec_type'] == 'audio':
            res.append(f"audio {s['codec_name']} {s.get('sample_rate')}Hz dur={s.get('duration')}")
    return '; '.join(res)


def decode(path, index, w, h, matrix, rng):
    vf = (f"select=eq(n\\,{index}),scale=in_range={rng}:in_color_matrix={matrix}:out_range=full:"
          f"flags=accurate_rnd+full_chroma_int,format=rgb24")
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', vf, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                       capture_output=True)
    raw = p.stdout
    if len(raw) != w * h * 3:
        return None
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3)


def patches_dev(img, patches):
    h, w, _ = img.shape
    strip = h // 16
    area = h - strip
    worst = 0
    per = []
    for r in range(ROWS):
        for c in range(COLS):
            cy = (r * area // ROWS + (r + 1) * area // ROWS) // 2
            cx = (c * w // COLS + (c + 1) * w // COLS) // 2
            blk = img[cy - 8:cy + 8, cx - 8:cx + 8].reshape(-1, 3).mean(axis=0)
            exp = np.array(patches[r * COLS + c], float)
            d = np.abs(blk - exp).max()
            per.append(round(float(d), 1))
            worst = max(worst, d)
    return worst, per


def counter(img):
    h, w, _ = img.shape
    strip = h // 16
    y = h - strip // 2
    val = 0
    for i in range(BITS):
        x = (i * w // BITS + (i + 1) * w // BITS) // 2
        if img[y - 4:y + 4, x - 4:x + 4].mean() > 128:
            val |= 1 << i
    return val


lines = []
for name, info in M['cases'].items():
    path = os.path.join(FX, name)
    patches = M['patchesA'] if info['patches'] == 'A' else M['patchesB']
    img = decode(path, 15, info['w'], info['h'], info['matrix'], info['range'])
    line = f"{name}: {probe(path)}"
    if img is None:
        line += ' | DECODE SIZE MISMATCH'
    else:
        worst, per = patches_dev(img, patches)
        line += f" | patch worst dev {worst:.1f} {per} | counter@15={counter(img)}"
        if name == 'c5-vfr.mp4':
            img2 = decode(path, 100, info['w'], info['h'], info['matrix'], info['range'])
            line += f" | counter@idx100={counter(img2) if img2 is not None else None} (expect 110)"
    lines.append(line)
    print(line, flush=True)
open(os.path.join(FX, 'selfcheck.txt'), 'w').write('\n'.join(lines))
