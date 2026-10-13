"""Generate the submission-ready GeoInspect PDF and editable draw.io diagrams.

Run with the bundled/documentation Python or any Python environment containing
ReportLab:

    python scripts/generate_submission_docs.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PDF_PATH = DOCS / "GeoInspect_Design_Report.pdf"
DRAWIO_PATH = DOCS / "GeoInspect_Architecture.drawio"

NAVY = colors.HexColor("#0B1F33")
BLUE = colors.HexColor("#176B87")
TEAL = colors.HexColor("#17A2A4")
PALE = colors.HexColor("#EAF5F5")
GOLD = colors.HexColor("#F4B942")
INK = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#526275")
LINE = colors.HexColor("#CBD5E1")
GREEN = colors.HexColor("#17865A")
RED = colors.HexColor("#C83A4A")
WHITE = colors.white


styles = getSampleStyleSheet()
TITLE = ParagraphStyle(
    "TitleCustom", parent=styles["Title"], fontName="Helvetica-Bold",
    fontSize=27, leading=31, textColor=NAVY, spaceAfter=8,
)
SUBTITLE = ParagraphStyle(
    "Subtitle", parent=styles["Normal"], fontName="Helvetica",
    fontSize=13, leading=17, textColor=BLUE, spaceAfter=12,
)
H1 = ParagraphStyle(
    "H1Custom", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=18, leading=22, textColor=NAVY, spaceAfter=8,
)
H2 = ParagraphStyle(
    "H2Custom", parent=styles["Heading2"], fontName="Helvetica-Bold",
    fontSize=11.5, leading=14, textColor=BLUE, spaceBefore=5, spaceAfter=4,
)
BODY = ParagraphStyle(
    "BodyCustom", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.8, leading=12.2, textColor=INK, spaceAfter=5,
)
SMALL = ParagraphStyle(
    "Small", parent=BODY, fontSize=7.6, leading=10, textColor=MUTED,
)
TINY = ParagraphStyle(
    "Tiny", parent=BODY, fontSize=6.8, leading=8.5, textColor=MUTED,
)
CALLOUT = ParagraphStyle(
    "Callout", parent=BODY, fontName="Helvetica-Bold", fontSize=9,
    leading=12.5, textColor=NAVY,
)
TABLE_HEAD = ParagraphStyle(
    "TableHead", parent=BODY, fontName="Helvetica-Bold", fontSize=7.7,
    leading=9.5, textColor=WHITE,
)
TABLE_CELL = ParagraphStyle(
    "TableCell", parent=BODY, fontSize=7.4, leading=9.4, spaceAfter=0,
)
CODE = ParagraphStyle(
    "Code", parent=BODY, fontName="Courier", fontSize=7.1, leading=9.1,
    leftIndent=7, rightIndent=7, borderColor=LINE, borderWidth=0.6,
    borderPadding=6, backColor=colors.HexColor("#F8FAFC"), spaceAfter=6,
)


def p(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(text, style)


def tbl(rows, widths, header=True, font_size=7.4):
    converted = []
    for r_i, row in enumerate(rows):
        converted.append([
            p(str(cell), TABLE_HEAD if header and r_i == 0 else ParagraphStyle(
                f"cell-{r_i}-{c_i}", parent=TABLE_CELL, fontSize=font_size,
                leading=font_size + 2,
            ))
            for c_i, cell in enumerate(row)
        ])
    t = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#F8FAFC")]),
        ]
    t.setStyle(TableStyle(commands))
    return t


def band(text: str, color=TEAL):
    t = Table([[p(text, CALLOUT)]], colWidths=[174 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.8, color),
        ("LINEBEFORE", (0, 0), (0, -1), 4, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def bullet(text: str):
    return p(f"<font color='#17A2A4'>&#9679;</font>&nbsp;&nbsp;{text}", BODY)


def arrow(d: Drawing, x1, y1, x2, y2, label="", color=BLUE, dy=4):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.4))
    angle = 1 if x2 >= x1 else -1
    d.add(Polygon([x2, y2, x2 - 5 * angle, y2 + 3, x2 - 5 * angle, y2 - 3],
                  fillColor=color, strokeColor=color))
    if label:
        d.add(String((x1 + x2) / 2, (y1 + y2) / 2 + dy, label,
                     fontName="Helvetica", fontSize=6.4, fillColor=MUTED,
                     textAnchor="middle"))


def service_box(d: Drawing, x, y, w, h, title, lines, fill):
    d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=fill, strokeColor=BLUE, strokeWidth=1))
    d.add(String(x + 8, y + h - 15, title, fontName="Helvetica-Bold", fontSize=9, fillColor=NAVY))
    for idx, line in enumerate(lines):
        d.add(String(x + 8, y + h - 29 - idx * 11, line,
                     fontName="Helvetica", fontSize=6.7, fillColor=MUTED))


def component_diagram():
    d = Drawing(500, 315)
    d.add(String(250, 300, "GeoInspect logical architecture", fontName="Helvetica-Bold",
                 fontSize=11, fillColor=NAVY, textAnchor="middle"))
    service_box(d, 8, 210, 105, 62, "API client / scripts", ["HTTP + JSON", "X-Correlation-ID"], colors.HexColor("#FFF7DF"))
    service_box(d, 145, 224, 112, 62, "Dispatch service", ["Orchestrated assignment", "PostgreSQL: dispatch_db"], PALE)
    service_box(d, 18, 90, 120, 70, "Work-order service", ["Jobs, GIS coordinates", "MongoDB + GridFS photos"], colors.HexColor("#EDF5FF"))
    service_box(d, 190, 90, 120, 70, "Workforce service", ["Inspectors, capacity", "PostgreSQL: workforce_db"], colors.HexColor("#EDF5FF"))
    service_box(d, 362, 90, 120, 70, "Notification service", ["Failure simulation", "MongoDB: notification_db"], colors.HexColor("#FFF0F2"))
    arrow(d, 113, 241, 145, 253, "REST POST /api/v1/assignments")
    arrow(d, 181, 224, 92, 160, "REST POST claim / confirm")
    arrow(d, 220, 224, 250, 160, "REST POST reservation")
    arrow(d, 257, 242, 422, 160, "REST POST notification")
    arrow(d, 145, 239, 113, 226, "HTTP response", color=GREEN, dy=-12)
    d.add(Rect(5, 18, 490, 45, rx=5, ry=5, fillColor=colors.HexColor("#F8FAFC"), strokeColor=LINE))
    d.add(String(15, 49, "Isolation rule", fontName="Helvetica-Bold", fontSize=8, fillColor=NAVY))
    d.add(String(15, 35, "Each service reads and writes only its own database. Cross-service references are IDs carried through REST APIs.",
                 fontName="Helvetica", fontSize=7, fillColor=INK))
    d.add(String(15, 22, "Deployment-ready seams: independent port, dependency file, .env.example, /health, OpenAPI, and structured logs.",
                 fontName="Helvetica", fontSize=7, fillColor=INK))
    return d


def sequence_diagram():
    d = Drawing(500, 305)
    actors = [(40, "Client"), (150, "Dispatch"), (265, "Work order"), (370, "Workforce"), (470, "Notification")]
    for x, name in actors:
        d.add(Rect(x - 34, 270, 68, 23, rx=4, ry=4, fillColor=PALE, strokeColor=BLUE))
        d.add(String(x, 278, name, fontName="Helvetica-Bold", fontSize=7, fillColor=NAVY, textAnchor="middle"))
        d.add(Line(x, 270, x, 18, strokeColor=LINE, strokeWidth=0.8, strokeDashArray=[3, 3]))
    steps = [
        (40, 150, 246, "1  POST assignment + Idempotency-Key"),
        (150, 265, 220, "2  POST /work-orders/{id}/claim"),
        (265, 150, 198, "3  CLAIMED + job details"),
        (150, 370, 170, "4  POST atomic reservation"),
        (370, 150, 148, "5  201 reservation"),
        (150, 265, 120, "6  POST /work-orders/{id}/confirm"),
        (265, 150, 98, "7  200 ASSIGNED"),
        (150, 470, 70, "8  POST notification (retry-safe)"),
        (470, 150, 48, "9  201 SENT"),
        (150, 40, 24, "10  201 CONFIRMED assignment"),
    ]
    for x1, x2, y, label in steps:
        arrow(d, x1, y, x2, y, label, color=GREEN if x2 < x1 else BLUE, dy=5)
    return d


def failure_diagram():
    d = Drawing(500, 230)
    service_box(d, 20, 142, 120, 58, "Dispatch", ["assignment=CONFIRMED", "notification=PENDING"], PALE)
    service_box(d, 200, 142, 120, 58, "Notification mock", ["timeout / HTTP 503", "same notification key"], colors.HexColor("#FFF0F2"))
    service_box(d, 360, 142, 120, 58, "Recovery endpoint", ["POST retry-notification", "state becomes SENT"], colors.HexColor("#EDF8F1"))
    arrow(d, 140, 172, 200, 172, "HTTP POST + retries")
    arrow(d, 320, 172, 360, 172, "manual retry", color=GREEN)
    d.add(Rect(20, 30, 460, 72, rx=5, ry=5, fillColor=colors.HexColor("#F8FAFC"), strokeColor=LINE))
    d.add(String(32, 84, "Why the assignment remains confirmed", fontName="Helvetica-Bold", fontSize=8.5, fillColor=NAVY))
    d.add(String(32, 66, "Notification is an external side effect after resource reservation and work-order assignment.", fontName="Helvetica", fontSize=7.2, fillColor=INK))
    d.add(String(32, 51, "Rolling back a valid field assignment because SMS/email is unavailable would reduce availability.", fontName="Helvetica", fontSize=7.2, fillColor=INK))
    d.add(String(32, 36, "Persisted PENDING state makes the partial failure visible and repeatable without creating duplicates.", fontName="Helvetica", fontSize=7.2, fillColor=INK))
    return d


def state_diagram():
    d = Drawing(500, 105)
    d.add(String(8, 78, "Work order", fontName="Helvetica-Bold", fontSize=7.5, fillColor=NAVY))
    for x, name in [(100, "OPEN"), (220, "CLAIMED"), (340, "ASSIGNED")]:
        d.add(Rect(x, 68, 86, 24, rx=7, ry=7, fillColor=PALE, strokeColor=BLUE))
        d.add(String(x + 43, 76.5, name, fontName="Helvetica-Bold", fontSize=7, fillColor=NAVY, textAnchor="middle"))
    arrow(d, 186, 80, 220, 80, "claim")
    arrow(d, 306, 80, 340, 80, "confirm")
    d.add(String(8, 29, "Assignment", fontName="Helvetica-Bold", fontSize=7.5, fillColor=NAVY))
    for x, name in [(100, "PENDING"), (220, "CONFIRMED"), (340, "REJECTED")]:
        fill = colors.HexColor("#EDF8F1") if name == "CONFIRMED" else (colors.HexColor("#FFF0F2") if name == "REJECTED" else PALE)
        d.add(Rect(x, 18, 86, 24, rx=7, ry=7, fillColor=fill, strokeColor=BLUE))
        d.add(String(x + 43, 26.5, name, fontName="Helvetica-Bold", fontSize=7, fillColor=NAVY, textAnchor="middle"))
    arrow(d, 186, 30, 220, 30, "success", color=GREEN)
    arrow(d, 186, 21, 340, 21, "definitive rejection", color=RED, dy=-9)
    return d


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename):
        super().__init__(filename, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                         topMargin=18 * mm, bottomMargin=17 * mm,
                         title="GeoInspect - Architecture and Technical Design",
                         author="GeoInspect project team")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=self._decorate))

    @staticmethod
    def _decorate(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 8 * mm, A4[0], 8 * mm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(WHITE)
        canvas.drawString(18 * mm, A4[1] - 5.2 * mm, "GEOINSPECT  |  ARCHITECTURE AND TECHNICAL DESIGN")
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, 12 * mm, A4[0] - 18 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 7.5 * mm, "Technical Design")
        canvas.drawRightString(A4[0] - 18 * mm, 7.5 * mm, f"Page {doc.page}")
        canvas.restoreState()


def mx_cell(cell_id, value="", style="", vertex=False, edge=False, parent="1", source=None, target=None, x=0, y=0, w=120, h=50):
    safe_value = escape(value).replace("\n", "&#xa;")
    attrs = [f'id="{cell_id}"', f'value="{safe_value}"', f'style="{style}"', f'parent="{parent}"']
    if vertex:
        attrs.append('vertex="1"')
    if edge:
        attrs.append('edge="1"')
    if source:
        attrs.append(f'source="{source}"')
    if target:
        attrs.append(f'target="{target}"')
    if edge:
        geom = '<mxGeometry relative="1" as="geometry"/>'
    else:
        geom = f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
    return f'<mxCell {" ".join(attrs)}>{geom}</mxCell>'


def diagram_page(name, cells, page_id):
    body = '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells)
    model = f'<mxGraphModel dx="1422" dy="794" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" pageHeight="827" math="0" shadow="0"><root>{body}</root></mxGraphModel>'
    return f'<diagram id="{page_id}" name="{escape(name)}">{model}</diagram>'


def build_drawio():
    box = "rounded=1;whiteSpace=wrap;html=1;fillColor=#EAF5F5;strokeColor=#176B87;fontColor=#0B1F33;fontStyle=1;"
    db = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;fillColor=#F8FAFC;strokeColor=#526275;fontColor=#0B1F33;"
    client = "rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF7DF;strokeColor=#F4B942;fontColor=#0B1F33;fontStyle=1;"
    edge = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;endFill=1;strokeColor=#176B87;fontColor=#526275;labelBackgroundColor=#FFFFFF;"
    dashed = edge + "dashed=1;strokeColor=#C83A4A;"

    c1 = [
        mx_cell("c", "API client / scripts", client, True, x=30, y=60, w=150, h=60),
        mx_cell("d", "Dispatch service :8003\nOrchestration + idempotency", box, True, x=260, y=60, w=190, h=70),
        mx_cell("w", "Work-order service :8001\nGIS jobs + GridFS photos", box, True, x=70, y=260, w=190, h=70),
        mx_cell("f", "Workforce service :8002\nInspectors + atomic slots", box, True, x=330, y=260, w=190, h=70),
        mx_cell("n", "Notification service :8004\nFailure simulation + dedupe", box, True, x=590, y=260, w=190, h=70),
        mx_cell("mdb1", "MongoDB\nworkorder_db + GridFS", db, True, x=85, y=430, w=160, h=80),
        mx_cell("pg1", "PostgreSQL\nworkforce_db", db, True, x=345, y=430, w=160, h=80),
        mx_cell("mdb2", "MongoDB\nnotification_db", db, True, x=605, y=430, w=160, h=80),
        mx_cell("pg2", "PostgreSQL\ndispatch_db", db, True, x=275, y=590, w=160, h=80),
        mx_cell("e1", "REST/HTTP POST /api/v1/assignments\nJSON + Idempotency-Key + X-Correlation-ID", edge, edge=True, source="c", target="d"),
        mx_cell("e2", "REST/HTTP work-order API", edge, edge=True, source="d", target="w"),
        mx_cell("e3", "REST/HTTP reservation API", edge, edge=True, source="d", target="f"),
        mx_cell("e4", "REST/HTTP notification API", edge, edge=True, source="d", target="n"),
        mx_cell("e5", "MongoDB wire protocol", edge, edge=True, source="w", target="mdb1"),
        mx_cell("e6", "PostgreSQL wire protocol", edge, edge=True, source="f", target="pg1"),
        mx_cell("e7", "MongoDB wire protocol", edge, edge=True, source="n", target="mdb2"),
        mx_cell("e8", "PostgreSQL wire protocol", edge, edge=True, source="d", target="pg2"),
    ]

    # Sequence uses participant boxes and message edges with explicit protocol labels.
    c2 = []
    participants = [("scl", "Client", 20), ("sdi", "Dispatch", 210), ("swo", "Work order", 400), ("swf", "Workforce", 590), ("sno", "Notification", 780)]
    for cid, label, x in participants:
        c2.append(mx_cell(cid, label, box, True, x=x, y=30, w=120, h=40))
        c2.append(mx_cell(cid + "l", "", "shape=line;html=1;strokeColor=#CBD5E1;dashed=1;", True, x=x + 59, y=70, w=1, h=610))
    msgs = [
        ("m1", "scl", "sdi", "1 REST/HTTP POST assignment", 100),
        ("m2", "sdi", "swo", "2 REST/HTTP POST claim", 165),
        ("m3", "swo", "sdi", "3 HTTP 200 CLAIMED + job details", 230),
        ("m4", "sdi", "swf", "4 REST/HTTP POST reservation", 295),
        ("m5", "swf", "sdi", "5 HTTP 201 reservation", 360),
        ("m6", "sdi", "swo", "6 REST/HTTP POST confirm -> ASSIGNED", 425),
        ("m7", "sdi", "sno", "7 REST/HTTP POST notification", 490),
        ("m8", "sno", "sdi", "8 HTTP 201 SENT", 555),
        ("m9", "sdi", "scl", "9 HTTP 201 CONFIRMED", 620),
    ]
    for mid, src, dst, label, y in msgs:
        # Invisible waypoints keep each message at a readable vertical level.
        wp1, wp2 = mid + "a", mid + "b"
        sx = dict((i[0], i[2]) for i in participants)[src] + 60
        tx = dict((i[0], i[2]) for i in participants)[dst] + 60
        c2 += [mx_cell(wp1, "", "opacity=0;", True, x=sx, y=y, w=1, h=1),
               mx_cell(wp2, "", "opacity=0;", True, x=tx, y=y, w=1, h=1),
               mx_cell(mid, label, edge, edge=True, source=wp1, target=wp2)]

    c3 = [
        mx_cell("fd", "Dispatch\nassignment=CONFIRMED\nnotification=PENDING", box, True, x=60, y=100, w=200, h=90),
        mx_cell("fn", "Notification mock\nFAIL / SLOW / COMMIT_THEN_SLOW", "rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF0F2;strokeColor=#C83A4A;fontColor=#0B1F33;fontStyle=1;", True, x=390, y=100, w=230, h=90),
        mx_cell("fr", "Retry notification endpoint\nstate becomes SENT", "rounded=1;whiteSpace=wrap;html=1;fillColor=#EDF8F1;strokeColor=#17865A;fontColor=#0B1F33;fontStyle=1;", True, x=720, y=100, w=200, h=90),
        mx_cell("fe1", "REST/HTTP POST\ntimeout + exponential backoff + jitter\nstable logical key", dashed, edge=True, source="fd", target="fn"),
        mx_cell("fe2", "REST/HTTP POST retry\nprovider recovers", edge, edge=True, source="fd", target="fr"),
        mx_cell("note", "Policy: notification failure does not invalidate a correct field assignment. Persist PENDING and retry safely.", "shape=note;whiteSpace=wrap;html=1;fillColor=#FFF7DF;strokeColor=#F4B942;fontColor=#0B1F33;", True, x=250, y=320, w=480, h=100),
    ]

    c4 = [
        mx_cell("ow", "WORK-ORDER OWNERSHIP\nwork_orders\n_id, asset_id, longitude, latitude, required_skill, slot, state\n\ninspection_photos GridFS\nphoto_id, work_order_id, metadata", box, True, x=40, y=60, w=250, h=210),
        mx_cell("of", "WORKFORCE OWNERSHIP\ninspectors\nreservations\n\nUNIQUE(inspector_id, slot)\nwork_order_id is an external reference", box, True, x=340, y=60, w=250, h=210),
        mx_cell("od", "DISPATCH OWNERSHIP\nassignments\nidempotency\n\nUNIQUE(Idempotency-Key)\nfingerprint + stored response", box, True, x=640, y=60, w=250, h=210),
        mx_cell("on", "NOTIFICATION OWNERSHIP\nnotifications\nlogical_key, assignment_id, status, attempts\n\nUNIQUE(logical_key)", box, True, x=340, y=390, w=250, h=180),
        mx_cell("oe1", "REST/HTTP IDs only\nno cross-DB FK or join", edge, edge=True, source="od", target="ow"),
        mx_cell("oe2", "REST/HTTP IDs only\nno cross-DB FK or join", edge, edge=True, source="od", target="of"),
        mx_cell("oe3", "REST/HTTP IDs only\nno cross-DB FK or join", edge, edge=True, source="od", target="on"),
    ]

    xml = '<?xml version="1.0" encoding="UTF-8"?>' \
          '<mxfile host="app.diagrams.net" modified="2026-10-13T00:00:00.000Z" agent="Codex" version="24.7.17" type="device">' \
          + diagram_page("01 Component Architecture", c1, "component") \
          + diagram_page("02 Main Assignment Sequence", c2, "sequence") \
          + diagram_page("03 Notification Failure and Recovery", c3, "failure") \
          + diagram_page("04 Data Ownership", c4, "ownership") \
          + '</mxfile>'
    DRAWIO_PATH.write_text(xml, encoding="utf-8")


def main():
    from generate_submission_package import main as package_main

    package_main()


if __name__ == "__main__":
    main()
