"""
Markdown reports rendered to PDF.

The old backend had seven near-identical view methods for this , risk, data
governance, data quality, bias metrics, bias warnings, final bias, drift , each
roughly 130 lines that re-declared the same ReportLab styles and the same
markdown handling. This is one renderer and one table of what can be rendered.

ReportLab is pure Python: unlike WeasyPrint or pdfkit it needs no system
libraries (pango, cairo, wkhtmltopdf) in the image. The brand assets it needs
are next to it in `assets/`: the logo mark, and the same Google Sans the app
is set in, so an exported report looks like the product it came from.
"""

import datetime as dt
import logging
import re
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

log = logging.getLogger("core.reports")

ASSETS = Path(__file__).resolve().parent / "assets"
FONTS = ASSETS / "fonts"
LOGO = ASSETS / "biashawk_icon.png"

APP_NAME = "BiasHawk"

# From the logo and the app's own palette: the mark's violet, near-black ink
# for headings, grey for everything the eye should skip.
BRAND = colors.HexColor("#9286EC")
INK = colors.HexColor("#0B0E16")
BODY_INK = colors.HexColor("#2A2D2D")
MUTED = colors.HexColor("#706E6C")
RULE = colors.HexColor("#E3E3E8")
BAND = colors.HexColor("#F4F3FD")

MARGIN = 2 * cm
TOP_MARGIN = 2.4 * cm
BOTTOM_MARGIN = 1.9 * cm
CONTENT_WIDTH = A4[0] - 2 * MARGIN

# slug -> (model attribute, document title)
INSTANCE_REPORTS = {
    # The structured write-up, as in the old stack's data-gov-structure PDF.
    "data-governance": ("data_quality_description", "Data Governance Report"),
    # The measurements that write-up was made from. The old stack kept these on
    # screen only; anything the app shows, it can hand over too.
    "data-profile": ("data_profile_description", "Data Profile Description Report"),
    "data-quality": ("data_quality_report", "Data Quality Report"),
    "bias-metrics": ("metrics_report", "Bias and Fairness Metrics Report"),
    "bias-warnings": ("warnings_report", "Bias and Fairness Warnings Report"),
    "bias-final": ("final_bias_report", "Bias and Fairness Executive Report"),
    "risk": ("nist_risk_report", "NIST AI RMF Risk Assessment Report"),
}

DRIFT_REPORTS = {
    "drift": ("final_drift_report", "Data and Bias Drift Report"),
}


def _register_fonts():
    """
    Set the reports in the app's own typeface.

    Falls back to the built-in Helvetica if the files are not in the image, so
    a stripped build still renders rather than raising at import.
    """
    faces = {
        "GoogleSans": "GoogleSans-Regular.ttf",
        "GoogleSans-Bold": "GoogleSans-Bold.ttf",
        "GoogleSans-Italic": "GoogleSans-Italic.ttf",
        "GoogleSansCode": "GoogleSansCode-Regular.ttf",
    }
    try:
        for name, filename in faces.items():
            path = FONTS / filename
            if not path.exists():
                raise FileNotFoundError(path)
            pdfmetrics.registerFont(TTFont(name, str(path)))
        registerFontFamily(
            "GoogleSans",
            normal="GoogleSans",
            bold="GoogleSans-Bold",
            italic="GoogleSans-Italic",
            # No bold-italic face is shipped; bold carries more than italic in
            # a report, so *** falls back to it rather than to the regular.
            boldItalic="GoogleSans-Bold",
        )
        return "GoogleSans", "GoogleSans-Bold", "GoogleSans-Italic", "GoogleSansCode"
    except Exception:
        log.warning("Google Sans not available, falling back to Helvetica.", exc_info=True)
        return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"


BODY_FONT, BOLD_FONT, ITALIC_FONT, MONO_FONT = _register_fonts()


def _styles():
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "Brand", parent=base["BodyText"], fontName=BOLD_FONT, fontSize=17,
            leading=20, textColor=INK, spaceAfter=0,
        ),
        "brandline": ParagraphStyle(
            "BrandLine", parent=base["BodyText"], fontName=BODY_FONT, fontSize=8.5,
            leading=11, textColor=MUTED, spaceAfter=0,
        ),
        "title": ParagraphStyle(
            "DocTitle", parent=base["Title"], fontName=BOLD_FONT, fontSize=21,
            leading=25, textColor=INK, spaceBefore=0, spaceAfter=4, alignment=0,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["BodyText"], fontName=BODY_FONT, fontSize=10.5,
            leading=14, textColor=MUTED, spaceAfter=0,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName=BOLD_FONT, fontSize=14.5,
            leading=18, spaceBefore=16, spaceAfter=7, textColor=INK,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName=BOLD_FONT, fontSize=12,
            leading=15, spaceBefore=12, spaceAfter=5, textColor=INK,
        ),
        "h3": ParagraphStyle(
            "H3", parent=base["Heading3"], fontName=BOLD_FONT, fontSize=10.5,
            leading=13, spaceBefore=10, spaceAfter=4, textColor=BODY_INK,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName=BODY_FONT, fontSize=9.5,
            leading=14, spaceAfter=6, textColor=BODY_INK,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=base["BodyText"], fontName=BODY_FONT, fontSize=9.5,
            leading=14, leftIndent=15, bulletIndent=4, spaceAfter=3, textColor=BODY_INK,
        ),
        "code": ParagraphStyle(
            "Code", parent=base["Code"], fontName=MONO_FONT, fontSize=8, leading=11,
            leftIndent=10, textColor=BODY_INK, backColor=colors.HexColor("#F6F6F8"),
            borderPadding=6, spaceAfter=6,
        ),
        "th": ParagraphStyle(
            "TH", parent=base["BodyText"], fontName=BOLD_FONT, fontSize=8,
            leading=10.5, textColor=INK, spaceAfter=0,
        ),
        "td": ParagraphStyle(
            "TD", parent=base["BodyText"], fontName=BODY_FONT, fontSize=8,
            leading=10.5, textColor=BODY_INK, spaceAfter=0,
        ),
    }


def _escape(text):
    """ReportLab paragraphs take a small HTML dialect, so escape the rest."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text):
    """Markdown emphasis and code spans -> ReportLab inline markup."""
    text = _escape(text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", text)
    # Underscore emphasis, but only at a word boundary: these reports are full
    # of identifiers such as disparity_threshold that must stay as they are.
    text = re.sub(r"(?<![A-Za-z0-9_])__(?!\s)(.+?)(?<!\s)__(?![A-Za-z0-9_])", r"<b>\1</b>", text)
    text = re.sub(r"(?<![A-Za-z0-9_])_(?!\s)(.+?)(?<!\s)_(?![A-Za-z0-9_])", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", rf'<font face="{MONO_FONT}">\1</font>', text)
    # Links render as their text; the URL is not clickable in a printed report.
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", text)
    return text


def _is_table_row(line):
    return line.startswith("|") and line.count("|") >= 2


def _is_table_divider(line):
    return "|" in line and bool(re.fullmatch(r"\|?[\s:\-\|]+\|?", line))


def _split_row(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _table(rows, styles):
    """
    A markdown table as a real table.

    The old renderer flattened these into one paragraph of pipe-separated text,
    which is where the metrics reports became unreadable: they are mostly
    tables.
    """
    if not rows:
        return []

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]

    # Wide tables need smaller type to stay inside the page.
    scale = 1.0 if width <= 5 else 0.88 if width <= 8 else 0.75
    head_style = ParagraphStyle(
        "THs", parent=styles["th"], fontSize=styles["th"].fontSize * scale,
        leading=styles["th"].leading * scale,
    )
    cell_style = ParagraphStyle(
        "TDs", parent=styles["td"], fontSize=styles["td"].fontSize * scale,
        leading=styles["td"].leading * scale,
    )

    header, *body = rows
    data = [[Paragraph(_inline(cell), head_style) for cell in header]]
    data += [[Paragraph(_inline(cell), cell_style) for cell in row] for row in body]

    table = Table(
        data,
        colWidths=[CONTENT_WIDTH / width] * width,
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BAND),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, BRAND),
                ("GRID", (0, 0), (-1, -1), 0.25, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFC")]),
            ]
        )
    )
    return [Spacer(1, 4), table, Spacer(1, 8)]


def _same_title(heading, title):
    """Is this heading just the document title again?"""
    clean = lambda text: re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return clean(heading) == clean(title)


def markdown_to_flowables(markdown, styles, title=""):
    """
    Convert the subset of Markdown these reports actually use.

    Headings, bullets, numbered items, tables, code fences, horizontal rules
    and paragraphs. Anything else becomes body text rather than being dropped.

    The reports open with their own title, which the cover has already said, so
    that first heading is dropped rather than printed twice.
    """
    flowables = []
    title_seen = False
    bullet_styles = {}

    def nested_bullet(depth):
        """A bullet style indented to its depth, made once and reused."""
        if depth not in bullet_styles:
            base = styles["bullet"]
            bullet_styles[depth] = ParagraphStyle(
                f"Bullet{depth}", parent=base,
                leftIndent=base.leftIndent + depth * 14,
                bulletIndent=base.bulletIndent + depth * 14,
            )
        return bullet_styles[depth]
    in_code = False
    code_lines = []
    table_rows = []

    def flush_table():
        if table_rows:
            flowables.extend(_table(list(table_rows), styles))
            table_rows.clear()

    for raw in markdown.splitlines():
        line = raw.rstrip()

        if line.strip().startswith("```"):
            flush_table()
            if in_code:
                flowables.append(
                    Paragraph("<br/>".join(_escape(c) for c in code_lines), styles["code"])
                )
                code_lines = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line or " ")
            continue

        stripped = line.strip()
        # Indentation is what makes a sub-list a sub-list; the reports lean on
        # it heavily, so it is measured before the line is stripped.
        depth = min((len(line) - len(line.lstrip(" "))) // 2, 3)

        if _is_table_row(stripped):
            if not _is_table_divider(stripped):
                table_rows.append(_split_row(stripped))
            continue
        flush_table()

        if not stripped:
            continue

        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            flowables.append(Spacer(1, 10))
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if heading:
            level = len(heading.group(1))
            if not title_seen and level == 1:
                title_seen = True
                if title and _same_title(heading.group(2), title):
                    continue
            text = _inline(heading.group(2))
            style = styles["h1"] if level <= 2 else styles["h2"] if level == 3 else styles["h3"]
            flowables.append(Paragraph(text, style))
            continue

        bullet = re.match(r"^[-*+]\s+(.*)", stripped)
        if bullet:
            # Glyphs the shipped faces actually carry: a white bullet would
            # come out as a .notdef box.
            marker = "•" if depth == 0 else "·" if depth == 1 else "–"
            flowables.append(
                Paragraph(_inline(bullet.group(1)), nested_bullet(depth), bulletText=marker)
            )
            continue

        numbered = re.match(r"^(\d+)[.)]\s+(.*)", stripped)
        if numbered:
            flowables.append(
                Paragraph(
                    _inline(numbered.group(2)),
                    nested_bullet(depth),
                    bulletText=f"{numbered.group(1)}.",
                )
            )
            continue

        flowables.append(Paragraph(_inline(stripped), styles["body"]))

    flush_table()
    return flowables


def _masthead(title, subtitle, styles):
    """Logo, app name and what this document is, above a brand rule."""
    generated = dt.datetime.now().strftime("%d %B %Y")

    name_block = [Paragraph(APP_NAME, styles["brand"])]
    name_block.append(Paragraph("AI fairness and compliance reporting", styles["brandline"]))

    if LOGO.exists():
        mark = Image(str(LOGO), width=1.25 * cm, height=1.25 * cm * 263 / 256)
        header = Table(
            [[mark, name_block]],
            colWidths=[1.7 * cm, CONTENT_WIDTH - 1.7 * cm],
            hAlign="LEFT",
        )
    else:
        header = Table([[name_block]], colWidths=[CONTENT_WIDTH], hAlign="LEFT")

    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    rule = Table([[""]], colWidths=[CONTENT_WIDTH], rowHeights=[1.6])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BRAND)]))

    block = [header, Spacer(1, 16), Paragraph(_escape(title), styles["title"])]
    if subtitle:
        block.append(Paragraph(_escape(subtitle), styles["subtitle"]))
    block.append(Paragraph(f"Generated {generated}", styles["subtitle"]))
    block.append(Spacer(1, 10))
    block.append(rule)
    block.append(Spacer(1, 14))
    return [KeepTogether(block)]


def _furniture(title):
    """The running header and footer, drawn on every page."""
    generated = dt.datetime.now().strftime("%d %B %Y")

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont(BODY_FONT, 7.5)
        canvas.setFillColor(MUTED)

        top = A4[1] - 1.15 * cm
        canvas.drawString(MARGIN, top, APP_NAME)
        canvas.drawRightString(A4[0] - MARGIN, top, title)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, top - 4, A4[0] - MARGIN, top - 4)

        bottom = 1.15 * cm
        canvas.line(MARGIN, bottom + 10, A4[0] - MARGIN, bottom + 10)
        canvas.drawString(MARGIN, bottom, generated)
        canvas.drawRightString(A4[0] - MARGIN, bottom, str(canvas.getPageNumber()))
        canvas.restoreState()

    return draw


def render_pdf(markdown, title, subtitle=""):
    """Render a Markdown report to PDF bytes."""
    styles = _styles()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=f"{APP_NAME} , {title}",
        author=APP_NAME,
        subject=subtitle or title,
    )

    story = _masthead(title, subtitle, styles)
    story.extend(markdown_to_flowables(markdown or "_No content._", styles, title))

    decorate = _furniture(title)
    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()
