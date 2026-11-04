"""Find where the clip landed on the canvas and score the patches at that place for several matrix readings.
usage: fxplace.py <export.mp4> <case> [frame]"""
import json
import os
import subprocess
import sys

import numpy as np

FX = os.environ.get('JOY_FX_DIR', 'fx')
M = json.load(open(os.path.join(FX, 'manifest.json')))
COLS, ROWS, BITS = M['cols'], M['rows'], M['counterBits']
out, case = sys.argv[1], sys.argv[2]
frame = int(sys.argv[3]) if len(sys.argv) > 3 else 15
info = M['cases'][case]
patches = M['patchesA'] if info['patches'] == 'A' else M['patchesB']
fw, fh = info['w'], info['h']

pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', out], capture_output=True, text=True).stdout)
v = [s for s in pr['streams'] if s['codec_type'] == 'video'][0]
W, H = v['width'], v['height']
print('output video', v['codec_name'], W, H, v.get('pix_fmt'), 'cs', v.get('color_space'), 'pri', v.get('color_primaries'), 'trc', v.get('color_transfer'),
      'range', v.get('color_range'), 'frames', v.get('nb_frames'), 'dur', v.get('duration'))
for s in pr['streams']:
    if s['codec_type'] == 'audio':
        print('audio', s['codec_name'], s.get('sample_rate'), s.get('channels'), 'dur', s.get('duration'))


def decode(matrix, rng):
    vf = (f"select=eq(n\\,{frame}),scale=in_range={rng}:in_color_matrix={matrix}:out_range=full:flags=accurate_rnd+full_chroma_int,format=rgb24")
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', out, '-vf', vf, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(H, W, 3) if len(p.stdout) == W * H * 3 else None


base = decode('bt709', 'tv')
bg = base[H - 5, W - 5].astype(int)
diff = np.abs(base.astype(int) - bg).max(axis=2) > 24
ys, xs = np.where(diff)
print('background pixel', bg.tolist(), 'content bbox x', xs.min(), xs.max(), 'y', ys.min(), ys.max(), 'size', xs.max() - xs.min() + 1, 'x', ys.max() - ys.min() + 1)
x0, y0 = int(xs.min()), int(ys.min())
cw, ch = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
print(f'fixture is {fw}x{fh}; content box {cw}x{ch} at ({x0},{y0}); scale x {cw / fw:.3f}')


def score(img):
    strip = ch // 16
    area = ch - strip
    devs, vals = [], []
    for r in range(ROWS):
        for c in range(COLS):
            cy = y0 + (r * area // ROWS + (r + 1) * area // ROWS) // 2
            cx = x0 + (c * cw // COLS + (c + 1) * cw // COLS) // 2
            blk = img[cy - 6:cy + 6, cx - 6:cx + 6].reshape(-1, 3).mean(axis=0)
            vals.append([int(round(x)) for x in blk])
            devs.append(float(np.abs(blk - np.array(patches[r * COLS + c], float)).max()))
    return devs, vals


for matrix in ('bt709', 'bt601'):
    for rng in ('tv', 'pc'):
        img = decode(matrix, rng)
        devs, vals = score(img)
        print(f'{matrix}/{rng}: worst {max(devs):.1f} mean {np.mean(devs):.1f}')
        if (matrix, rng) in (('bt709', 'tv'), ('bt601', 'tv'), ('bt709', 'pc')):
            print('   patch RGB:', vals)
print('expected  :', [list(p) for p in patches])
