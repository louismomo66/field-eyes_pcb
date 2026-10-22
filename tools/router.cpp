// Grid router for the two-layer Field Eyes board (negotiated congestion, PathFinder style).
// build: clang++ -O2 -std=c++17 -o router router.cpp      run: ./router board.txt result.txt [seconds]
// Reads the file written by export_route.py; writes SEG / VIA lines for every net it could route without any clearance conflict.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <fstream>
#include <map>
#include <numeric>
#include <queue>
#include <sstream>
#include <string>
#include <unordered_set>
#include <vector>
using namespace std;
typedef vector<pair<double,double>> Poly;

static const double RES = 0.1, CLR = 0.2, HOLE_CLR = 0.25, EDGE_CLR = 0.5, MARGIN = 0.07, VIA_D = 0.6;
// track width classes (0..4) and the via pseudo-class (5)
static const double CW[6] = {0.2, 0.25, 0.35, 0.5, 0.8, VIA_D};
static const int NCLS = 6, VIA = 5;
static double HW(int k) { return CW[k] / 2; }

int NX, NY, N;
struct Obj { int type; int layer; int net; Poly poly; double x, y, r, w, x2, y2; };   // type 0 poly, 1 seg, 2 via, 3 keepout poly, 4 hole
vector<Obj> objs;
Poly outline;
double BW, BH;

static double dseg(double px, double py, double ax, double ay, double bx, double by) {
    double dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy, t = l2 > 0 ? ((px - ax) * dx + (py - ay) * dy) / l2 : 0;
    t = max(0.0, min(1.0, t));
    return hypot(px - (ax + t * dx), py - (ay + t * dy));
}
static bool inside(const Poly& P, double x, double y) {
    bool in = false;
    for (size_t i = 0, j = P.size() - 1; i < P.size(); j = i++)
        if ((P[i].second > y) != (P[j].second > y) && x < (P[j].first - P[i].first) * (y - P[i].second) / (P[j].second - P[i].second) + P[i].first) in = !in;
    return in;
}
static double dedge(const Poly& P, double x, double y) {       // distance to the boundary
    double d = 1e9;
    for (size_t i = 0, j = P.size() - 1; i < P.size(); j = i++) d = min(d, dseg(x, y, P[j].first, P[j].second, P[i].first, P[i].second));
    return d;
}
static double dpoly(const Poly& P, double x, double y) {       // 0 when inside
    if (inside(P, x, y)) return 0;
    return dedge(P, x, y);
}

// ---- static obstacles: stat[k][l][cell] = 0 free, net id (only that net may pass), -1 blocked
vector<int16_t> stat_[NCLS][2];
vector<uint8_t> noVia;
// ---- dynamic copper of routed nets
vector<int16_t> ownA[NCLS][2];
vector<uint16_t> cntA[NCLS][2], cntO[NCLS][2];
vector<float> hist_;
vector<pair<int,int>> disc[NCLS][NCLS];     // offsets for an item of class a stamping into class k

static void markStatic(int k, int l, int c, int net) {
    int16_t& s = stat_[k][l][c];
    if (net <= 0) s = -1;
    else if (s == 0) s = net;
    else if (s != net) s = -1;
}
static void stampStatic() {
    for (int k = 0; k < NCLS; k++) for (int l = 0; l < 2; l++) stat_[k][l].assign(N, 0);
    noVia.assign(N, 0);
    for (auto& o : objs) {
        double x0, y0, x1, y1;
        if (o.type == 0 || o.type == 3) {
            x0 = y0 = 1e9; x1 = y1 = -1e9;
            for (auto& p : o.poly) { x0 = min(x0, p.first); x1 = max(x1, p.first); y0 = min(y0, p.second); y1 = max(y1, p.second); }
        } else if (o.type == 1) { x0 = min(o.x, o.x2) - o.w / 2; x1 = max(o.x, o.x2) + o.w / 2; y0 = min(o.y, o.y2) - o.w / 2; y1 = max(o.y, o.y2) + o.w / 2; }
        else { x0 = o.x - o.r; x1 = o.x + o.r; y0 = o.y - o.r; y1 = o.y + o.r; }
        for (int k = 0; k < NCLS; k++) {
            double clr = (o.type == 4) ? HOLE_CLR : (o.type == 3 ? 0.0 : CLR);
            double r = clr + HW(k) + MARGIN;
            int i0 = max(0, (int)floor((x0 - r) / RES)), i1 = min(NX - 1, (int)ceil((x1 + r) / RES));
            int j0 = max(0, (int)floor((y0 - r) / RES)), j1 = min(NY - 1, (int)ceil((y1 + r) / RES));
            for (int j = j0; j <= j1; j++) for (int i = i0; i <= i1; i++) {
                double x = i * RES, y = j * RES, d;
                if (o.type == 0 || o.type == 3) d = dpoly(o.poly, x, y);
                else if (o.type == 1) d = dseg(x, y, o.x, o.y, o.x2, o.y2) - o.w / 2;
                else d = hypot(x - o.x, y - o.y) - o.r;
                if (d < r) {
                    int c = j * NX + i;
                    if (o.type == 3) markStatic(k, o.layer, c, -1);
                    else if (o.type == 4) { markStatic(k, 0, c, -1); markStatic(k, 1, c, -1); }
                    else if (o.type == 2) { markStatic(k, 0, c, o.net); markStatic(k, 1, c, o.net); }   // a via is copper on both layers
                    else markStatic(k, o.layer, c, o.net);
                }
            }
        }
        if (o.type == 0) {                 // vias keep a via radius away from every pad
            double r = 0.45;
            int i0 = max(0, (int)floor((x0 - r) / RES)), i1 = min(NX - 1, (int)ceil((x1 + r) / RES)), j0 = max(0, (int)floor((y0 - r) / RES)), j1 = min(NY - 1, (int)ceil((y1 + r) / RES));
            for (int j = j0; j <= j1; j++) for (int i = i0; i <= i1; i++) if (dpoly(o.poly, i * RES, j * RES) < r) noVia[j * NX + i] = 1;
        }
    }
    // board edge: copper stays EDGE_CLR (+ half its width) inside the outline
    for (int j = 0; j < NY; j++) for (int i = 0; i < NX; i++) {
        double x = i * RES, y = j * RES;
        double band = min(min(x, BW - x), min(y, BH - y));
        bool far = band > 6.0;
        bool in = far ? true : inside(outline, x, y);
        double d = far ? 1e9 : dedge(outline, x, y);
        for (int k = 0; k < NCLS; k++) {
            double r = EDGE_CLR + HW(k) + MARGIN;
            if (!in || d < r) for (int l = 0; l < 2; l++) stat_[k][l][j * NX + i] = -1;
        }
    }
}
static void buildDiscs() {
    for (int a = 0; a < NCLS; a++) for (int k = 0; k < NCLS; k++) {
        double r = HW(a) + CLR + HW(k) + MARGIN; int R = (int)ceil(r / RES);
        for (int dj = -R; dj <= R; dj++) for (int di = -R; di <= R; di++) if (hypot(di * RES, dj * RES) < r) disc[a][k].push_back({di, dj});
    }
}
static void stampDyn(int a, int net, int l, int i, int j, int sgn) {
    for (int k = 0; k < NCLS; k++) for (auto& o : disc[a][k]) {
        int x = i + o.first, y = j + o.second;
        if (x < 0 || y < 0 || x >= NX || y >= NY) continue;
        int c = y * NX + x;
        if (sgn > 0) {
            if (ownA[k][l][c] == 0 || cntA[k][l][c] == 0) { ownA[k][l][c] = net; cntA[k][l][c] = 1; }
            else if (ownA[k][l][c] == net) cntA[k][l][c]++;
            else cntO[k][l][c]++;
        } else {
            if (ownA[k][l][c] == net && cntA[k][l][c] > 0) cntA[k][l][c]--;
            else if (cntO[k][l][c] > 0) cntO[k][l][c]--;
        }
    }
}
static inline bool foreignDyn(int k, int l, int c, int net) {
    return (cntA[k][l][c] > 0 && ownA[k][l][c] != net) || cntO[k][l][c] > 0;
}

// ---- nets
struct Term { int mask; double x, y; int i, j; };
struct Net {
    int id; string name; double pw; vector<Term> terms; int cls;
    vector<vector<array<int,3>>> paths; vector<array<int,2>> vias; bool ok = false; int tries = 0; bool any = false, fan = false;   // any: join terminal 0 to whichever other terminal is cheapest to reach
};
vector<Net> nets;

static double presFac = 1.0;
struct QN { float f; int n; bool operator<(const QN& o) const { return f > o.f; } };
vector<float> G; vector<int> par; vector<uint32_t> gen_; uint32_t curGen = 0;

static bool routeOne(Net& net, const vector<int>& srcNodes, const vector<int>& goalNodes, vector<int>& pathOut, int margin) {
    int cls = net.cls;
    int gi = goalNodes[0] % N % NX, gj = goalNodes[0] % N / NX;
    int bi0 = NX, bi1 = 0, bj0 = NY, bj1 = 0;
    for (int n : srcNodes) { int c = n % N; bi0 = min(bi0, c % NX); bi1 = max(bi1, c % NX); bj0 = min(bj0, c / NX); bj1 = max(bj1, c / NX); }
    bi0 = min(bi0, gi); bi1 = max(bi1, gi); bj0 = min(bj0, gj); bj1 = max(bj1, gj);
    bi0 = max(0, bi0 - margin); bi1 = min(NX - 1, bi1 + margin); bj0 = max(0, bj0 - margin); bj1 = min(NY - 1, bj1 + margin);
    curGen++;
    priority_queue<QN> pq;
    bool anyMode = goalNodes.size() > 2 || net.any || net.fan;
    auto H = [&](int c) { if (anyMode) return 0.0f; int dx = abs(c % NX - gi), dy = abs(c / NX - gj); return (float)(RES * (max(dx, dy) + 0.4142 * min(dx, dy))); };
    for (int n : srcNodes) { G[n] = 0; par[n] = -1; gen_[n] = curGen; pq.push({H(n % N), n}); }
    unordered_set<int> goals(goalNodes.begin(), goalNodes.end());
    static const int DX[8] = {1,-1,0,0,1,1,-1,-1}, DY[8] = {0,0,1,-1,1,-1,1,-1};
    while (!pq.empty()) {
        QN q = pq.top(); pq.pop();
        int n = q.n, l = n / N, c = n % N;
        if (q.f > G[n] + H(c) + 1e-4) continue;
        bool fanGoal = false;
        if (net.fan && gen_[n] == curGen && G[n] > 0.25 && !noVia[c]) {
            int16_t s0 = stat_[VIA][0][c], s1 = stat_[VIA][1][c];
            bool near = false;
            for (auto& nt : nets) for (auto& v : nt.vias) if (hypot(v[0] - c % NX, v[1] - c / NX) < 7.5) near = true;
            for (auto& o : objs) if (o.type == 2 && hypot(o.x / RES - c % NX, o.y / RES - c / NX) < 7.5) near = true;
            fanGoal = !near && (s0 == 0 || s0 == net.id) && (s1 == 0 || s1 == net.id) && !foreignDyn(VIA, 0, c, net.id) && !foreignDyn(VIA, 1, c, net.id);
        }
        if (fanGoal) {      // a fan-out ends in a via: take the cheapest cell where one fits
            pathOut.clear();
            for (int m = n; m != -1; m = par[m]) pathOut.push_back(m);
            reverse(pathOut.begin(), pathOut.end());
            pathOut.push_back((1 - l) * N + c);
            return true;
        }
        if (!net.fan && goals.count(n)) {
            pathOut.clear();
            for (int m = n; m != -1; m = par[m]) pathOut.push_back(m);
            reverse(pathOut.begin(), pathOut.end());
            return true;
        }
        int i = c % NX, j = c / NX;
        for (int d = 0; d < 8; d++) {
            int x = i + DX[d], y = j + DY[d];
            if (x < bi0 || x > bi1 || y < bj0 || y > bj1) continue;
            int cc = y * NX + x, nn = l * N + cc;
            int16_t s = stat_[cls][l][cc];
            if (s == -1 || (s > 0 && s != net.id)) continue;
            double step = RES * (d < 4 ? 1.0 : 1.4142);
            bool horiz = d < 2;
            if (d < 4) step *= ((l == 0) == horiz) ? 1.0 : 1.45; else step *= 1.2;
            if (foreignDyn(cls, l, cc, net.id)) step += presFac;
            step += hist_[l * N + cc];
            float g = G[n] + (float)step;
            if (gen_[nn] != curGen || g < G[nn]) { gen_[nn] = curGen; G[nn] = g; par[nn] = n; pq.push({g + H(cc), nn}); }
        }
        int l2 = 1 - l, nn = l2 * N + c;
        if (!noVia[c]) {
            int16_t s0 = stat_[VIA][0][c], s1 = stat_[VIA][1][c];
            if ((s0 == 0 || s0 == net.id) && (s1 == 0 || s1 == net.id)) {
                double step = 3.0 + (foreignDyn(VIA, 0, c, net.id) ? presFac : 0) + (foreignDyn(VIA, 1, c, net.id) ? presFac : 0) + hist_[c] + hist_[N + c];
                float g = G[n] + (float)step;
                if (gen_[nn] != curGen || g < G[nn]) { gen_[nn] = curGen; G[nn] = g; par[nn] = n; pq.push({g + H(c), nn}); }
            }
        }
    }
    return false;
}

static void ripUp(Net& net) {
    for (auto& p : net.paths) for (auto& cl : p) stampDyn(net.cls, net.id, cl[0], cl[1], cl[2], -1);
    for (auto& v : net.vias) { stampDyn(VIA, net.id, 0, v[0], v[1], -1); stampDyn(VIA, net.id, 1, v[0], v[1], -1); }
    net.paths.clear(); net.vias.clear(); net.ok = false;
}
static void commit(Net& net, const vector<int>& path) {
    vector<array<int,3>> cells;
    for (size_t p = 0; p < path.size(); p++) {
        int l = path[p] / N, c = path[p] % N, i = c % NX, j = c / NX;
        if (p > 0 && path[p - 1] % N == c && path[p - 1] / N != l) {
            net.vias.push_back({i, j});
            stampDyn(VIA, net.id, 0, i, j, +1); stampDyn(VIA, net.id, 1, i, j, +1);
        }
        cells.push_back({l, i, j});
        stampDyn(net.cls, net.id, l, i, j, +1);
    }
    net.paths.push_back(cells);
}
// connect all terminals of a net: the unconnected terminal nearest to the growing tree each time
static bool routeNet(Net& net, int margin0) {
    ripUp(net);
    int T = net.terms.size();
    vector<char> done(T, 0);
    vector<int> tree;
    auto addTerm = [&](int t) {
        done[t] = 1;
        for (int l = 0; l < 2; l++) if (net.terms[t].mask >> l & 1) tree.push_back(l * N + net.terms[t].j * NX + net.terms[t].i);
    };
    addTerm(0);
    if (net.fan) {
        vector<int> path; bool ok = false;
        for (int margin : {60, 150}) { ok = routeOne(net, tree, tree, path, margin); if (ok) break; }
        if (!ok) return false;
        commit(net, path);
        return true;
    }
    if (net.any) {
        vector<int> goal;
        for (int t = 1; t < T; t++) for (int l = 0; l < 2; l++) if (net.terms[t].mask >> l & 1) goal.push_back(l * N + net.terms[t].j * NX + net.terms[t].i);
        vector<int> path; bool ok = false;
        for (int margin : {margin0, 400, 100000}) { ok = routeOne(net, tree, goal, path, margin); if (ok) break; }
        if (!ok) return false;
        commit(net, path);
        return true;
    }
    for (int step = 1; step < T; step++) {
        int best = -1; double bd = 1e18;
        for (int t = 0; t < T; t++) if (!done[t]) {
            for (int n : tree) { int c = n % N; double d = hypot(c % NX - net.terms[t].i, c / NX - net.terms[t].j); if (d < bd) { bd = d; best = t; } }
        }
        vector<int> goal;
        for (int l = 0; l < 2; l++) if (net.terms[best].mask >> l & 1) goal.push_back(l * N + net.terms[best].j * NX + net.terms[best].i);
        vector<int> path; bool ok = false;
        for (int margin : {margin0, 400, 100000}) {
            ok = routeOne(net, tree, goal, path, margin);
            if (ok) break;
        }
        if (!ok) return false;
        commit(net, path);
        for (int n : path) tree.push_back(n);
        addTerm(best);
    }
    return true;
}
static int countConflicts(Net& net, vector<array<int,3>>* bad = nullptr) {
    int n = 0;
    for (auto& p : net.paths) for (auto& cl : p) if (foreignDyn(net.cls, cl[0], cl[2] * NX + cl[1], net.id)) { n++; if (bad) bad->push_back(cl); }
    for (auto& v : net.vias) {
        int c = v[1] * NX + v[0];
        if (foreignDyn(VIA, 0, c, net.id) || foreignDyn(VIA, 1, c, net.id)) n++;
    }
    return n;
}

int main(int argc, char** argv) {
    ifstream in(argv[1]); double limit = argc > 3 ? atof(argv[3]) : 300;
    string line; map<int, pair<string,double>> netInfo; vector<Net> routes;
    while (getline(in, line)) {
        istringstream s(line); string tag; s >> tag;
        if (tag == "GRID") { s >> BW >> BH; NX = (int)ceil(BW / RES) + 1; NY = (int)ceil(BH / RES) + 1; N = NX * NY; }
        else if (tag == "OUTLINE") { int n; s >> n; for (int i = 0; i < n; i++) { double x, y; s >> x >> y; outline.push_back({x, y}); } }
        else if (tag == "NET") { int id; double w; string nm; s >> id >> w >> nm; netInfo[id] = {nm, w}; }
        else if (tag == "POLY" || tag == "KEEP") {
            Obj o; o.type = tag == "POLY" ? 0 : 3; int n;
            if (tag == "POLY") s >> o.layer >> o.net >> n; else { o.net = 0; s >> o.layer >> n; }
            for (int i = 0; i < n; i++) { double x, y; s >> x >> y; o.poly.push_back({x, y}); }
            objs.push_back(o);
        } else if (tag == "SEG") { Obj o; o.type = 1; s >> o.layer >> o.net >> o.w >> o.x >> o.y >> o.x2 >> o.y2; objs.push_back(o); }
        else if (tag == "VIA") { Obj o; o.type = 2; double d; s >> o.net >> o.x >> o.y >> d; o.r = d / 2; o.layer = 0; objs.push_back(o); }
        else if (tag == "HOLE") { Obj o; o.type = 4; o.net = 0; s >> o.x >> o.y >> o.r; o.layer = 0; objs.push_back(o); }
        else if (tag == "ROUTE" || tag == "ROUTEANY" || tag == "ROUTEFAN") {
            Net nt; nt.any = tag == "ROUTEANY"; nt.fan = tag == "ROUTEFAN"; int n; s >> nt.id >> n; nt.name = netInfo[nt.id].first; nt.pw = netInfo[nt.id].second;
            for (int i = 0; i < n; i++) { Term t; s >> t.mask >> t.x >> t.y; t.i = (int)lround(t.x / RES); t.j = (int)lround(t.y / RES); nt.terms.push_back(t); }
            routes.push_back(nt);
        }
    }
    fprintf(stderr, "grid %dx%d, %zu objects, %zu nets\n", NX, NY, objs.size(), routes.size());
    buildDiscs(); stampStatic();
    for (int k = 0; k < NCLS; k++) for (int l = 0; l < 2; l++) { ownA[k][l].assign(N, 0); cntA[k][l].assign(N, 0); cntO[k][l].assign(N, 0); }
    hist_.assign(2 * N, 0); G.assign(2 * N, 0); par.assign(2 * N, -1); gen_.assign(2 * N, 0);
    nets = routes;
    for (auto& n : nets) n.cls = n.pw >= 0.7 ? 4 : n.pw >= 0.45 ? 3 : n.pw >= 0.3 ? 2 : 1;
    vector<int> order(nets.size()); iota(order.begin(), order.end(), 0);      // wide nets first, then short nets
    auto span = [&](Net& n) { double x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9; for (auto& t : n.terms) { x0 = min(x0, t.x); x1 = max(x1, t.x); y0 = min(y0, t.y); y1 = max(y1, t.y); } return (x1 - x0) + (y1 - y0); };
    sort(order.begin(), order.end(), [&](int a, int b) { if (nets[a].cls != nets[b].cls) return nets[a].cls > nets[b].cls; return span(nets[a]) < span(nets[b]); });
    auto t0 = chrono::steady_clock::now();
    auto elapsed = [&]() { return chrono::duration<double>(chrono::steady_clock::now() - t0).count(); };
    vector<char> need(nets.size(), 1);
    for (int it = 0; it < 300 && elapsed() < limit; it++) {
        presFac = min(1000.0, 1.0 * pow(1.5, it));
        int rerouted = 0;
        for (int idx : order) {
            if (!need[idx]) continue;
            Net& n = nets[idx];
            bool ok = routeNet(n, 100);
            rerouted++;
            if (!ok) {
                ripUp(n);
                if (n.cls > 0 && ++n.tries >= 2) { n.cls--; n.tries = 0; fprintf(stderr, "  %s: no path, trying width %.2f\n", n.name.c_str(), CW[n.cls]); }
            }
            n.ok = ok;
        }
        int bad = 0, nfail = 0;
        for (size_t idx = 0; idx < nets.size(); idx++) {
            Net& n = nets[idx];
            if (!n.ok) { need[idx] = 1; nfail++; continue; }
            vector<array<int,3>> cells; int cnum = countConflicts(n, &cells);
            if (cnum) {
                bad++; need[idx] = 1;
                for (auto& cl : cells) hist_[cl[0] * N + cl[2] * NX + cl[1]] += 1.0f;
            } else need[idx] = 0;
        }
        fprintf(stderr, "iteration %2d  %5.1fs  rerouted %3d  nets in conflict %3d  no path %3d\n", it, elapsed(), rerouted, bad, nfail);
        if (bad + nfail == 0) break;
    }
    for (;;) {      // nets still in conflict are dropped (worst first) so that everything written is clean
        int worst = -1, wc = 0;
        for (size_t idx = 0; idx < nets.size(); idx++) if (nets[idx].ok) {      // ground links give way before signal nets do
            int c = countConflicts(nets[idx]) * (nets[idx].name == "GND" ? 1000 : 1);
            if (c > wc) { wc = c; worst = idx; }
        }
        if (wc >= 1000) wc /= 1000;
        if (worst < 0) break;
        fprintf(stderr, "  dropping %s (%d conflicts)\n", nets[worst].name.c_str(), wc);
        ripUp(nets[worst]);
    }
    ofstream out(argv[2]); int okN = 0;
    for (auto& n : nets) {
        if (!n.ok) {
            out << "FAIL " << n.name << " " << n.terms[0].x << " " << n.terms[0].y << "\n";
            int c = n.terms[0].j * NX + n.terms[0].i;
            fprintf(stderr, "  FAIL %s at %.2f,%.2f  cell state F:%d B:%d (class %d)\n", n.name.c_str(), n.terms[0].x, n.terms[0].y, stat_[n.cls][0][c], stat_[n.cls][1][c], n.cls);
            continue;
        }
        okN++;
        for (auto& path : n.paths) {                  // straight runs of cells become one segment each
            size_t start = 0; int pdx = 0, pdy = 0; bool have = false;
            auto flush = [&](size_t a, size_t b) {
                if (b > a) out << "SEG " << n.name << " " << path[a][0] << " " << CW[n.cls] << " " << path[a][1] * RES << " " << path[a][2] * RES << " " << path[b][1] * RES << " " << path[b][2] * RES << "\n";
            };
            for (size_t q = 1; q < path.size(); q++) {
                if (path[q][0] != path[q - 1][0]) { flush(start, q - 1); start = q; have = false; continue; }
                int dx = path[q][1] - path[q - 1][1], dy = path[q][2] - path[q - 1][2];
                if (have && (dx != pdx || dy != pdy)) { flush(start, q - 1); start = q - 1; }
                pdx = dx; pdy = dy; have = true;
            }
            flush(start, path.size() - 1);
        }
        for (auto& v : n.vias) out << "VIA " << n.name << " " << v[0] * RES << " " << v[1] * RES << "\n";
        for (auto& t : n.terms)                       // short stub from the exact pad centre to the grid cell the path starts from
            for (int l = 0; l < 2; l++) if (t.mask >> l & 1) {
                bool used = false;
                for (auto& p : n.paths) for (auto& cl : p) if (cl[0] == l && cl[1] == t.i && cl[2] == t.j) used = true;
                if (used && hypot(t.x - t.i * RES, t.y - t.j * RES) > 0.002)
                    out << "SEG " << n.name << " " << l << " " << CW[n.cls] << " " << t.x << " " << t.y << " " << t.i * RES << " " << t.j * RES << "\n";
            }
        out << "OK " << n.name << " " << CW[n.cls] << "\n";
    }
    fprintf(stderr, "routed %d of %zu nets in %.1fs\n", okN, nets.size(), elapsed());
}
