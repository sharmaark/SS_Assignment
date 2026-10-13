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
                         title="GeoInspect - Microservices Design and Development",
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
        canvas.drawString(18 * mm, A4[1] - 5.2 * mm, "GEOINSPECT  |  SCALABLE SERVICES (SEZG583)")
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, 12 * mm, A4[0] - 18 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 7.5 * mm, "Design and Technical Report")
        canvas.drawRightString(A4[0] - 18 * mm, 7.5 * mm, f"Page {doc.page}")
        canvas.restoreState()


def build_pdf():
    story = []

    # Page 1 - cover and rubric map
    story += [Spacer(1, 15 * mm), p("GeoInspect", TITLE),
              p("GIS-enabled field inspection assignment platform", SUBTITLE),
              band("A four-service application that prevents double-booking of field inspectors, makes assignment creation idempotent, and remains usable when notifications fail."),
              Spacer(1, 6 * mm)]
    cover_meta = [
        ["Course", "Scalable Services (SEZG583)"],
        ["Assignment", "Assignment 1 - Design and Development of a Microservices Application"],
        ["Repository", "https://github.com/sharmaark/SS_Assignment"],
        ["Team", "[Add student names and IDs before submission]"],
        ["Prepared", date.today().isoformat()],
    ]
    story += [tbl(cover_meta, [35 * mm, 139 * mm], header=False, font_size=8), Spacer(1, 7 * mm), p("Rubric traceability", H2)]
    rubric = [
        ["Criterion", "Marks", "What the evaluator can verify", "Report location"],
        ["Problem and decomposition", "2", "Meaningful GIS field-inspection problem; capability boundaries; clear ownership; rejected alternatives", "Pages 2-3"],
        ["Architecture and API design", "2", "Protocol-labelled diagrams, communication choice, OpenAPI, error contract, explicit states", "Pages 4-8"],
        ["Implementation quality", "3", "Runnable services, rules, validation, environment config, tests, repository hygiene", "Pages 2, 8, 11"],
        ["Engineering challenges", "3", "Concurrency, concurrent idempotency, and resilience with repeatable scripts and limits", "Pages 9-10 and 6"],
        ["Report, video and evidence", "3", "Claim-to-file mapping, editable diagrams, live-demo plan, submission links", "Pages 11-12"],
    ]
    story += [tbl(rubric, [41 * mm, 13 * mm, 82 * mm, 38 * mm], font_size=6.8), Spacer(1, 5 * mm),
              p("Submission note", H2),
              p("The report describes the code and evidence currently present in the repository. Team details, individual reflections, and the final Google Drive/video link are deliberately left as labelled fields because they require student-owned information.", SMALL), PageBreak()]

    # Page 2
    story += [p("1. Problem, scope and business rules", H1),
              p("Municipal and utility organisations create field work orders at geographic locations and assign inspectors for a time slot. The scarce resource is an inspector's availability. Two coordinators can request the same inspector and slot concurrently; a naive availability check can approve both. Retried client requests can also create duplicate assignments, while notification providers may respond slowly, fail, or commit a message before the HTTP response is lost.", BODY),
              band("Design objective: complete a traceable three-service assignment transaction while preserving inspector capacity and making retries safe. Notification is the deliberately unreliable fourth service."),
              p("Business rules and traceability", H2)]
    brs = [
        ["Rule", "Enforced behavior", "Code location", "Unit test"],
        ["BR1", "The inspector's rectangular service area must cover the inspection point; boundaries count as covered.", "services/workforce/src/business.py", "services/workforce/tests/test_business.py"],
        ["BR2", "The inspector must have the work order's required skill.", "services/workforce/src/business.py", "services/workforce/tests/test_business.py"],
        ["BR3", "An inspector may hold only one reservation for a time slot.", "services/workforce/src/business.py + DB UNIQUE constraint", "services/workforce/tests/test_business.py"],
        ["BR4", "Only the assignment that owns a work-order claim may confirm it.", "services/work_order/src/business.py", "services/work_order/tests/test_business.py"],
        ["BR5", "Reusing an Idempotency-Key with a different payload is rejected with HTTP 409.", "services/dispatch/src/business.py", "services/dispatch/tests/test_business.py"],
        ["BR6", "JPEG/PNG photos within the size limit may be attached only after assignment.", "services/work_order/src/business.py", "services/work_order/tests/test_business.py"],
    ]
    story += [tbl(brs, [12 * mm, 62 * mm, 54 * mm, 46 * mm], font_size=6.55),
              p("Scope assumptions", H2),
              bullet("Dispatch is the workflow orchestrator. Calls use REST over HTTP and JSON; every service owns its persistence."),
              bullet("A work order stores a point location and optional inspection photos. MongoDB GridFS stores photo bytes and metadata; files are not embedded in API payloads."),
              bullet("The demo uses a single slot string as the contention key. Production scheduling could use intervals and geospatial travel constraints."),
              p("Out of scope", H2),
              p("Authentication, UI, route optimisation, offline mobile synchronisation, real SMS/email, and full image-processing pipelines are excluded by design. This keeps the one-week implementation focused on the assignment's distributed-system requirements.", BODY), PageBreak()]

    # Page 3
    story += [p("2. Service decomposition and ownership", H1),
              p("The boundaries follow business capabilities that can change independently. Each service can be explained in one sentence and has its own dependency file, environment template, API layer, business layer, data layer, database, health endpoint, logs, and OpenAPI document.", BODY)]
    services = [
        ["Service", "Responsibility", "Owns", "Why this boundary"],
        ["Work-order :8001", "Create field jobs, validate GIS points, control job state, store photos", "MongoDB work orders; GridFS files", "Location/photo lifecycle differs from staff scheduling and uses document/file storage."],
        ["Workforce :8002", "Register inspectors and reserve a slot atomically", "PostgreSQL inspectors and reservations", "Capacity is a consistency boundary that benefits from a relational UNIQUE constraint."],
        ["Dispatch :8003", "Orchestrate assignment and store idempotent outcomes", "PostgreSQL assignments and idempotency records", "Workflow state and replay semantics belong together; it does not own inspectors or work orders."],
        ["Notification :8004", "Simulate slow/failing provider and deduplicate notifications", "MongoDB notification attempts/results", "External failure behavior can evolve independently and is isolated from the core transaction."],
    ]
    story += [tbl(services, [29 * mm, 52 * mm, 41 * mm, 52 * mm], font_size=6.8),
              p("Database-per-service ownership", H2)]
    ownership = [
        ["Data", "Authoritative service", "Referenced elsewhere as"],
        ["Work order and GIS point", "Work-order", "work_order_id"],
        ["Photo file and metadata", "Work-order / GridFS", "photo_id"],
        ["Inspector", "Workforce", "inspector_id"],
        ["Slot reservation", "Workforce", "reservation_id"],
        ["Assignment + replay response", "Dispatch", "assignment_id / Idempotency-Key"],
        ["Notification", "Notification", "notification_id and logical key"],
    ]
    story += [tbl(ownership, [52 * mm, 55 * mm, 67 * mm], font_size=7),
              p("Alternatives rejected", H2),
              bullet("One shared database would simplify joins, but would violate independent ownership and allow services to bypass APIs."),
              bullet("A service per table would create CRUD wrappers with chatty coupling. Work orders and photos stay together because they share one lifecycle."),
              bullet("A long A-to-B-to-C-to-D chain was avoided. Dispatch calls the three capability services directly, making state and failure handling explicit."),
              bullet("Kafka/RabbitMQ was deferred because Assignment 2 would require another container and Challenge 3A can demonstrate partial failure with less infrastructure."), PageBreak()]

    # Page 4
    story += [p("3. Architecture", H1),
              p("The client sends one assignment command to Dispatch. Dispatch claims the work order, reserves capacity in Workforce, confirms the work-order assignment, and requests a notification. All calls carry the correlation ID so one flow can be reconstructed from structured logs.", BODY),
              component_diagram(),
              p("Communication choice", H2),
              p("REST is used because the assignment explicitly requires HTTP APIs and because the workflow needs immediate conflict feedback. Dispatch is an orchestrator rather than a pass-through controller: it owns assignment state, idempotency, retry policy, and the visible partial-failure outcome. Database drivers communicate only with the database owned by the calling service.", BODY),
              p("Editable source", H2),
              p("The matching component, sequence, failure, and data-ownership diagrams are provided in <b>docs/GeoInspect_Architecture.drawio</b>. Arrows name both direction and protocol for assessment and later Assignment 2 deployment planning.", BODY), PageBreak()]

    # Page 5
    story += [p("3.1 Main transaction and state model", H1),
              p("Happy path: validate the request, load the work order, reserve the inspector/slot atomically, mark the work order assigned, notify the inspector, persist the complete response, and return HTTP 201. A repeated command with the same key returns the persisted response.", BODY),
              sequence_diagram(),
              p("Explicit workflow states", H2), state_diagram(),
              p("Integrity across services", H2),
              p("There is no distributed database transaction. The design instead gives the contended reservation a strong local invariant, records the dispatch workflow state, and makes every repeated side effect idempotent. If reservation conflicts, the work order is not modified. If notification fails after the assignment is valid, the core state remains confirmed and the notification state exposes the repair action.", BODY), PageBreak()]

    # Page 6
    story += [p("3.2 Failure path / 6.3 Challenge 3A resilience", H1),
              p("Notification is the simulated slow or failing dependency. Dispatch applies a configured timeout, bounded retries, exponential backoff, and jitter. The request uses a stable logical notification key, so a provider that commits before its response is lost still produces one notification record.", BODY),
              failure_diagram(),
              p("Design choice and observed behavior", H2)]
    resilience = [
        ["Forced condition", "Expected behavior", "Recorded result"],
        ["Provider returns failure", "Retries end; assignment remains CONFIRMED; notification becomes PENDING", "evidence/challenge-3a-resilience/output.txt"],
        ["Provider recovers", "Retry endpoint sends the pending notification and marks it SENT", "Same evidence file"],
        ["Provider commits then delays response", "Dispatch retries with the same key; provider returns the existing result", "Exactly one SENT notification record"],
    ]
    story += [tbl(resilience, [48 * mm, 78 * mm, 48 * mm], font_size=7),
              p("Why this failure policy", H2),
              p("Field work should proceed when only messaging is unavailable. Persisting PENDING is a graceful, inspectable degradation and avoids undoing a valid scarce-resource reservation. The retry endpoint makes recovery demonstrable without a background worker.", BODY),
              p("Limitations", H2),
              p("Retries run in the request path and the circuit breaker is intentionally omitted. A production version would use an outbox plus worker and automatic retry scheduling, while retaining the same notification idempotency key.", BODY), PageBreak()]

    # Page 7
    story += [p("4. Data design, GIS data and photos", H1),
              p("Each service has an independent schema and credentials. Cross-service IDs are ordinary values, not foreign keys. This prevents accidental cross-database joins and keeps each service deployable on its own.", BODY)]
    data = [
        ["Service", "Entity / key fields", "Invariant or index"],
        ["Work-order (MongoDB)", "work_orders: _id, asset_id, longitude, latitude, required_skill, slot, state, assignment_id", "Coordinate/time validation; OPEN -> CLAIMED -> ASSIGNED"],
        ["Work-order GridFS", "inspection_photos.files/chunks: photo_id, work_order_id, filename, content_type", "Photo metadata points to work_order_id inside same service"],
        ["Workforce (PostgreSQL)", "inspectors; reservations(id, inspector_id, slot, work_order_id)", "UNIQUE(inspector_id, slot) prevents over-allocation"],
        ["Dispatch (PostgreSQL)", "assignments; idempotency(key, fingerprint, status, response)", "UNIQUE(key); fingerprint detects conflicting reuse"],
        ["Notification (MongoDB)", "notifications: logical_key, assignment_id, status, attempts", "Unique logical_key deduplicates provider retries"],
    ]
    story += [tbl(data, [42 * mm, 85 * mm, 47 * mm], font_size=6.9),
              p("Why MongoDB for inspection photos", H2),
              p("MongoDB fits flexible work-order attributes and GridFS provides streamed file storage with metadata and chunking. The REST API accepts multipart uploads and returns photo identifiers. The database choice does not mean every service shares MongoDB: the consistency-sensitive reservation and dispatch records remain in separate PostgreSQL databases.", BODY),
              p("GIS scope", H2),
              p("The application stores WGS84 latitude/longitude and validates coordinate ranges. This is enough to make inspection orders map-ready without adding a UI or spatial server. Future versions could add a GeoJSON point with a 2dsphere index for proximity queries and PostGIS for route planning; those are outside the one-week scope.", BODY),
              p("Sample work order", H2),
              p('{"asset_id":"VALVE-101","longitude":77.5946,"latitude":12.9716,"required_skill":"valve","slot":"2026-10-15T09:00:00Z"}', CODE),
              p("Backup and lifecycle note", H2),
              p("Deleting or archiving a work order should apply a same-service policy to its GridFS files. The current assignment does not implement retention or virus scanning; both belong in production hardening.", BODY), PageBreak()]

    # Page 8
    story += [p("5. API design", H1),
              p("All business endpoints are versioned under /api/v1. Every service also exposes GET /health and FastAPI-generated /docs and /openapi.json. Input models perform validation, domain exceptions map to meaningful status codes, and correlation IDs are accepted or generated and forwarded downstream.", BODY)]
    endpoints = [
        ["Service", "Method and path", "Purpose / principal responses"],
        ["Work-order", "POST /api/v1/work-orders", "Create job: 201; validation: 422"],
        ["Work-order", "POST /api/v1/work-orders/{id}/claim | /confirm | /release-claim", "Idempotent participant operations: 200 / 404 / 409"],
        ["Work-order", "POST /api/v1/work-orders/{id}/photos", "Stream photo to GridFS: 201 / 404"],
        ["Workforce", "POST /api/v1/inspectors", "Register inspector: 201 / conflict"],
        ["Workforce", "POST /api/v1/reservations", "Atomic slot reservation: 201 / 409"],
        ["Dispatch", "POST /api/v1/assignments", "Main transaction; Idempotency-Key required: 201 / 409 / 422"],
        ["Dispatch", "POST /api/v1/assignments/{id}/retry-notification", "Recover PENDING notification: 200"],
        ["Notification", "POST /api/v1/notifications", "Idempotent mock send: 201 / 503 / timeout simulation"],
        ["Notification", "PUT /api/v1/mock-mode", "Set normal, fail, slow, or commit-then-slow demo mode"],
    ]
    story += [tbl(endpoints, [31 * mm, 78 * mm, 65 * mm], font_size=6.85),
              p("Consistent error model", H2),
              p('{"error":{"code":"SLOT_ALREADY_RESERVED","message":"Inspector is already reserved for this slot","details":{}},"correlation_id":"..."}', CODE),
              p("OpenAPI files", H2),
              p("Committed specifications are in docs/openapi/work-order.json, docs/openapi/workforce.json, docs/openapi/dispatch.json, and docs/openapi/notification.json. Swagger UI is available on ports 8001-8004 at /docs while services are running.", BODY),
              p("Configuration and operability", H2),
              p("Ports, database URLs, downstream service URLs, photo-size limit, timeouts, retry counts, and retry timing come from environment variables documented in each .env.example. Structured logs include correlation_id, service, event, and relevant entity IDs.", BODY), PageBreak()]

    # Page 9
    story += [p("6.1 Engineering challenge 1 - concurrency control", H1),
              band("Pass condition demonstrated: 20 parallel reservation attempts compete for capacity N=1; exactly one succeeds, 19 receive a meaningful conflict, and one reservation remains in PostgreSQL."),
              p("Problem", H2),
              p("Two requests can both observe an inspector as free before either writes a reservation. A check in Python followed by INSERT is therefore a time-of-check/time-of-use race and can over-allocate the inspector.", BODY),
              p("Design", H2),
              p("Workforce defines a database UNIQUE constraint on (inspector_id, slot). Every request attempts the INSERT. PostgreSQL serialises conflicting index writes; one transaction commits and the others raise an integrity conflict that the API maps to HTTP 409. Correctness therefore holds across processes and service replicas, not only within one Python process.", BODY),
              p("Repeatable evidence", H2)]
    concurrency = [
        ["Artifact", "Claim"],
        ["scripts/challenge_1_concurrency.py", "Fires 20 assignment requests concurrently and queries the resulting reservation state"],
        ["evidence/challenge-1-concurrency/output.txt", "Shows success_count=1, conflict_count=19, reservation_count=1"],
        ["services/workforce/src/data.py", "Defines persistence path and handles uniqueness conflict"],
        ["services/workforce/tests/test_business.py", "Covers the business rejection contract"],
    ]
    story += [tbl(concurrency, [72 * mm, 102 * mm], font_size=7.2),
              p("Why plain check-then-update fails", H2),
              p("Request A reads zero reservations. Before it inserts, request B also reads zero. Both then insert. Application-level checks do not lock a shared resource and each process has independent memory. The database constraint moves the invariant to the only component that sees all concurrent writes.", BODY),
              p("Limitations", H2),
              p("The key models exact slot equality. Overlapping time intervals would require an exclusion constraint, interval bucketing, or serialisable transaction logic. The demo intentionally uses the smallest rule that proves the required contention behavior.", BODY), PageBreak()]

    # Page 10
    story += [p("6.2 Engineering challenge 2 - idempotency", H1),
              band("Pass condition demonstrated: concurrent identical requests with one key return the same assignment and create one effect; the same key with a changed payload returns HTTP 409."),
              p("Algorithm", H2)]
    algo = [
        ["Step", "Operation"],
        ["1", "Canonicalise the request payload and compute a SHA-256 fingerprint."],
        ["2", "Insert an idempotency row keyed by Idempotency-Key before performing unsafe effects."],
        ["3", "If the key exists, compare fingerprints. Different payload: 409. Same payload: wait/read stored outcome."],
        ["4", "Persist status and the complete HTTP response so later repeats return the same result."],
        ["5", "Use stable downstream identifiers so notification retries also deduplicate."],
    ]
    story += [tbl(algo, [16 * mm, 158 * mm], font_size=7.4),
              p("Why a fingerprint is required", H2),
              p("A key alone cannot distinguish a legitimate replay from accidental reuse for another inspector, slot, or work order. Comparing the canonical payload protects the caller from receiving an unrelated stored response.", BODY),
              p("Repeatable evidence", H2)]
    idem = [
        ["Artifact", "Recorded result"],
        ["scripts/challenge_2_idempotency.py", "Sends two same-moment calls, a sequential replay, and a changed-payload call"],
        ["evidence/challenge-2-idempotency/output.txt", "Both concurrent calls: 201 and same assignment_id; replay: same response; changed payload: 409"],
        ["Database state in output", "reservation_count=1 and notification_count=1"],
        ["services/dispatch/src/data.py", "Unique key plus persisted fingerprint/status/response"],
    ]
    story += [tbl(idem, [72 * mm, 102 * mm], font_size=7),
              p("Concurrency behavior", H2),
              p("The first request owns execution. A simultaneous duplicate observes the same in-progress record and resolves to the stored result instead of repeating the workflow. Failed terminal outcomes can also be replayed consistently rather than hiding a previous side effect.", BODY),
              p("Limitations", H2),
              p("The assignment keeps idempotency records indefinitely for demo clarity. Production needs an expiry policy longer than the maximum client retry window, plus metrics for stuck IN_PROGRESS records.", BODY), PageBreak()]

    # Page 11
    story += [p("7. Testing, evidence and implementation quality", H1),
              p("Tests are layered around business invariants, then complemented by executable system scripts. The scripts use public APIs and leave database state available for inspection, which makes the evidence repeatable during the demo.", BODY)]
    tests = [
        ["Level", "Command / artifact", "Result captured"],
        ["Unit tests", "python -m pytest", "18 passed"],
        ["Main flow", "python scripts/end_to_end.py", "Assignment CONFIRMED, notification SENT, GridFS photo uploaded and listed"],
        ["Concurrency", "python scripts/challenge_1_concurrency.py", "1 success, 19 conflicts, one final reservation"],
        ["Idempotency", "python scripts/challenge_2_idempotency.py", "Concurrent replay safe; mismatch rejected; one reservation and notification"],
        ["Resilience", "python scripts/challenge_3a_resilience.py", "Failure visible as PENDING; recovery to SENT; commit-then-slow deduplicated"],
    ]
    story += [tbl(tests, [32 * mm, 73 * mm, 69 * mm], font_size=7.1),
              p("Fresh-clone run path", H2),
              p("1. Create a virtual environment. 2. Install requirements-dev.txt. 3. Start PostgreSQL and MongoDB with docker compose up -d. 4. Start services with python scripts/run_all.py. 5. Run the scripts above from a second terminal. README.md lists ports, environment variables, Swagger URLs, troubleshooting, and cleanup.", BODY),
              p("Evidence index", H2)]
    evidence = [
        ["Folder", "Evidence purpose"],
        ["evidence/challenge-1-concurrency", "Parallel command output and explanation of database-enforced capacity"],
        ["evidence/challenge-2-idempotency", "First/replay/concurrent/mismatched results and single-effect database state"],
        ["evidence/challenge-3a-resilience", "Failure, retry recovery, and response-loss deduplication"],
        ["evidence/tests", "Unit and end-to-end output"],
    ]
    story += [tbl(evidence, [68 * mm, 106 * mm], font_size=7.1),
              p("Repository hygiene", H2),
              p("Generated caches, local virtual environments, secrets, and database volumes are ignored. Each service has isolated dependencies and an environment example. The code separates API, business, and data access layers, keeping rule logic testable and persistence details replaceable.", BODY),
              p("Evidence caveat", H2),
              p("Before final submission, rerun scripts on the final commit and capture timestamped terminal screenshots in the corresponding evidence folders. Raw text outputs are already committed and should remain the primary auditable evidence.", BODY), PageBreak()]

    # Page 12
    story += [p("8. Decisions, limitations and submission appendix", H1), p("Key design decisions", H2)]
    decisions = [
        ["Decision", "Options considered", "Rationale and trade-off"],
        ["Orchestrated REST workflow", "Orchestration vs choreography", "Easier to explain, trace, and return conflicts in one week. Dispatch carries coupling and must manage partial failure."],
        ["DB-enforced uniqueness", "In-process lock, optimistic version, UNIQUE constraint", "A UNIQUE key works across replicas and is directly demonstrable. Exact slots are less flexible than interval scheduling."],
        ["MongoDB GridFS for photos", "Filesystem, object storage, byte arrays", "Keeps photo metadata/streaming within work-order ownership and runs locally. Cloud object storage would scale better."],
        ["Notification failure is recoverable", "Rollback assignment vs keep assignment", "Messaging is secondary to a valid field assignment. PENDING state preserves work and makes repair explicit."],
        ["Challenge 3A", "Time holds, saga, broker, resilience", "Meets partial-failure objective with the least extra infrastructure and prepares HTTP boundaries for containerisation."],
    ]
    story += [tbl(decisions, [44 * mm, 49 * mm, 81 * mm], font_size=6.8),
              p("Known limitations and future work", H2),
              bullet("No authentication or authorisation; add service identities and role-based access after the assignment."),
              bullet("No automatic outbox worker; add one for durable background notification retries."),
              bullet("No geospatial search, routing, or offline sync; add GeoJSON indexes and a mobile client when product scope requires them."),
              bullet("No automatic idempotency retention; define expiry and monitoring before production use."),
              p("Submission links and individual appendix", H2)]
    submission = [
        ["Item", "Value to complete"],
        ["GitHub repository", "https://github.com/sharmaark/SS_Assignment"],
        ["Google Drive / demo video", "[Insert final shareable link]"],
        ["Team contributions", "[Add one row per student: service/challenge/report/demo responsibility and commit evidence]"],
        ["Individual reflections", "[Append one half-page reflection per student]"],
    ]
    story += [tbl(submission, [52 * mm, 122 * mm], font_size=7.2),
              p("AI-use declaration", H2),
              p("AI tools were used to assist with project planning, boilerplate, documentation structure, test-script drafting, and review. The team remains responsible for validating the design, running the code, understanding every submitted component, correcting generated material, and explaining the implementation during the demo.", BODY),
              band("Final review before upload: replace all bracketed fields, rerun evidence on the final commit, confirm the repository is public to faculty, and keep the video within 8-10 minutes.", color=GOLD)]

    ReportDoc(str(PDF_PATH)).build(story)


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
