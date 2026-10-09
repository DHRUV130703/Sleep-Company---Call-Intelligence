"""Render the report outline (report.py) as a PDF on the server, with fpdf2.

Hindi (Devanagari) needs text shaping (joined letters like क्या): fpdf2 does it with HarfBuzz (`uharfbuzz`),
using the Noto fonts bundled in app/fonts/ (SIL Open Font License, see OFL.txt). Latin text uses Noto Sans;
any character it lacks falls back to Noto Sans Devanagari.
"""

from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from app.pipeline.report_blocks import Bullets, Para, Quote, Report, Sub, Table

FONTS = Path(__file__).resolve().parents[1] / "fonts"
INK, MUTED, RULE = (17, 19, 24), (107, 114, 128), (201, 204, 211)
AI_BLUE, HUMAN_ORANGE, HEAD_BG = (47, 111, 222), (232, 105, 44), (241, 242, 244)
MIN_COL_MM = 17


# Characters the bundled fonts don't have, replaced with ones they do.
MISSING_GLYPHS = str.maketrans({"→": "->", "←": "<-", "⚠": "!"})


def _clean(text: str) -> str:
    return text.translate(MISSING_GLYPHS)


def _pdf() -> FPDF:
    pdf = FPDF(format="A4")
    pdf.set_margins(14, 16, 14)
    pdf.set_auto_page_break(True, margin=16)
    pdf.add_font("Noto", "", FONTS / "NotoSans-Regular.ttf")
    pdf.add_font("Noto", "B", FONTS / "NotoSans-Bold.ttf")
    pdf.add_font("Noto", "I", FONTS / "NotoSans-Italic.ttf")
    pdf.add_font("Deva", "", FONTS / "NotoSansDevanagari-Regular.ttf")
    pdf.add_font("Deva", "B", FONTS / "NotoSansDevanagari-Bold.ttf")
    pdf.set_fallback_fonts(["Deva"], exact_match=False)
    pdf.set_text_shaping(True)
    pdf.set_text_color(*INK)
    return pdf


def _text(
    pdf: FPDF, text: str, size: float = 10, style: str = "", color: tuple = INK, h: float = 5.2
) -> None:
    pdf.set_font("Noto", style, size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, h, _clean(text), align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)


def _col_widths(block: Table, page_width: float) -> tuple[float, ...]:
    """Column widths in mm: wider for longer text, but never narrower than MIN_COL_MM."""
    n_cols = len(block.headers)
    lengths = [
        max([len(block.headers[i])] + [len(r[i]) for r in block.rows if i < len(r)]) for i in range(n_cols)
    ]
    weights = [min(max(n, 8), 60) for n in lengths]
    widths = [page_width * w / sum(weights) for w in weights]
    short = sum(MIN_COL_MM - w for w in widths if w < MIN_COL_MM)
    if short:
        wide = sum(w for w in widths if w >= MIN_COL_MM)
        widths = [MIN_COL_MM if w < MIN_COL_MM else w - short * w / wide for w in widths]
    return tuple(widths)


def _table(pdf: FPDF, block: Table, base_url: str) -> None:
    pdf.set_font("Noto", "", 8)
    pdf.set_draw_color(*RULE)
    head = FontFace(emphasis="BOLD", fill_color=HEAD_BG)
    with pdf.table(
        col_widths=_col_widths(block, pdf.epw),
        headings_style=head,
        line_height=4.2,
        padding=1.2,
        text_align="LEFT",
    ) as t:
        row = t.row()
        for h in block.headers:
            color = AI_BLUE if h == "AI voice bot" else HUMAN_ORANGE if h == "Human agents" else INK
            row.cell(_clean(h), style=FontFace(emphasis="BOLD", color=color, fill_color=HEAD_BG))
        for values in block.rows:
            row = t.row()
            for v in values:
                row.cell(_clean(v))
    pdf.ln(3)


def _quote(pdf: FPDF, block: Quote, base_url: str) -> None:
    x, y = pdf.get_x(), pdf.get_y()
    pdf.set_x(x + 3)
    pdf.set_font("Noto", "I", 9.5)
    pdf.multi_cell(0, 4.8, f"“{_clean(block.text)}”", align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(x + 3)
    pdf.set_font("Noto", "", 7.5)
    pdf.set_text_color(*MUTED)
    link = f"{base_url}{block.href}" if base_url and block.href else ""
    pdf.multi_cell(0, 3.8, _clean(block.source), link=link, align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.6)
    pdf.line(x + 0.5, y, x + 0.5, pdf.get_y())  # the quote's left bar (same page only)
    pdf.set_line_width(0.2)
    pdf.ln(1.5)


def render_pdf(report: Report, base_url: str = "") -> bytes:
    """`base_url` (e.g. https://app.example.com) turns quote sources into links to the call moment."""
    pdf = _pdf()
    pdf.add_page()
    _text(pdf, report.title, 18, "B", h=9)
    for line in report.meta:
        _text(pdf, line, 9, color=MUTED, h=4.6)
    for section in report.sections:
        pdf.ln(4)
        if pdf.get_y() > pdf.h - 45:  # don't strand a heading at the bottom of a page
            pdf.add_page()
        _text(pdf, section.heading, 13, "B", h=7)
        pdf.set_draw_color(*RULE)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(2)
        for b in section.blocks:
            if isinstance(b, Sub):
                pdf.ln(1.5)
                _text(pdf, b.text, 10.5, "B", h=5.6)
            elif isinstance(b, Para):
                _text(pdf, b.text, 9.5, color=MUTED if b.muted else INK)
            elif isinstance(b, Bullets):
                for item in b.items:
                    _text(pdf, f"•  {item}", 9.5)
            elif isinstance(b, Quote):
                _quote(pdf, b, base_url)
            elif isinstance(b, Table):
                _table(pdf, b, base_url)
    return bytes(pdf.output())
