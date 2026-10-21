"""Minimal KiCad s-expression reader/writer."""
import re, uuid
TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')

def parse(s):
    stack = [[]]
    for m in TOK.finditer(s):
        t = m.group(0)
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop(); stack[-1].append(x)
        else:
            stack[-1].append(t)
    return stack[0]

def dump(x, ind=0):
    if not isinstance(x, list):
        return x
    parts = [dump(e, ind + 1) for e in x]
    flat = '(' + ' '.join(parts) + ')'
    if len(flat) < 110 and '\n' not in flat:
        return flat
    out = '(' + parts[0]
    for p in parts[1:]:
        out += '\n' + '\t' * (ind + 1) + p
    return out + '\n' + '\t' * ind + ')'

def find(x, head):
    return [e for e in x if isinstance(e, list) and e and e[0] == head]

def fmt(v):
    v = round(v, 4)
    return ('%d' % v) if v == int(v) else ('%g' % v)

def q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'

def new_uuid():
    return str(uuid.uuid4())
