#!/usr/bin/env python3
"""Build a local HTML page to listen to ODAQ pairs next to the model's description.

Run: python eval/odaq/listen_page.py PREDICTIONS.jsonl [--out DIR]
Then serve it:  python eval/odaq/listen_page.py --serve DIR [--port 8765]
and open http://localhost:8765 (forward the port if working over SSH).

Uses PREDICTIONS_clap.csv (from clap_score.py) when it exists next to the JSONL.
Audio is copied into DIR/audio as browser-friendly 16-bit PCM WAV.
"""

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import METHOD_PATTERNS, actual_condition, predicted_severity  # noqa: E402
import re  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ODAQ Listening</title>
<style>
:root {{ --bg:#fafaf8; --card:#fff; --fg:#1c1c1c; --muted:#6b6b6b; --line:#e4e2dc;
  --accent:#2f5d8a; --ok:#2e7d4f; --bad:#b0442c; --chip:#efede7; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161616; --card:#1f1f1f; --fg:#e8e8e8;
  --muted:#9a9a9a; --line:#333; --accent:#7fb0e0; --ok:#6cc08f; --bad:#e58a72; --chip:#2b2b2b; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
header {{ position:sticky; top:0; z-index:2; background:var(--bg); border-bottom:1px solid var(--line);
  padding:12px 16px; display:flex; flex-wrap:wrap; gap:8px 16px; align-items:center; }}
h1 {{ font-size:17px; margin:0 12px 0 0; }}
header label {{ color:var(--muted); font-size:13px; }}
select, input {{ font:inherit; padding:4px 8px; border:1px solid var(--line); border-radius:6px;
  background:var(--card); color:var(--fg); }}
#count {{ color:var(--muted); font-size:13px; margin-left:auto; }}
main {{ max-width:980px; margin:0 auto; padding:16px; display:grid; gap:12px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.top {{ display:flex; flex-wrap:wrap; gap:6px 10px; align-items:baseline; margin-bottom:8px; }}
.clip {{ font-weight:600; }}
.cond {{ font-family:ui-monospace, monospace; font-size:13px; }}
.chip {{ font-size:12px; background:var(--chip); border-radius:999px; padding:1px 8px; }}
.hit {{ color:var(--ok); }} .miss {{ color:var(--bad); }}
.players {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:6px 0 10px; }}
.players div {{ font-size:12px; color:var(--muted); }}
audio {{ width:100%; height:36px; }}
.resp {{ margin:0; }}
.meta {{ margin-top:8px; font-size:12px; color:var(--muted); display:flex; flex-wrap:wrap; gap:4px 14px; }}
@media (max-width:640px) {{ .players {{ grid-template-columns:1fr; }} }}
</style></head><body>
<header>
  <h1>{title}</h1>
  <label>Method <select id="m"><option value="">all</option>{method_opts}</select></label>
  <label>Detected <select id="d"><option value="">any</option>
    <option value="hit">correct method matched</option><option value="miss">not matched</option></select></label>
  <label>Severity <select id="v"><option value="">all</option>
    <option value="high">high (level 1, LP35, LP70)</option><option value="mid">medium (levels 2–3)</option>
    <option value="low">low (levels 4–5)</option><option value="none">identical pairs</option></select></label>
  <label>Search <input id="q" placeholder="text in response"></label>
  <label>Sort <select id="s"><option value="">file order</option>
    <option value="delta">CLAP Δ (deg − ref), low first</option>
    <option value="sim">reference↔degraded, low first</option>
    <option value="mushra">listener MUSHRA, worst first</option></select></label>
  <span id="count"></span>
</header>
<main id="list">{cards}</main>
<script>
const cards=[...document.querySelectorAll('.card')], m=document.getElementById('m'),
  d=document.getElementById('d'), v=document.getElementById('v'), q=document.getElementById('q'), c=document.getElementById('count'),
  so=document.getElementById('s'), list=document.getElementById('list');
// Cards without CLAP scores sort last.
function sortCards(){{ const k=so.value, v=el=>k&&el.dataset[k]!==''?+el.dataset[k]:Infinity;
  const order=k?[...cards].sort((a,b)=>v(a)-v(b)):cards; for (const el of order) list.appendChild(el); }}
so.addEventListener('input',sortCards);
function f(){{ let n=0; const s=q.value.toLowerCase();
  for (const el of cards) {{ const ok=(!m.value||el.dataset.m===m.value)&&(!d.value||el.dataset.d===d.value)
      &&(!v.value||el.dataset.v===v.value)&&(!s||el.dataset.t.includes(s)); el.hidden=!ok; n+=ok; }}
  c.textContent=n+' / '+cards.length+' pairs'; }}
[m,d,v,q].forEach(e=>e.addEventListener('input',f)); f();
// Only one clip plays at a time.
document.addEventListener('play',e=>{{ for (const a of document.querySelectorAll('audio')) if(a!==e.target) a.pause(); }},true);
</script></body></html>
"""


def read_csv(path):
    return {(r["reference path"], r["degraded path"]): r for r in csv.DictReader(path.open())} if path.exists() else {}


def serve(directory, port):
    """Static server with HTTP Range support (Safari will not play audio without it)."""
    import functools
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    class Handler(SimpleHTTPRequestHandler):
        def send_head(self):
            rng = self.headers.get("Range")
            path = Path(self.translate_path(self.path))
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng or "")
            if not m or not path.is_file():
                return super().send_head()
            size = path.stat().st_size
            start = int(m[1]) if m[1] else max(size - int(m[2] or 0), 0)
            end = min(int(m[2]), size - 1) if m[1] and m[2] else size - 1
            if start >= size or start > end:
                self.send_error(416)
                return None
            f = path.open("rb")
            f.seek(start)
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(str(path)))
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self._remaining = end - start + 1
            return f

        def copyfile(self, source, outputfile):
            n = getattr(self, "_remaining", None)
            if n is None:
                return super().copyfile(source, outputfile)
            while n > 0 and (chunk := source.read(min(n, 1 << 16))):
                outputfile.write(chunk)
                n -= len(chunk)

        def end_headers(self):
            if not self.headers.get("Range"):
                self.send_header("Accept-Ranges", "bytes")
            super().end_headers()

    httpd = ThreadingHTTPServer(("127.0.0.1", port),
                                functools.partial(Handler, directory=str(directory)))
    print(f"Serving {directory} at http://localhost:{port}", flush=True)
    httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("predictions", type=Path, help="Predictions JSONL, or the page DIR with --serve")
    ap.add_argument("--out", type=Path, help="Defaults to PREDICTIONS_listen/")
    ap.add_argument("--serve", action="store_true", help="Serve an existing page directory")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    if args.serve:
        return serve(args.predictions, args.port)
    out = args.out or args.predictions.with_name(args.predictions.stem + "_listen")
    out.mkdir(parents=True, exist_ok=True)

    records = [json.loads(l) for l in args.predictions.open() if l.strip()]
    clap = read_csv(args.predictions.with_name(args.predictions.stem + "_clap.csv"))
    # Mean listener score per (item, condition), from compare_mushra.py output if present.
    mushra_csv = args.predictions.with_name(args.predictions.stem + "_mushra.csv")
    mushra = ({(r["item"], r["process"]): r["mushra"] for r in csv.DictReader(mushra_csv.open())}
              if mushra_csv.exists() else {})
    root = Path(os.path.commonpath([a for r in records for a in r["audios"]]))
    if root.suffix:  # single file; use its parent
        root = root.parent
    # ODAQ files are 24-bit WAVE_FORMAT_EXTENSIBLE with channel mask 0, which many
    # browsers play as silence. Write plain 16-bit PCM copies (TPDF-dithered).
    link = out / "audio"
    if link.is_symlink():
        link.unlink()
    rng = np.random.default_rng(0)
    for src in sorted({a for r in records for a in r["audios"]}):
        dst = link / Path(src).relative_to(root)
        if dst.exists() and dst.stat().st_mtime >= Path(src).stat().st_mtime:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        x, sr = sf.read(src, dtype="float64", always_2d=True)
        lsb = 1 / 32768
        x = x + (rng.random(x.shape) - rng.random(x.shape)) * lsb
        sf.write(dst, np.clip(x, -1, 1 - lsb), sr, subtype="PCM_16", format="WAV")

    cards, methods = [], []
    for r in records:
        ref, deg = r["audios"]
        resp = r["response"]
        method, sev = actual_condition(Path(ref), Path(deg))
        methods.append(method)
        found = [k for k, p in METHOD_PATTERNS.items() if re.search(p, resp, re.I)]
        if method in METHOD_PATTERNS:
            hit = "hit" if method in found else "miss"
        else:  # reference control: "hit" means no processing was named
            hit = "hit" if not found else "miss"
        cond = "identical pair" if method == "reference" else Path(deg).stem
        rel = lambda p: "audio/" + "/".join(html.escape(x) for x in Path(p).relative_to(root).parts)
        c = clap.get((ref, deg), {})
        meta = [f"actual severity: {sev}", f"predicted severity: {predicted_severity(resp) or '–'}"]
        band = ("none" if method == "reference" else "high" if sev != "" and sev <= 1.5
                else "mid" if sev != "" and sev <= 3 else "low")
        score = mushra.get((Path(ref).parent.name, "reference" if ref == deg else Path(deg).stem), "")
        if score:
            score = f"{float(score):.1f}"
            meta.append(f"listener MUSHRA {score}")
        delta = sim = ""
        if c:
            delta = f"{float(c['clap_text_degraded']) - float(c['clap_text_reference']):+.4f}"
            sim = c["clap_audio_ref_deg"]
            meta += [f"CLAP text↔degraded {c['clap_text_degraded']}",
                     f"text↔reference {c['clap_text_reference']}",
                     f"Δ {delta}",
                     f"reference↔degraded {sim}"]
        cards.append(f"""<article class="card" data-m="{method}" data-d="{hit}" data-delta="{delta}" data-sim="{sim}" data-v="{band}" data-mushra="{score}" data-t="{html.escape(resp.lower())}">
<div class="top"><span class="clip">{html.escape(Path(ref).parent.name)}</span>
<span class="cond">{html.escape(cond)}</span><span class="chip">{method}</span>
<span class="chip {hit}">matched: {', '.join(found) or 'none'}</span></div>
<div class="players"><div>Reference<audio controls preload="none" src="{rel(ref)}"></audio></div>
<div>Degraded<audio controls preload="none" src="{rel(deg)}"></audio></div></div>
<p class="resp">{html.escape(resp)}</p>
<div class="meta">{''.join(f'<span>{html.escape(x)}</span>' for x in meta)}</div></article>""")

    opts = "".join(f'<option value="{m}">{m}</option>' for m in dict.fromkeys(sorted(methods)))
    (out / "index.html").write_text(PAGE.format(title=html.escape(args.predictions.stem[:60]),
                                                method_opts=opts, cards="\n".join(cards)))
    print(out / "index.html")


if __name__ == "__main__":
    main()
