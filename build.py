#!/usr/bin/env python3
"""Génère la version HTML du cours à partir du Markdown.

    python3 build.py                 -> docs/index.html (page complète, autonome)
    python3 build.py --fragment F    -> F : contenu sans <html>/<head>/<body> (pour publication)

Dépendance : python-markdown (pip install markdown).
"""
import html
import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
SRC = ROOT / "cours" / "cours-sql-server-performance.md"
OUT = ROOT / "docs" / "index.html"

TITLE = "SQL Server à grande échelle"
SUBTITLE = "Cours de performance : penser comme le moteur, puis diagnostiquer et corriger sur un lab"

# ---------------------------------------------------------------- slug (style GitHub)


def gh_slug(value, separator="-"):
    value = re.sub(r"`", "", value).lower()
    value = re.sub(r"[^\w\- ]", "", value)
    return value.replace(" ", separator)


# ---------------------------------------------------------------- coloration SQL

KEYWORDS = set(
    """SELECT FROM WHERE AND OR NOT IN IS NULL AS ON JOIN LEFT RIGHT INNER OUTER CROSS APPLY ORDER BY
    GROUP HAVING TOP DISTINCT UNION ALL INSERT INTO VALUES UPDATE SET DELETE CREATE ALTER DROP TABLE
    INDEX CLUSTERED NONCLUSTERED COLUMNSTORE PARTITION FUNCTION SCHEME RANGE FOR TO WITH OPTION DECLARE
    BEGIN END WHILE IF ELSE EXEC EXECUTE PROCEDURE DATABASE SCOPED CONFIGURATION GO TRUNCATE CONSTRAINT
    PRIMARY KEY INCLUDE REBUILD REORGANIZE RESUME PAUSE ONLINE OFF STATISTICS DBCC OVER CASE WHEN THEN
    LIKE BETWEEN EXISTS SWITCH SPLIT MERGE NEXT USED IDENTITY ROLLBACK IMMEDIATE RECONFIGURE
    PARTITIONS FULLSCAN SAMPLE PERCENT RESAMPLE INCREMENTAL OPTIMIZE UNKNOWN RECOMPILE USE HINT
    HOURS DAYS MINUTES CLEAR PLAN STATISTICS TABLOCK MAXDOP RESUMABLE
    INT BIGINT DATETIME DATETIME2 DECIMAL VARCHAR NVARCHAR CHAR NCHAR DATE BIT""".split()
)

TOKEN = re.compile(
    r"(?P<comment>--[^\n]*)"
    r"|(?P<string>'(?:[^']|'')*')"
    r"|(?P<bracket>\[[^\]]*\])"
    r"|(?P<var>@@?\w+)"
    r"|(?P<number>\b\d+(?:\.\d+)?\b)"
    r"|(?P<word>[A-Za-z_][\w$]*)"
)


def highlight_sql(code: str) -> str:
    out = []
    pos = 0
    for m in TOKEN.finditer(code):
        out.append(html.escape(code[pos : m.start()]))
        kind = m.lastgroup
        text = m.group()
        esc = html.escape(text)
        if kind == "word":
            if text.upper() in KEYWORDS:
                out.append(f'<span class="k">{esc}</span>')
            elif code[m.end() : m.end() + 1] == "(":
                out.append(f'<span class="f">{esc}</span>')
            else:
                out.append(esc)
        elif kind == "comment":
            out.append(f'<span class="c">{esc}</span>')
        elif kind == "string":
            out.append(f'<span class="s">{esc}</span>')
        elif kind == "var":
            out.append(f'<span class="v">{esc}</span>')
        elif kind == "number":
            out.append(f'<span class="n">{esc}</span>')
        else:
            out.append(esc)
        pos = m.end()
    out.append(html.escape(code[pos:]))
    return "".join(out)


# ---------------------------------------------------------------- markdown -> html


def convert(md_text: str) -> str:
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
        extension_configs={"toc": {"slugify": gh_slug, "toc_depth": "1-3"}},
    )
    return md.convert(md_text)


def postprocess(body: str) -> str:
    # blocs de code : coloration + bouton copier
    def code_block(m):
        lang, inner = m.group(1), html.unescape(m.group(2))
        if lang == "sql":
            return (
                '<figure class="code"><button type="button" class="copy" aria-label="Copier le code">Copier</button>'
                f'<pre><code class="language-sql">{highlight_sql(inner)}</code></pre></figure>'
            )
        return f'<figure class="code diagram"><pre><code>{html.escape(inner)}</code></pre></figure>'

    body = re.sub(
        r'<pre><code class="language-(\w+)">(.*?)</code></pre>', code_block, body, flags=re.S
    )

    # tableaux : conteneur défilant
    body = re.sub(r"<table>(.*?)</table>", r'<div class="table-wrap"><table>\1</table></div>', body, flags=re.S)

    # "Ce qu'il faut pouvoir expliquer" -> encart de révision
    body = re.sub(
        r'<h3 id="(ce-quil-faut-pouvoir-expliquer[^"]*)">Ce qu\'il faut pouvoir expliquer</h3>\s*<ul>(.*?)</ul>',
        r'<aside class="recap" id="\1"><h3>Ce qu\'il faut pouvoir expliquer</h3><ul>\2</ul></aside>',
        body,
        flags=re.S,
    )
    # "Exercice" -> encart jusqu'à la fin de la section
    body = re.sub(
        r'<h3 id="(exercice[^"]*)">Exercice</h3>(.*?)(?=<hr />|<h2 |<h1 |\Z)',
        r'<aside class="exercise" id="\1"><h3>Exercice</h3>\2</aside>',
        body,
        flags=re.S,
    )
    # chaînes de causalité (épisode 15) : paragraphes qui commencent en gras
    body = re.sub(r"<p><strong>", '<p class="chain"><strong>', body)

    # h2 : kicker "Épisode N" / "Chapitre N"
    def h2(m):
        hid, text = m.group(1), m.group(2)
        mm = re.match(r"(Épisode (\d+)|(\d+))\. (.*)", text)
        if mm:
            kicker = f"Épisode {mm.group(2)}" if mm.group(2) else f"Chapitre {mm.group(3)}"
            return f'<h2 id="{hid}"><span class="kicker">{kicker}</span>{mm.group(4)}</h2>'
        return m.group(0)

    body = re.sub(r'<h2 id="([^"]+)">(.*?)</h2>', h2, body)
    # h1 restants = parties
    body = re.sub(r'<h1 id="([^"]+)">(.*?)</h1>', r'<h1 class="part" id="\1">\2</h1>', body)
    return body


# ---------------------------------------------------------------- navigation


def build_nav(md_text: str) -> str:
    items = []
    for line in md_text.split("\n"):
        if line.startswith("# Partie"):
            title = line[2:]
            items.append(("part", gh_slug(title), title))
        elif line.startswith("## ") and not line.startswith("## Sommaire"):
            title = line[3:]
            m = re.match(r"(?:Épisode )?(\d+)\. (.*)", title)
            if m:
                items.append(("item", gh_slug(title), m.group(1), re.sub(r"`", "", m.group(2))))
    out = []
    open_list = False
    for it in items:
        if it[0] == "part":
            if open_list:
                out.append("</ol>")
            label = it[2].split(" : ", 1)
            out.append(
                f'<a class="part-link" href="#{it[1]}"><span>{html.escape(label[0])}</span>'
                f"{html.escape(label[1]) if len(label) > 1 else ''}</a><ol>"
            )
            open_list = True
        else:
            out.append(f'<li><a href="#{it[1]}"><b>{it[2]}</b><span>{html.escape(it[3])}</span></a></li>')
    if open_list:
        out.append("</ol>")
    return "\n".join(out)


# ---------------------------------------------------------------- page

CSS = r"""
:root {
  --bg: #F3F5F7; --surface: #FFFFFF; --ink: #1D2733; --muted: #5E6B78; --line: #D8DEE5;
  --accent: #1F5F8B; --accent-ink: #174A6E; --accent-soft: #E6EFF6;
  --amber: #8A5A00; --amber-soft: #FFF3D6; --amber-line: #E9C46A;
  --code-bg: #EEF1F5; --code-ink: #1D2733;
  --k: #1F5F8B; --s: #2E7D4F; --c: #7A8794; --n: #A6551D; --v: #7A3E9D; --f: #0B6E6E;
  --shadow: 0 1px 2px rgba(29,39,51,.06), 0 8px 24px rgba(29,39,51,.06);
  --serif: "IBM Plex Serif", Georgia, "Times New Roman", serif;
  --sans: "IBM Plex Sans", "Segoe UI", Helvetica, Arial, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #10151B; --surface: #171E26; --ink: #E4E9EE; --muted: #9AA6B2; --line: #2B3540;
    --accent: #7DB3E3; --accent-ink: #A9CDEE; --accent-soft: #1B2A3A;
    --amber: #E5B85C; --amber-soft: #2A2410; --amber-line: #7A5F1E;
    --code-bg: #0C1116; --code-ink: #DCE3EA;
    --k: #7DB3E3; --s: #8FD19E; --c: #7C8894; --n: #E0A070; --v: #C8A2E0; --f: #6FC9C9;
    --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
  }
}
:root[data-theme="dark"] {
  --bg: #10151B; --surface: #171E26; --ink: #E4E9EE; --muted: #9AA6B2; --line: #2B3540;
  --accent: #7DB3E3; --accent-ink: #A9CDEE; --accent-soft: #1B2A3A;
  --amber: #E5B85C; --amber-soft: #2A2410; --amber-line: #7A5F1E;
  --code-bg: #0C1116; --code-ink: #DCE3EA;
  --k: #7DB3E3; --s: #8FD19E; --c: #7C8894; --n: #E0A070; --v: #C8A2E0; --f: #6FC9C9;
  --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 24px; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 400 17px/1.6 var(--sans); -webkit-font-smoothing: antialiased;
  padding-block: 0; padding-inline: 16px;
}
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 3px; }
a:hover { color: var(--accent-ink); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 3px; }

/* ---- en-tête ---- */
.top { max-width: 1240px; margin: 0 auto; padding-block: 40px 28px; border-bottom: 1px solid var(--line); }
.top .eyebrow { font: 500 12px/1 var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin: 0 0 14px; }
.top h1 { font: 600 clamp(28px, 4vw, 42px)/1.15 var(--serif); margin: 0 0 10px; text-wrap: balance; letter-spacing: -.01em; }
.top .sub { margin: 0; color: var(--muted); font-size: 18px; max-width: 62ch; text-wrap: pretty; }
.top .meta { display: flex; flex-wrap: wrap; gap: 8px 22px; margin: 18px 0 0; padding: 0; list-style: none; font: 500 13px/1.4 var(--mono); color: var(--muted); }
.top .meta b { color: var(--ink); font-weight: 600; }

/* ---- structure ---- */
.shell { max-width: 1240px; margin: 0 auto; display: grid; grid-template-columns: 290px minmax(0, 1fr); gap: 56px; align-items: start; }
.side { position: sticky; top: 0; max-height: 100vh; overflow-y: auto; padding-block: 28px 40px; font-size: 14px; }
.side summary { display: none; }
.side .part-link { display: block; margin: 18px 0 8px; color: var(--ink); text-decoration: none; font: 600 15px/1.3 var(--serif); }
.side .part-link span { display: block; font: 500 11px/1 var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 4px; }
.side ol { list-style: none; margin: 0; padding: 0; border-left: 1px solid var(--line); }
.side li a { display: grid; grid-template-columns: 26px 1fr; gap: 8px; padding: 5px 10px 5px 12px; color: var(--muted); text-decoration: none; line-height: 1.35; margin-left: -1px; border-left: 2px solid transparent; }
.side li a b { font: 500 12px/1.6 var(--mono); color: var(--muted); }
.side li a:hover { color: var(--ink); }
.side li a[aria-current="true"] { color: var(--ink); border-left-color: var(--accent); background: var(--accent-soft); }
.side li a[aria-current="true"] b { color: var(--accent); }

.doc { max-width: 76ch; padding-block: 28px 96px; }
.doc > p:first-child { font-size: 19px; }
.doc p, .doc li { text-wrap: pretty; }
.doc h1.part { font: 600 13px/1 var(--mono); letter-spacing: .14em; text-transform: uppercase; color: var(--accent); margin: 72px 0 8px; padding-top: 24px; border-top: 3px solid var(--accent); }
.doc h1.part + p { color: var(--muted); }
.doc h2 { font: 600 30px/1.2 var(--serif); margin: 64px 0 20px; letter-spacing: -.01em; text-wrap: balance; }
.doc h2 .kicker { display: block; font: 500 12px/1 var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }
.doc h3 { font: 600 19px/1.3 var(--serif); margin: 36px 0 10px; }
.doc p { margin: 0 0 16px; }
.doc ul, .doc ol { margin: 0 0 16px; padding-left: 1.4em; }
.doc li { margin: 4px 0; }
.doc li::marker { color: var(--muted); }
.doc hr { border: 0; height: 1px; background: var(--line); margin: 48px 0 0; }
.doc code { font: 400 .88em/1.4 var(--mono); background: var(--code-bg); color: var(--code-ink); padding: .1em .35em; border-radius: 4px; }
.doc strong { font-weight: 600; }

/* ---- chaînes de causalité ---- */
.doc p.chain { border-left: 3px solid var(--amber-line); padding: 6px 0 6px 16px; margin: 0 0 18px; }
.doc p.chain strong { display: block; margin-bottom: 4px; font-family: var(--serif); font-size: 18px; }

/* ---- code ---- */
figure.code { margin: 20px 0 24px; position: relative; background: var(--code-bg); border: 1px solid var(--line); border-radius: 8px; }
figure.code pre { margin: 0; padding: 16px 18px; overflow-x: auto; font: 400 14px/1.55 var(--mono); color: var(--code-ink); tab-size: 4; }
figure.code pre code { background: none; padding: 0; font-size: inherit; }
figure.code .copy { position: absolute; top: 8px; right: 8px; font: 500 11px/1 var(--mono); letter-spacing: .06em; text-transform: uppercase; color: var(--muted); background: var(--surface); border: 1px solid var(--line); border-radius: 5px; padding: 6px 8px; cursor: pointer; opacity: 0; transition: opacity .15s; }
figure.code:hover .copy, figure.code .copy:focus-visible, figure.code .copy.done { opacity: 1; }
figure.code .copy.done { color: var(--s); border-color: var(--s); }
figure.code.diagram { background: var(--surface); }
.k { color: var(--k); font-weight: 500; } .s { color: var(--s); } .c { color: var(--c); font-style: italic; }
.n { color: var(--n); } .v { color: var(--v); } .f { color: var(--f); }

/* ---- tableaux ---- */
.table-wrap { overflow-x: auto; margin: 20px 0 24px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }
table { border-collapse: collapse; width: 100%; font-size: 15px; font-variant-numeric: tabular-nums; }
th, td { text-align: left; vertical-align: top; padding: 10px 14px; border-bottom: 1px solid var(--line); }
th { font: 500 12px/1.3 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); background: var(--code-bg); }
tr:last-child td { border-bottom: 0; }
td code { font-size: .85em; white-space: nowrap; }

/* ---- encarts ---- */
aside.recap, aside.exercise { margin: 32px 0 8px; padding: 20px 24px 8px; border-radius: 10px; }
aside.recap { background: var(--accent-soft); border: 1px solid transparent; }
aside.exercise { background: var(--amber-soft); border: 1px solid var(--amber-line); }
aside h3 { margin: 0 0 12px !important; font: 500 12px/1 var(--mono) !important; letter-spacing: .12em; text-transform: uppercase; }
aside.recap h3 { color: var(--accent-ink); }
aside.exercise h3 { color: var(--amber); }
aside.recap h3::before { content: "✓  "; }
aside.exercise h3::before { content: "▶  "; }
aside p, aside ul, aside ol { margin-bottom: 12px; }
aside figure.code { background: var(--surface); }

/* ---- responsive ---- */
@media (max-width: 960px) {
  .shell { grid-template-columns: 1fr; gap: 0; }
  .side { position: static; max-height: none; padding-block: 16px 0; border-bottom: 1px solid var(--line); }
  .side summary { display: block; cursor: pointer; font: 600 15px/1 var(--serif); padding: 8px 0; list-style: none; }
  .side summary::before { content: "☰  "; color: var(--muted); }
  .side[open] summary { margin-bottom: 8px; }
  .doc h2 { font-size: 26px; margin-top: 48px; }
  body { font-size: 16px; }
}
@media print {
  body { background: #fff; color: #000; font-size: 11pt; padding: 0; }
  .side, .copy { display: none !important; }
  .shell { display: block; }
  .doc { max-width: none; }
  figure.code, .table-wrap, aside { break-inside: avoid; box-shadow: none; }
  .doc h2 { break-before: page; margin-top: 0; }
  .doc h1.part { break-before: page; }
  a { color: inherit; text-decoration: none; }
}
"""

JS = r"""
(function () {
  // sommaire repliable sur mobile
  var side = document.querySelector('details.side');
  if (side && window.matchMedia('(max-width: 960px)').matches) side.removeAttribute('open');

  // surlignage de la section courante
  var links = Array.prototype.slice.call(document.querySelectorAll('.side li a'));
  var byId = {};
  links.forEach(function (a) { byId[a.getAttribute('href').slice(1)] = a; });
  var heads = Array.prototype.slice.call(document.querySelectorAll('.doc h2[id]'));
  function setCurrent(id) {
    links.forEach(function (a) { a.removeAttribute('aria-current'); });
    var a = byId[id];
    if (a) { a.setAttribute('aria-current', 'true'); }
  }
  function onScroll() {
    var y = window.scrollY + 120, cur = heads[0];
    for (var i = 0; i < heads.length; i++) { if (heads[i].offsetTop <= y) cur = heads[i]; else break; }
    if (cur) setCurrent(cur.id);
  }
  if (heads.length) { window.addEventListener('scroll', onScroll, { passive: true }); onScroll(); }

  // copier un bloc de code
  document.querySelectorAll('figure.code .copy').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var text = btn.parentNode.querySelector('pre').innerText;
      function done() { btn.textContent = 'Copié'; btn.classList.add('done'); setTimeout(function () { btn.textContent = 'Copier'; btn.classList.remove('done'); }, 1600); }
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).then(done, fallback); } else { fallback(); }
      } catch (e) { fallback(); }
      function fallback() {
        var sel = window.getSelection(), range = document.createRange();
        range.selectNodeContents(btn.parentNode.querySelector('pre')); sel.removeAllRanges(); sel.addRange(range);
        try { document.execCommand('copy'); done(); } catch (e) {}
      }
    });
  });
})();
"""


def build(md_text: str) -> tuple[str, str]:
    """Retourne (fragment, page complète)."""
    # intro = tout ce qui précède "## Sommaire" (sans le titre h1)
    intro_md, rest = md_text.split("## Sommaire", 1)
    intro_md = re.sub(r"^# .*\n", "", intro_md, count=1).strip()
    # on retire les listes du sommaire (la navigation latérale les remplace), on garde le parcours conseillé
    rest = "## Parcours conseillé" + rest.split("### Parcours conseillé", 1)[1]
    body = postprocess(convert(intro_md + "\n\n" + rest))
    nav = build_nav(md_text)

    n_ep = len(re.findall(r"^## Épisode", md_text, flags=re.M))
    n_ch = len(re.findall(r"^## \d+\.", md_text, flags=re.M))
    n_sql = md_text.count("```sql")

    fragment = f"""<title>{TITLE}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,400;0,500;1,400&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Serif:wght@500;600&display=swap">
<style>{CSS}</style>
<header class="top">
  <p class="eyebrow">Cours · SQL Server 2019 et 2022</p>
  <h1>{TITLE}</h1>
  <p class="sub">{SUBTITLE}</p>
  <ul class="meta">
    <li><b>{n_ep}</b> épisodes de théorie</li>
    <li><b>{n_ch}</b> chapitres pratiques</li>
    <li><b>{n_sql}</b> scripts T-SQL</li>
    <li>d'après <b>How to Think Like the SQL Server Engine</b>, Brent Ozar</li>
  </ul>
</header>
<div class="shell">
  <details class="side" open>
    <summary>Sommaire</summary>
    <nav aria-label="Sommaire">
{nav}
    </nav>
  </details>
  <main class="doc">
{body}
  </main>
</div>
<script>{JS}</script>
"""
    # <title>/<link>/<style> vont dans <head>, le reste dans <body>
    head_part, body_part = fragment.split("<header", 1)
    page = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
{head_part}</head>
<body>
<header{body_part}</body>
</html>
"""
    return fragment, page


def main():
    md_text = SRC.read_text(encoding="utf-8")
    fragment, page = build(md_text)
    if len(sys.argv) > 2 and sys.argv[1] == "--fragment":
        Path(sys.argv[2]).write_text(fragment, encoding="utf-8")
        print(f"fragment -> {sys.argv[2]} ({len(fragment) // 1024} Ko)")
    else:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(page, encoding="utf-8")
        print(f"page -> {OUT} ({len(page) // 1024} Ko)")


if __name__ == "__main__":
    main()
