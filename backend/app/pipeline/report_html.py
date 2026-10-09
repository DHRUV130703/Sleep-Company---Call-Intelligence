"""Render the report outline (report.py) as a print-ready web page — "Save as PDF" from the browser.

Why the browser makes the PDF: Hindi (Devanagari) quotes need proper text shaping. Browsers do this
perfectly with the fonts already on the computer; Python PDF libraries would need extra font files.
Opened with ?print=1 the page shows the print dialog straight away.
"""

from html import escape

from app.pipeline.report import Bullets, Para, Quote, Report, Sub, Table

CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: Inter, -apple-system, "Segoe UI", Roboto, "Noto Sans", "Noto Sans Devanagari", sans-serif;
       color: #111318; background: #fff; margin: 0 auto; max-width: 900px; padding: 24px; font-size: 13px; line-height: 1.5; }
h1 { font-size: 24px; margin: 0 0 4px; }
h2 { font-size: 17px; margin: 28px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #e6e7eb; break-after: avoid; }
h3 { font-size: 14px; margin: 16px 0 6px; break-after: avoid; }
.meta, .muted { color: #6b7280; }
.meta { margin: 0; }
table { width: 100%; border-collapse: collapse; margin: 6px 0 12px; break-inside: auto; }
th, td { border: 1px solid #e6e7eb; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #f1f2f4; font-weight: 600; }
tr { break-inside: avoid; }
th.ai { color: #2f6fde; } th.human { color: #e8692c; }
blockquote { margin: 6px 0; padding: 6px 10px; border-left: 3px solid #c9ccd3; background: #f7f7f8; break-inside: avoid; }
blockquote .src { display: block; color: #6b7280; font-size: 11px; margin-top: 2px; }
.bar { position: sticky; top: 0; background: #fff; padding: 8px 0 12px; display: flex; gap: 8px; align-items: center; }
.bar button { font: inherit; padding: 6px 12px; border: 1px solid #c9ccd3; border-radius: 8px; background: #111318;
              color: #fff; cursor: pointer; }
@media print { .bar { display: none; } body { padding: 0; } }
"""


def _block(b: object) -> str:
    if isinstance(b, Sub):
        return f"<h3>{escape(b.text)}</h3>"
    if isinstance(b, Para):
        return f'<p class="{"muted" if b.muted else ""}">{escape(b.text)}</p>'
    if isinstance(b, Bullets):
        return "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in b.items) + "</ul>"
    if isinstance(b, Quote):
        return f'<blockquote>“{escape(b.text)}”<span class="src">{escape(b.source)}</span></blockquote>'
    if isinstance(b, Table):

        def th(h: str) -> str:
            cls = "ai" if h == "AI voice bot" else "human" if h == "Human agents" else ""
            return f'<th class="{cls}">{escape(h)}</th>'

        head = "".join(th(h) for h in b.headers)
        body = "".join("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row) + "</tr>" for row in b.rows)
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    return ""


def render_html(report: Report, auto_print: bool = False) -> str:
    sections = "".join(
        f"<section><h2>{escape(s.heading)}</h2>{''.join(_block(b) for b in s.blocks)}</section>"
        for s in report.sections
    )
    meta = "".join(f'<p class="meta">{escape(m)}</p>' for m in report.meta)
    script = (
        "<script>window.addEventListener('load', () => setTimeout(() => window.print(), 300))</script>"
        if auto_print
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(report.title)}</title><style>{CSS}</style></head>
<body>
<div class="bar"><button onclick="window.print()">Save as PDF / Print</button>
<span class="muted">In the print dialog choose “Save as PDF”.</span></div>
<h1>{escape(report.title)}</h1>{meta}
{sections}
{script}
</body></html>"""
