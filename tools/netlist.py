from sexp import parse, find
def load(path):
    r = parse(open(path).read())[0]
    comps = {}
    for c in find(find(r, 'components')[0], 'comp'):
        g = lambda k: find(c, k)[0][1].strip('"') if find(c, k) else ''
        sp = find(c, 'sheetpath')[0]
        comps[g('ref')] = dict(value=g('value'), fp=g('footprint'), tstamp=g('tstamps'),
                               sheet=find(sp, 'tstamps')[0][1].strip('"'),
                               dnp=any(p for p in find(c, 'property') if find(p, 'name')[0][1].strip('"') == 'dnp'))
    nets = {}
    for n in find(r, 'nets')[0][1:]:
        name = find(n, 'name')[0][1].strip('"')
        for nd in find(n, 'node'):
            nets.setdefault(name, []).append((find(nd, 'ref')[0][1].strip('"'), find(nd, 'pin')[0][1].strip('"')))
    return comps, nets
