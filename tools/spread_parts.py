"""Evens out the placement: parts push each other out of crowded areas into empty ones, with a light pull toward the parts they
are wired to. Parts that must stay where they are (ESP32, modem, connectors, SIM tray, holes...) are fixed. Writes new centres."""
import sys, json
import numpy as np

src, out = sys.argv[1], sys.argv[2]
d = json.load(open(src))
W, H = d['W'], d['H']
P = d['parts']
FIXED = {'U201', 'U301', 'J302', 'J301', 'J304', 'C313', 'L301', 'R318', 'X1', 'X2', 'X3', 'X4', 'SV1', 'J101', 'J403', 'H201', 'H202', 'H203', 'H204'}
refs = [r for r in P if not P[r]['back']]
idx = {r: i for i, r in enumerate(refs)}
n = len(refs)
pos = np.array([[P[r]['x'], P[r]['y']] for r in refs], float)
size = np.array([[P[r]['w'], P[r]['h']] for r in refs], float)
fixed = np.array([r in FIXED for r in refs])
home = pos.copy()
EDGE, MARGIN = 1.0, 0.7

# nets that pull parts together (rails and ground would pull everything into one clump)
RAILS = {'GND', 'VSYS', '+3V3', '+3V3_SW', '+12V_SENS', '+5V_SENS', '/MODEM_VBAT', '/SOLAR_P', '/VDD_1V8', 'BATN'}
groups = []
for net, rs in d['nets'].items():
    members = [idx[r] for r in rs if r in idx]
    if net in RAILS or len(members) < 2 or len(members) > 8:
        continue
    groups.append((members, 1.0 / (len(members) - 1)))

def hpwl(p):
    t = 0.0
    for m, _ in groups:
        xy = p[m]; t += (xy[:, 0].max() - xy[:, 0].min()) + (xy[:, 1].max() - xy[:, 1].min())
    return t

# fixed obstacles that are not parts: the battery holder's peg holes
pegs = [np.array(b) for b in d['pegs']]
G = 2.0                                           # density grid cell (mm)
gx, gy = int(np.ceil(W / G)), int(np.ceil(H / G))

def density(p):
    grid = np.zeros((gx, gy))
    for i in range(n):
        x0, x1 = p[i, 0] - size[i, 0] / 2, p[i, 0] + size[i, 0] / 2
        y0, y1 = p[i, 1] - size[i, 1] / 2, p[i, 1] + size[i, 1] / 2
        for cx in range(max(0, int(x0 // G)), min(gx, int(x1 // G) + 1)):
            ox = min(x1, (cx + 1) * G) - max(x0, cx * G)
            if ox <= 0: continue
            for cy in range(max(0, int(y0 // G)), min(gy, int(y1 // G) + 1)):
                oy = min(y1, (cy + 1) * G) - max(y0, cy * G)
                if oy > 0: grid[cx, cy] += ox * oy / (G * G)
    return grid

def blur(a, s):
    k = np.exp(-0.5 * (np.arange(-3 * s, 3 * s + 1) / s) ** 2); k /= k.sum()
    a = np.apply_along_axis(lambda v: np.convolve(v, k, mode='same'), 0, a)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode='same'), 1, a)

def fixed_density():
    grid = np.zeros((gx, gy))
    keep = fixed.copy()
    sav = size.copy()
    q = np.zeros((n, 2)); 
    return grid

_fx = None
def stats(p):
    global _fx
    g = blur(density(p), 2)
    if _fx is None:
        saved = fixed.copy()
        gg = np.zeros((gx, gy))
        for i in range(n):
            if not fixed[i]: continue
            x0, x1 = p[i, 0] - size[i, 0] / 2, p[i, 0] + size[i, 0] / 2
            y0, y1 = p[i, 1] - size[i, 1] / 2, p[i, 1] + size[i, 1] / 2
            gg[max(0, int(x0 // G)):int(x1 // G) + 1, max(0, int(y0 // G)):int(y1 // G) + 1] = 1
        _fx = gg == 0                             # cells not covered by a fixed part
        _fx[:1, :] = False; _fx[-1:, :] = False; _fx[:, :1] = False; _fx[:, -1:] = False
    v = g[_fx]
    return v.std(), v.max()

def resolve(p, margin, rounds):
    """push overlapping boxes apart (fixed parts and peg holes do not move)"""
    for _ in range(rounds):
        moved = 0
        for i in range(n):
            for j in range(i + 1, n):
                if fixed[i] and fixed[j]:
                    continue
                dx = p[j, 0] - p[i, 0]; dy = p[j, 1] - p[i, 1]
                ox = (size[i, 0] + size[j, 0]) / 2 + margin - abs(dx)
                oy = (size[i, 1] + size[j, 1]) / 2 + margin - abs(dy)
                if ox > 0 and oy > 0:
                    moved += 1
                    if ox < oy:
                        s = np.sign(dx) or 1.0; push = np.array([s * ox, 0.0])
                    else:
                        s = np.sign(dy) or 1.0; push = np.array([0.0, s * oy])
                    if fixed[i]: p[j] += push
                    elif fixed[j]: p[i] -= push
                    else: p[j] += push / 2; p[i] -= push / 2
        for i in range(n):
            if fixed[i]: continue
            for b in pegs:
                bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                ox = (size[i, 0] + b[2] - b[0]) / 2 + 0.3 - abs(p[i, 0] - bx); oy = (size[i, 1] + b[3] - b[1]) / 2 + 0.3 - abs(p[i, 1] - by)
                if ox > 0 and oy > 0:
                    moved += 1
                    if ox < oy: p[i, 0] += np.sign(p[i, 0] - bx or 1) * ox
                    else: p[i, 1] += np.sign(p[i, 1] - by or 1) * oy
            p[i, 0] = np.clip(p[i, 0], EDGE + size[i, 0] / 2, W - EDGE - size[i, 0] / 2)
            p[i, 1] = np.clip(p[i, 1], EDGE + size[i, 1] / 2, H - EDGE - size[i, 1] / 2)
        if not moved:
            return True
    return False

s0, m0 = stats(pos); w0 = hpwl(pos)
rng = np.random.default_rng(1)
ITER = 900
for it in range(ITER):
    t = 1.0 - it / ITER
    force = np.zeros((n, 2))
    # light pull toward the other members of each net
    for members, wgt in groups:
        c = pos[members].mean(axis=0)
        force[members] += 0.03 * wgt * (c - pos[members])
    # push out of crowded areas into empty ones
    g = blur(density(pos), 2)
    gradx, grady = np.gradient(g)
    for i in range(n):
        cx = min(gx - 1, max(0, int(pos[i, 0] // G))); cy = min(gy - 1, max(0, int(pos[i, 1] // G)))
        force[i] -= 9.0 * np.array([gradx[cx, cy], grady[cx, cy]])
    force[fixed] = 0
    pos += np.clip(force, -0.8, 0.8) * (0.3 + 0.7 * t)
    resolve(pos, MARGIN, 2)
ok = resolve(pos, MARGIN, 400)
if not ok:
    ok = resolve(pos, 0.3, 400)
def overlaps(p, tol=0.01):
    return [(i, j) for i in range(n) for j in range(i + 1, n)
            if abs(p[i, 0] - p[j, 0]) < (size[i, 0] + size[j, 0]) / 2 - tol and abs(p[i, 1] - p[j, 1]) < (size[i, 1] + size[j, 1]) / 2 - tol]
def leave_obstacles(p):
    """move any part that still sits inside an obstacle (peg hole, antenna keep-out) to the nearest free side"""
    changed = 0
    for i in range(n):
        if fixed[i]: continue
        for b in pegs:
            hw, hh = size[i, 0] / 2 + 0.4, size[i, 1] / 2 + 0.4
            if b[0] - hw < p[i, 0] < b[2] + hw and b[1] - hh < p[i, 1] < b[3] + hh:
                cands = [(b[0] - hw, p[i, 1]), (b[2] + hw, p[i, 1]), (p[i, 0], b[3] + hh)]
                cands = [c for c in cands if EDGE + size[i, 0] / 2 <= c[0] <= W - EDGE - size[i, 0] / 2]
                c = min(cands, key=lambda c: abs(c[0] - p[i, 0]) + abs(c[1] - p[i, 1]))
                p[i] = c; changed += 1
    return changed

leave_obstacles(pos); resolve(pos, MARGIN, 300)
for attempt in range(60):          # nudge any pair that is still touching, then separate again
    leave_obstacles(pos)
    bad = overlaps(pos)
    if not bad:
        ok = True
        break
    for i, j in bad:
        for k in (i, j):
            if not fixed[k]:
                pos[k] += rng.normal(0, 0.8, 2)
    resolve(pos, MARGIN if attempt < 30 else 0.3, 300)
s1, m1 = stats(pos); w1 = hpwl(pos)
bad = [(refs[i], refs[j]) for i in range(n) for j in range(i + 1, n)
       if abs(pos[i, 0] - pos[j, 0]) < (size[i, 0] + size[j, 0]) / 2 - 0.01 and abs(pos[i, 1] - pos[j, 1]) < (size[i, 1] + size[j, 1]) / 2 - 0.01]
print(f'overlap-free: {ok}; overlaps left: {bad}')
print(f'density spread (std, lower = more even): {s0:.3f} -> {s1:.3f}; densest area {m0:.2f} -> {m1:.2f}')
print(f'wiring length of signal nets: {w0:.0f} -> {w1:.0f} mm')
json.dump({r: [float(pos[idx[r], 0]), float(pos[idx[r], 1])] for r in refs}, open(out, 'w'))
