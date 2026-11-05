#!/usr/bin/env python3
"""Build sim/output.html: test results, BER graphs, circuit schematics and waveforms.

Usage: python tools/make_output.py   (run.sh does this)
"""
import base64
import html
import json
import os
import re
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(ROOT, "sim")
RTL = os.path.join(ROOT, "rtl")
DOCS = os.path.join(ROOT, "docs")
VCD = os.path.join(SIM, "tb_ofdm_top.vcd")
LOG = os.path.join(SIM, "sim_log.txt")

T = "tb_ofdm_top"
# (label, signal, kind)  kind: bit | bus | dec (signed decimal) | analog | state
SIGNALS = [
    ("clk", f"{T}.clk", "bit"),
    ("in_ready", f"{T}.in_ready", "bit"),
    ("in_valid", f"{T}.in_valid", "bit"),
    ("in_bits", f"{T}.in_bits", "bus"),
    ("QPSK I", f"{T}.dut.u_tx.map_i", "dec"),
    ("IFFT state", f"{T}.dut.u_tx.u_ifft.state", "state"),
    ("IFFT stage", f"{T}.dut.u_tx.u_ifft.stage", "bus"),
    ("tx_valid", f"{T}.tx_valid", "bit"),
    ("tx_re (I)", f"{T}.tx_re", "analog"),
    ("tx_im (Q)", f"{T}.tx_im", "analog"),
    ("FFT state", f"{T}.dut.u_rx.u_fft.state", "state"),
    ("FFT out re", f"{T}.dut.u_rx.fft_re", "analog"),
    ("out_valid", f"{T}.out_valid", "bit"),
    ("out_bits", f"{T}.out_bits", "bus"),
]
STATES = ["LOAD", "CALC", "OUT", "?"]
SCHEMATICS = [  # (module, title, hint, block_level)
    ("ofdm_top", "Top level: transmitter → AWGN channel → receiver", "", True),
    ("ofdm_tx", "Transmitter (ofdm_tx)", "QPSK mapper → IFFT → cyclic prefix insertion.", True),
    ("ofdm_rx", "Receiver (ofdm_rx)", "Cyclic prefix removal → FFT → QPSK demapper.", True),
    ("butterfly_r2", "Radix-2 butterfly (butterfly_r2), detailed logic",
     "Complex multiply by the twiddle, round, then add/subtract and divide by 2.", False),
    ("qpsk_mapper", "QPSK mapper, detailed logic", "", False),
    ("qpsk_demapper", "QPSK demapper, detailed logic", "", False),
    ("cp_remove", "Cyclic prefix removal, detailed logic", "", False),
]


# ---------------- waveform ----------------
def read_vcd(path):
    scope, ids, width, changes, t, unit = [], {}, {}, {}, 0, 1
    units = {"s": 10**15, "ms": 10**12, "us": 10**9, "ns": 10**6, "ps": 10**3, "fs": 1}
    in_ts = False
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if in_ts:
                m = re.match(r"(\d+)\s*(s|ms|us|ns|ps|fs)", s)
                if m:
                    unit = int(m.group(1)) * units[m.group(2)]
                in_ts = "$end" not in s
                continue
            if s.startswith("$timescale"):
                rest = s[len("$timescale"):].replace("$end", "").strip()
                m = re.match(r"(\d+)\s*(s|ms|us|ns|ps|fs)", rest)
                if m:
                    unit = int(m.group(1)) * units[m.group(2)]
                else:
                    in_ts = True
            elif s.startswith("$scope"):
                scope.append(s.split()[2])
            elif s.startswith("$upscope"):
                scope.pop()
            elif s.startswith("$var"):
                p = s.split()
                full = ".".join(scope + [p[4]])
                ids.setdefault(full, p[3])
                width[p[3]] = int(p[2])
                changes.setdefault(p[3], [])
            elif s[0] == "#":
                t = int(s[1:])
            elif s[0] in "01xzXZ" and s[1:] in changes:
                changes[s[1:]].append((t, s[0].lower()))
            elif s[0] in "bB":
                v, i = s[1:].split()
                if i in changes:
                    changes[i].append((t, v.lower()))
    return ids, width, changes, t, unit / 1e9  # microseconds per tick


def to_int(v, w, signed):
    if any(c in v for c in "xz"):
        return None
    n = int(v, 2)
    if signed and n >= 1 << (w - 1):
        n -= 1 << w
    return n


def wave_svg(vcd, t0, t1, tick_us, W=1150):
    ids, width, ch, _, us = vcd
    rows = [(lab, ids[n], kind) for lab, n, kind in SIGNALS if n in ids]
    L, R = 100, 12
    rh = {"analog": 56}
    H = sum(rh.get(k, 28) for *_, k in rows) + 34
    X = lambda t: L + (t - t0) / (t1 - t0) * (W - L - R)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" class="wave">']
    k = 0
    while k * tick_us <= (t1 - t0) * us + 1e-9:
        x = X(t0 + k * tick_us / us)
        o.append(f'<line x1="{x:.1f}" y1="4" x2="{x:.1f}" y2="{H-24}" class="grid"/>'
                 f'<text x="{x:.1f}" y="{H-8}" text-anchor="middle" class="tick">{t0*us + k*tick_us:g} µs</text>')
        k += 1
    y0 = 6
    for lab, i, kind in rows:
        h = rh.get(kind, 28)
        hi, lo = y0 + 3, y0 + h - 9
        mid = (hi + lo) / 2
        o.append(f'<text x="6" y="{mid+4}" class="name">{lab}</text>')
        lst, cur = ch[i], "x"
        for t, v in lst:
            if t <= t0:
                cur = v
            else:
                break
        segs, ct = [], t0
        for t, v in lst:
            if t <= t0:
                continue
            if t >= t1:
                break
            if v != cur:
                segs.append((ct, t, cur))
                ct, cur = t, v
        segs.append((ct, t1, cur))
        w = width[i]
        if kind == "bit":
            if lab == "clk" and len(segs) > (W - L) / 3:
                o.append(f'<rect x="{L}" y="{hi}" width="{W-L-R}" height="{lo-hi}" class="clkband"/>'
                         f'<text x="{(L+W)/2}" y="{mid+4}" text-anchor="middle" class="val">100 MHz clock (too fast to show at this zoom)</text>')
            else:
                d = ""
                for a, b, v in segs:
                    y = hi if v == "1" else lo if v == "0" else mid
                    d += f'{"M" if not d else "L"}{X(a):.1f},{y} L{X(b):.1f},{y} '
                o.append(f'<path d="{d}" class="bit"/>')
        elif kind == "analog":
            vals = [to_int(v, w, True) for *_, v in segs]
            big = max([abs(v) for v in vals if v is not None] + [1])
            o.append(f'<line x1="{L}" y1="{mid}" x2="{W-R}" y2="{mid}" class="zero"/>')
            d = ""
            for (a, b, _), v in zip(segs, vals):
                y = mid if v is None else mid - v / big * (lo - hi) / 2
                d += f'{"M" if not d else "L"}{X(a):.1f},{y:.1f} L{X(b):.1f},{y:.1f} '
            o.append(f'<path d="{d}" class="analog"/>')
        else:
            for a, b, v in segs:
                xa, xb = X(a), X(b)
                s = min(4, (xb - xa) / 2)
                o.append(f'<path d="M{xa:.1f},{mid} L{xa+s:.1f},{hi} L{xb-s:.1f},{hi} L{xb:.1f},{mid} '
                         f'L{xb-s:.1f},{lo} L{xa+s:.1f},{lo} Z" class="bus"/>')
                n = to_int(v, w, kind == "dec")
                if n is None:
                    txt = "x"
                elif kind == "state":
                    txt = STATES[min(n, 3)]
                else:
                    txt = str(n)
                if xb - xa > len(txt) * 7 + 6:
                    o.append(f'<text x="{(xa+xb)/2:.1f}" y="{mid+4}" text-anchor="middle" class="val">{txt}</text>')
        y0 += h
    o.append("</svg>")
    return "\n".join(o)


# ---------------- schematics ----------------
def schematics():
    if not (shutil.which("yosys") and shutil.which("netlistsvg")):
        return None
    out = {}
    src = " ".join(os.path.join(RTL, f) for f in sorted(os.listdir(RTL)) if f.endswith(".v"))
    for mod, *_, block in SCHEMATICS:
        js = os.path.join(SIM, f"schematic_{mod}.json")
        svg = os.path.join(SIM, f"schematic_{mod}.svg")
        if block:   # show sub-blocks as boxes, not their insides
            cmd = (f"read_verilog {src}; hierarchy -top {mod}; proc; opt -full; clean -purge; "
                   f"select -module {mod}; write_json -selected {js}")
        else:
            cmd = f"read_verilog {src}; hierarchy -top {mod}; proc; opt -full; clean -purge; write_json {js}"
        r = subprocess.run(["yosys", "-q", "-p", cmd], capture_output=True, text=True)
        if r.returncode:
            out[mod] = f'<p class="err">Yosys error: {html.escape(r.stderr.strip()[-400:])}</p>'
            continue
        d = json.load(open(js))
        for m in d["modules"].values():
            for c in m.get("cells", {}).values():
                c["type"] = re.sub(r"^\$paramod\\(\w+)\\.*$", r"\1", c["type"])
        json.dump(d, open(js, "w"))
        subprocess.run(["netlistsvg", js, "-o", svg], capture_output=True)
        out[mod] = open(svg).read() if os.path.exists(svg) else '<p class="err">netlistsvg failed</p>'
    r = subprocess.run(["yosys", "-q", "-p", f"read_verilog {src}; synth -top ofdm_top -flatten; "
                        f"tee -o {SIM}/synth_stat.txt stat"], capture_output=True, text=True)
    out["stat"] = open(f"{SIM}/synth_stat.txt").read() if os.path.exists(f"{SIM}/synth_stat.txt") else ""
    return out


def img(path, alt):
    if not os.path.exists(path):
        return f'<p class="err">{html.escape(os.path.relpath(path, ROOT))} not found.</p>'
    data = base64.b64encode(open(path, "rb").read()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{html.escape(alt)}">'


def ber_table():
    p = os.path.join(DOCS, "ber_summary.md")
    if not os.path.exists(p):
        return ""
    rows, notes = [], []
    for line in open(p).read().splitlines():
        if line.startswith("|") and not line.startswith("|---"):
            rows.append([c.strip() for c in line.strip("|").split("|")])
        elif line and not line.startswith("#") and not line.startswith("|"):
            notes.append(html.escape(line.lstrip("- ")))
    if not rows:
        return ""
    head = "".join(f"<th>{html.escape(c)}</th>" for c in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
    return f'<table><tr>{head}</tr>{body}</table><p class="hint">{" ".join(notes)}</p>'


# ---------------- page ----------------
def main():
    log = open(LOG, errors="replace").read() if os.path.exists(LOG) else "(no simulation log)"
    log_html = "\n".join(
        f'<span class="{"pass" if l.startswith("PASS") or "ALL TESTS PASSED" in l else "fail" if "FAIL" in l else ""}">'
        f"{html.escape(l)}</span>" for l in log.rstrip().splitlines())
    ok = "ALL TESTS PASSED" in log

    waves = ""
    if os.path.exists(VCD):
        vcd = read_vcd(VCD)
        ids, _, ch, tend, us = vcd
        starts = [t for t, v in ch.get(ids.get(f"{T}.in_valid"), []) if v == "1"]
        ends = [t for t, v in ch.get(ids.get(f"{T}.out_valid"), []) if v == "0"]
        if starts:
            a = starts[0]
            b = next((t for t in ends if t > a), tend)
            span = b - a
            waves += ('<h3>One OFDM symbol through the whole modem</h3><p class="hint">64 bit pairs go in → '
                      'QPSK → IFFT (LOAD 64, CALC 192 clocks, OUT 64) → 80 samples with cyclic prefix on tx → '
                      'FFT in the receiver → the same 64 bit pairs come out.</p>')
            waves += '<div class="box">' + wave_svg(vcd, max(0, a - span * 0.02), b + span * 0.03, 0.5) + "</div>"
        waves += ('<h3>Noise-free test, all 4 symbols</h3><div class="box">'
                  + wave_svg(vcd, 0, tend, 2) + "</div>")

    sch = schematics()
    if sch is None:
        circ = ('<p class="err">Install Yosys and netlistsvg to draw the circuit: '
                "<code>brew install yosys</code> and <code>npm install -g netlistsvg</code></p>")
    else:
        circ = ""
        for mod, title, hint, block in SCHEMATICS:
            cls = "box top" if block else "box zoom"
            circ += f"<h3>{html.escape(title)}</h3>"
            if hint:
                circ += f'<p class="hint">{html.escape(hint)}</p>'
            circ += f'<div class="{cls}">{sch[mod]}</div>'
        st = sch["stat"]
        cells = re.search(r"(\d+) cells", st)
        ffs = sum(int(n) for n in re.findall(r"(\d+)\s+\$_S?DFFE?_\w+", st))
        circ += (f"<h3>Size after synthesis (generic gates, Yosys)</h3><p>{cells.group(1) if cells else '?'} "
                 f"logic cells in total, of which {ffs} are flip-flops (most of them hold the 64 samples "
                 f"inside each FFT and the cyclic prefix buffer).</p>"
                 f"<details><summary>Full Yosys statistics</summary><pre>{html.escape(st)}</pre></details>")

    page = f'''<!doctype html><html><head><meta charset="utf-8"><title>OFDM Simulation Output</title>
<style>
body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:0;background:#f6f7f9;color:#1d1f23}}
header{{background:#1d2633;color:#fff;padding:18px 28px}} header h1{{margin:0;font-size:22px}}
header p{{margin:6px 0 0;color:#c9d1dc;font-size:14px}}
.badge{{display:inline-block;margin-left:12px;padding:3px 10px;border-radius:12px;font-size:14px;background:{'#1f9d55' if ok else '#c53030'}}}
nav{{padding:10px 28px;background:#fff;border-bottom:1px solid #dde1e6;position:sticky;top:0;z-index:2}}
nav a{{margin-right:18px;color:#2257a8;text-decoration:none;font-weight:600}}
main{{padding:8px 28px 40px;max-width:1300px}} h2{{margin-top:30px;border-bottom:2px solid #dde1e6;padding-bottom:6px}}
h3{{margin:22px 0 6px}} .hint{{color:#555;margin:2px 0 8px}} .err{{color:#c53030}}
pre.log{{background:#16191d;color:#ddd;padding:14px 16px;border-radius:6px;font-size:13px;overflow-x:auto}}
.pass{{color:#5ee28f}} .fail{{color:#ff7b7b}}
.box{{background:#fff;border:1px solid #d5d9df;border-radius:6px;padding:8px;overflow:auto}}
.box.zoom{{height:560px}} .box.zoom svg{{width:100%;height:auto}} .box.top svg{{max-width:100%;height:auto}} .box svg{{max-width:none}}
.imgs img{{max-width:100%;background:#fff;border:1px solid #d5d9df;border-radius:6px;margin:4px 0 14px}}
table{{border-collapse:collapse;background:#fff;font-size:14px;margin:6px 0}}
th,td{{border:1px solid #d5d9df;padding:5px 10px;text-align:right}} th{{background:#eef1f5}}
svg.wave{{width:100%;height:auto;font-family:Menlo,Consolas,monospace;font-size:11px}}
.grid{{stroke:#e3e6ea;stroke-dasharray:2 3}} .tick{{fill:#555}} .name{{font-weight:bold;fill:#222}}
.bit{{fill:none;stroke:#2267c9;stroke-width:1.5}} .analog{{fill:none;stroke:#13925b;stroke-width:1.2}}
.zero{{stroke:#c9ced6;stroke-width:1}} .bus{{fill:#edf3fd;stroke:#2267c9;stroke-width:1.1}}
.val{{fill:#222}} .clkband{{fill:#e9eef6}} .zbtn{{margin:0 4px 6px 0;padding:3px 10px;cursor:pointer}}
</style></head><body>
<header><h1>OFDM modem simulation output <span class="badge">{'ALL TESTS PASSED' if ok else 'CHECK RESULTS'}</span></h1>
<p>QPSK · 64-point FFT/IFFT · cyclic prefix 16 · Q1.15 fixed point · AWGN channel</p></header>
<nav><a href="#results">Test results</a><a href="#ber">BER graph</a><a href="#circuit">Circuit</a><a href="#graph">Waveform graph</a></nav>
<main>
<h2 id="results">Test results</h2><pre class="log">{log_html}</pre>
<h2 id="ber">BER graph</h2>
<div class="imgs">{img(os.path.join(DOCS, "ber_final.png"), "BER vs Eb/N0")}</div>
{ber_table()}
<h3>Received constellation (hardware FFT output)</h3>
<div class="imgs">{img(os.path.join(DOCS, "constellation.png"), "Received constellation")}</div>
<h3>Hardware noise generator</h3>
<div class="imgs">{img(os.path.join(DOCS, "noise_histogram.png"), "Noise histogram")}</div>
<h2 id="circuit">Circuit</h2>{circ}
<h2 id="graph">Waveform graph</h2>{waves or '<p class="err">No waveform file found.</p>'}
</main>
<script>
document.querySelectorAll('.box.zoom').forEach(b => {{
  let z = 100; const bar = document.createElement('div');
  for (const [t, d] of [['−', -50], ['+', 50], ['Fit', 0]]) {{
    const btn = document.createElement('button'); btn.textContent = t; btn.className = 'zbtn';
    btn.onclick = () => {{ z = d ? Math.max(50, z + d) : 100; b.querySelector('svg').style.width = z + '%'; }};
    bar.appendChild(btn);
  }}
  b.parentNode.insertBefore(bar, b);
}});
</script></body></html>'''
    open(os.path.join(SIM, "output.html"), "w").write(page)
    print("Output page: sim/output.html")


if __name__ == "__main__":
    main()
