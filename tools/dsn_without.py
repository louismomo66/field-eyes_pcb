"""Takes nets out of the autorouter's input (ground comes from the pours; the RF lines are routed by hand)."""
import sys
src, dst, *nets = sys.argv[1:]
s = open(src).read()
for n in nets:
    key = f'    (net {n}\n'
    if key not in s:
        key = f'    (net "{n}"\n'
    if key not in s:
        print('not found:', n); continue
    i = s.index(key); d = 0; j = i
    while True:
        d += (s[j] == '('); d -= (s[j] == ')')
        if d == 0: break
        j += 1
    s = s[:i] + s[j + 1:].lstrip('\n')
    for form in (f' {n}\n', f' "{n}"\n'):
        s = s.replace(form, '\n')
    print('removed', n)
open(dst, 'w').write(s)
