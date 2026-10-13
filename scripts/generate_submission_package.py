"""Generate the concise GeoInspect report and split diagram package."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
import xml.etree.ElementTree as ET

from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Spacer

import report_components as c


DOCS = c.DOCS
DIAGRAMS = DOCS / "diagrams"
REPORT = DOCS / "GeoInspect_Technical_Design.pdf"


def build_short_report() -> None:
    story = []

    # Page 1 - document overview
    story += [
        Spacer(1, 13 * mm),
        c.p("GeoInspect", c.TITLE),
        c.p("Architecture and Technical Design", c.SUBTITLE),
        c.band(
            "GIS-enabled field inspection assignment with four independently runnable services, "
            "database-per-service, concurrency control, idempotency, and resilient notifications."
        ),
        Spacer(1, 5 * mm),
        c.tbl(
            [
                ["System", "GIS-enabled field inspection platform"],
                ["Repository", "https://github.com/sharmaark/SS_Assignment"],
                ["Document", "Technical design and implementation reference"],
                ["Prepared", date.today().isoformat()],
            ],
            [36 * mm, 138 * mm],
            header=False,
            font_size=8,
        ),
        Spacer(1, 6 * mm),
        c.p("Executive overview", c.H2),
        c.p("GeoInspect coordinates the assignment of field inspections to eligible inspectors. Its design protects scarce inspector availability, preserves one outcome for repeated requests, and makes notification failures visible without invalidating confirmed work. The system uses REST APIs and independently owned PostgreSQL and MongoDB databases.", c.BODY),
        c.p("Document guide", c.H2),
        c.tbl([
            ["Section", "Page"],
            ["1. Domain, scope and service boundaries", "2"],
            ["2. Architecture and communication", "3"],
            ["3. Data ownership and API contracts", "4"],
            ["4. Concurrency and request idempotency", "5"],
            ["5. Resilience and verification", "6"],
            ["6. Design decisions and operational limits", "7"],
        ], [147 * mm, 27 * mm], font_size=8),
        c.p("Supporting technical references", c.H2),
        c.tbl(
            [
                ["File", "Purpose"],
                ["diagrams/01_System_Architecture.pdf + .drawio", "Service boundaries, databases, protocols, and ownership"],
                ["diagrams/02_Main_Assignment_Sequence.pdf + .drawio", "Happy-path transaction across services"],
                ["diagrams/03_Notification_Failure_Sequence.pdf + .drawio", "Timeout, retry, graceful failure, and recovery"],
                ["diagrams/04_Data_Ownership.pdf + .drawio", "Per-service entities and integrity constraints"],
                ["services/* and scripts/*", "Source code, unit tests, startup, end-to-end, and challenge scripts"],
            ],
            [76 * mm, 98 * mm],
            font_size=7.2,
        ),
        PageBreak(),
    ]

    # Page 2 - problem, rules, services
    story += [
        c.p("1. Domain, scope and service boundaries", c.H1),
        c.p(
            "Field coordinators assign geographically distributed inspections to inspectors. "
            "The same inspector and slot can be requested concurrently; retries can create duplicate assignments; "
            "and the notification provider may fail after the operational work has succeeded.",
            c.BODY,
        ),
        c.band(
            "Scope is deliberately API-only: fixed slots, WGS84 points, rectangular service areas, "
            "synthetic data, and a mock notification provider. Authentication, UI, routing, and real SMS/email are excluded."
        ),
        c.p("Business rules", c.H2),
        c.tbl(
            [
                ["Rule", "Enforced behavior", "Code / test"],
                ["BR1", "Inspector service area covers the inspection point; boundaries are included.", "workforce/src/business.py + tests"],
                ["BR2", "Inspector has the required skill.", "workforce/src/business.py + tests"],
                ["BR3", "One inspector reservation per exact time slot.", "workforce/src/data.py UNIQUE + tests"],
                ["BR4", "Only the assignment owning a work-order claim may confirm it.", "work_order/src/business.py + tests"],
                ["BR5", "Same idempotency key with changed payload returns HTTP 409.", "dispatch/src/business.py + tests"],
                ["BR6", "Only assigned jobs accept size-limited JPEG/PNG photos.", "work_order/src/business.py + tests"],
            ],
            [14 * mm, 94 * mm, 66 * mm],
            font_size=7.0,
        ),
        c.p("Service responsibilities", c.H2),
        c.tbl(
            [
                ["Service", "One responsibility", "Owned database"],
                ["Work Order :8001", "Inspection location, skill, state, and GridFS photos", "MongoDB work_order_db"],
                ["Workforce :8002", "Inspector eligibility and atomic slot reservation", "PostgreSQL workforce_db"],
                ["Dispatch :8003", "Assignment orchestration and stored idempotent results", "PostgreSQL dispatch_db"],
                ["Notification :8004", "Failure simulation and deduplicated delivery", "MongoDB notification_db"],
            ],
            [38 * mm, 87 * mm, 49 * mm],
            font_size=7.2,
        ),
        c.p(
            "The boundaries follow business capabilities. Services exchange IDs through REST APIs and never read another service's database. "
            "A shared database and service-per-table split were rejected because both weaken ownership and create a distributed CRUD system.",
            c.BODY,
        ),
        PageBreak(),
    ]

    # Page 3 - architecture
    story += [
        c.p("2. Architecture and communication", c.H1),
        c.p(
            "Dispatch is the workflow orchestrator. It claims the work order, asks Workforce to reserve the inspector and slot, "
            "confirms the work order, and then requests notification. X-Correlation-ID is propagated through every HTTP call.",
            c.BODY,
        ),
        system_architecture_drawing_scaled(),
        c.p("Why this communication design", c.H2),
        c.p(
            "REST provides immediate eligibility and contention feedback. "
            "The client makes one request to Dispatch, while Dispatch calls each capability service directly; there is no long A-to-B-to-C-to-D service chain. "
            "Local database constraints protect strong invariants, while persisted workflow state makes partial failure visible.",
            c.BODY,
        ),
        c.p("Detailed views", c.H2),
        c.p(
            "Open diagrams/01_System_Architecture for the component view, diagrams/02_Main_Assignment_Sequence for the happy path, "
            "and diagrams/03_Notification_Failure_Sequence for the failure path. Each is supplied as a presentation-ready PDF and editable draw.io file.",
            c.BODY,
        ),
        PageBreak(),
    ]

    # Page 4 - data and APIs
    story += [
        c.p("3. Data ownership and API contracts", c.H1),
        c.p("Data ownership", c.H2),
        c.tbl(
            [
                ["Service", "Core records", "Integrity rule"],
                ["Work Order", "work_orders; inspection_photos GridFS bucket", "OPEN -> CLAIMED -> ASSIGNED; claim owner controls confirmation"],
                ["Workforce", "inspectors; reservations", "UNIQUE(inspector_id, slot); UNIQUE(assignment_id)"],
                ["Dispatch", "assignments; idempotency_records", "Primary key on Idempotency-Key; SHA-256 request fingerprint"],
                ["Notification", "notifications", "Unique delivery_key keeps retry effects singular"],
            ],
            [35 * mm, 66 * mm, 73 * mm],
            font_size=7.1,
        ),
        c.p(
            "MongoDB GridFS stores photo bytes in chunks and metadata inside Work Order ownership. PostgreSQL is used where relational uniqueness protects "
            "reservation and idempotency invariants. Foreign IDs are values only; there are no cross-service foreign keys or joins.",
            c.BODY,
        ),
        c.p("API summary", c.H2),
        c.tbl(
            [
                ["Service", "Important versioned endpoints", "Responses"],
                ["Work Order", "POST /api/v1/work-orders; POST /{id}/claim|confirm|release-claim; POST /{id}/photos", "201, 200, 404, 409, 422"],
                ["Workforce", "POST /api/v1/inspectors; POST /api/v1/reservations", "201, 409, 422"],
                ["Dispatch", "POST /api/v1/assignments; POST /{id}/retry-notification", "201, 202, 409, 422, 503"],
                ["Notification", "POST /api/v1/notifications; PUT /api/v1/mock-mode", "201, 200 replay, 202, 503"],
            ],
            [34 * mm, 94 * mm, 46 * mm],
            font_size=6.9,
        ),
        c.p("Error model", c.H2),
        c.p(
            '{"error":{"code":"SLOT_UNAVAILABLE","message":"Inspector is already reserved for this slot","details":{}},"correlation_id":"..."}',
            c.CODE,
        ),
        c.p(
            "Every service exposes GET /health, Swagger UI at /docs, generated /openapi.json, environment-based configuration, and structured correlation-aware logs. "
            "Committed specifications are under docs/openapi/.",
            c.BODY,
        ),
        PageBreak(),
    ]

    # Page 5 - concurrency and idempotency
    story += [
        c.p("4. Concurrency and request idempotency", c.H1),
        c.p("Concurrency control", c.H2),
        c.band(
            "Recorded result: 20 parallel assignment requests compete for capacity N=1. Exactly 1 succeeds, 19 return HTTP 409, and PostgreSQL contains one reservation."
        ),
        c.p(
            "Workforce attempts the reservation INSERT directly. PostgreSQL's UNIQUE(inspector_id, slot) constraint selects one winner across processes and replicas; "
            "integrity errors become SLOT_UNAVAILABLE. A Python check followed by INSERT would race because two requests can both read zero rows before either writes.",
            c.BODY,
        ),
        c.tbl(
            [
                ["Evidence", "Claim"],
                ["scripts/challenge_1_concurrency.py", "Creates 20 eligible assignments concurrently"],
                ["evidence/challenge-1-concurrency/output.txt", "successes=1; conflicts=19; final_reservations=1"],
            ],
            [78 * mm, 96 * mm],
            font_size=7.2,
        ),
        c.p("Request idempotency", c.H2),
        c.band(
            "Recorded result: two simultaneous identical calls and a sequential replay return HTTP 201 with the same assignment ID; changed payload with the same key returns HTTP 409."
        ),
        c.p(
            "Dispatch stores Idempotency-Key, canonical SHA-256 fingerprint, assignment ID, status code, and response body. The unique key selects one owner; a concurrent duplicate "
            "waits for and replays the stored result. A changed fingerprint is rejected. Stable downstream assignment and delivery keys prevent duplicate reservation and notification effects.",
            c.BODY,
        ),
        c.tbl(
            [
                ["Evidence", "Claim"],
                ["scripts/challenge_2_idempotency.py", "Concurrent, sequential, and mismatched-payload cases"],
                ["evidence/challenge-2-idempotency/output.txt", "One assignment result, one reservation, one notification"],
            ],
            [78 * mm, 96 * mm],
            font_size=7.2,
        ),
        PageBreak(),
    ]

    # Page 6 - resilience and tests
    story += [
        c.p("5. Resilience and verification", c.H1),
        c.p("Notification resilience", c.H2),
        c.p(
            "Dispatch uses a configured timeout, three total attempts, exponential backoff, and jitter. A failed provider leaves a valid assignment CONFIRMED with notification PENDING. "
            "After recovery, POST /api/v1/assignments/{id}/retry-notification changes it to SENT. In commit-then-slow mode, the provider commits before the HTTP response is lost; "
            "the same delivery key makes the retry return the existing notification instead of sending twice.",
            c.BODY,
        ),
        c.tbl(
            [
                ["Forced condition", "Observed state", "Evidence"],
                ["Provider fails", "Assignment CONFIRMED; notification PENDING", "challenge-3a-resilience/output.txt"],
                ["Provider recovers", "Manual retry returns notification SENT", "same output"],
                ["Commit then response timeout", "Notification SENT; exactly one notification record", "same output"],
            ],
            [45 * mm, 76 * mm, 53 * mm],
            font_size=7.2,
        ),
        c.p("Testing results", c.H2),
        c.tbl(
            [
                ["Level", "Command", "Recorded result"],
                ["Unit", "python -m pytest", "18 passed"],
                ["End to end", "python scripts/end_to_end.py", "CONFIRMED, SENT, GridFS photo uploaded/listed"],
                ["Concurrency", "python scripts/challenge_1_concurrency.py", "1 success, 19 conflicts"],
                ["Idempotency", "python scripts/challenge_2_idempotency.py", "Concurrent replay safe; changed request rejected"],
                ["Resilience", "python scripts/challenge_3a_resilience.py", "Failure, recovery, and response-loss cases pass"],
            ],
            [29 * mm, 70 * mm, 75 * mm],
            font_size=7.0,
        ),
        c.p(
            "Raw outputs are stored under evidence/challenge-1-concurrency, evidence/challenge-2-idempotency, evidence/challenge-3a-resilience, and evidence/tests. "
            "These files capture the observed behavior of the recorded test runs. Repeat the scripts after changes to transaction or persistence logic and preserve the raw outputs alongside their timestamps.",
            c.BODY,
        ),
        PageBreak(),
    ]

    # Page 7 - decisions and final fields
    story += [
        c.p("6. Design decisions and operational limits", c.H1),
        c.p("Key decisions and trade-offs", c.H2),
        c.tbl(
            [
                ["Decision", "Why selected", "Limit"],
                ["REST orchestration", "Immediate conflict feedback and simple tracing", "Dispatch coordinates partial failures"],
                ["Exact fixed slots", "Small, demonstrable contention key", "Does not detect overlapping intervals"],
                ["Database uniqueness", "Correct across concurrent processes and replicas", "Schema encodes the capacity model"],
                ["MongoDB GridFS photos", "Self-contained streaming storage with metadata", "Object storage scales better"],
                ["Keep assignment when notification fails", "Messaging is secondary to valid operational work", "Requires visible PENDING state and retry"],
            ],
            [44 * mm, 79 * mm, 51 * mm],
            font_size=7.0,
        ),
        c.p("Limitations and future work", c.H2),
        c.bullet("Add automatic outbox workers and idempotency-record retention for production."),
        c.bullet("Add GeoJSON/2dsphere or PostGIS only when proximity search and routing enter scope."),
        c.bullet("Add service authentication, role-based access, malware scanning, and object storage before real deployment."),
        c.p("Recovery boundaries", c.H2),
        c.p("Notification recovery is explicit and initiated through the retry API. The current implementation has no background workflow reconciler. An interrupted core transaction can leave an assignment PENDING; a duplicate request waits for a stored outcome and may return HTTP 202. Automatic takeover and full crash recovery are future work.", c.BODY),
        c.p("Engineering tooling", c.H2),
        c.p(
            "OpenAI Codex assisted with planning, implementation scaffolding, test scripts, documentation, and review. Recorded verification results are linked in this document; generated material remains subject to engineering review.",
            c.BODY,
        ),
    ]

    c.ReportDoc(str(REPORT)).build(story)


def system_architecture_drawing_scaled() -> Drawing:
    drawing = system_architecture_drawing()
    factor = 490 / drawing.width
    drawing.scale(factor, factor)
    drawing.width *= factor
    drawing.height *= factor
    return drawing


def data_ownership_drawing() -> Drawing:
    d = Drawing(720, 330)
    boxes = [
        (15, 180, 160, 115, "WORK ORDER", ["MongoDB: work_orders", "GridFS: inspection_photos", "State: OPEN > CLAIMED > ASSIGNED"]),
        (195, 180, 160, 115, "WORKFORCE", ["PostgreSQL: inspectors", "PostgreSQL: reservations", "UNIQUE(inspector_id, slot)"]),
        (375, 180, 160, 115, "DISPATCH", ["PostgreSQL: assignments", "idempotency_records", "PK key + SHA-256 fingerprint"]),
        (555, 180, 150, 115, "NOTIFICATION", ["MongoDB: notifications", "UNIQUE delivery_key", "attempt/status history"]),
    ]
    for x, y, w, h, title, lines in boxes:
        c.service_box(d, x, y, w, h, title, lines, c.PALE)
    d.add(Rect(95, 30, 530, 75, rx=6, ry=6, fillColor=colors.HexColor("#F8FAFC"), strokeColor=c.LINE))
    d.add(String(360, 80, "Cross-service references", fontName="Helvetica-Bold", fontSize=10, fillColor=c.NAVY, textAnchor="middle"))
    d.add(String(360, 61, "work_order_id | inspector_id | assignment_id | reservation_id | delivery_key", fontName="Helvetica", fontSize=8, fillColor=c.INK, textAnchor="middle"))
    d.add(String(360, 43, "IDs travel through REST/HTTP JSON. No cross-database joins or foreign keys.", fontName="Helvetica-Bold", fontSize=8, fillColor=c.BLUE, textAnchor="middle"))
    for x in [95, 275, 455, 630]:
        d.add(Line(x, 180, x, 105, strokeColor=c.BLUE, strokeWidth=1.3))
        d.add(Polygon([x, 105, x - 4, 111, x + 4, 111], fillColor=c.BLUE, strokeColor=c.BLUE))
    return d


def system_architecture_drawing() -> Drawing:
    """Spacious standalone component view with protocols and owned stores."""
    d = Drawing(720, 400)
    c.service_box(d, 20, 295, 150, 64, "API CLIENT / SCRIPTS", ["JSON request", "Idempotency-Key", "X-Correlation-ID"], colors.HexColor("#FFF7DF"))
    c.service_box(d, 270, 295, 180, 64, "DISPATCH :8003", ["Workflow orchestration", "Stored idempotent result"], c.PALE)
    c.service_box(d, 20, 145, 170, 70, "WORK ORDER :8001", ["GIS job and state", "GridFS inspection photos"], colors.HexColor("#EDF5FF"))
    c.service_box(d, 275, 145, 170, 70, "WORKFORCE :8002", ["Inspector eligibility", "Atomic slot reservation"], colors.HexColor("#EDF5FF"))
    c.service_box(d, 530, 145, 170, 70, "NOTIFICATION :8004", ["Provider failure simulation", "Deduplicated delivery"], colors.HexColor("#FFF0F2"))

    db_style = colors.HexColor("#F8FAFC")
    c.service_box(d, 25, 28, 160, 56, "MongoDB", ["work_order_db", "inspection_photos GridFS"], db_style)
    c.service_box(d, 280, 28, 160, 56, "PostgreSQL", ["workforce_db", "UNIQUE(inspector_id, slot)"], db_style)
    c.service_box(d, 535, 28, 160, 56, "MongoDB", ["notification_db", "UNIQUE delivery_key"], db_style)
    c.service_box(d, 535, 300, 160, 56, "PostgreSQL", ["dispatch_db", "assignments + idempotency"], db_style)

    c.arrow(d, 170, 327, 270, 327, "REST/HTTP POST assignment", dy=8)
    c.arrow(d, 305, 295, 105, 215, "REST/HTTP claim + confirm", dy=10)
    c.arrow(d, 360, 295, 360, 215, "REST/HTTP reserve", dy=6)
    c.arrow(d, 415, 295, 615, 215, "REST/HTTP notify", dy=10)
    c.arrow(d, 450, 327, 535, 327, "PostgreSQL driver", dy=8, color=c.MUTED)
    c.arrow(d, 105, 145, 105, 84, "MongoDB driver", dy=5, color=c.MUTED)
    c.arrow(d, 360, 145, 360, 84, "PostgreSQL driver", dy=5, color=c.MUTED)
    c.arrow(d, 615, 145, 615, 84, "MongoDB driver", dy=5, color=c.MUTED)

    d.add(String(360, 4, "Each service accesses only its owned database. Cross-service references are IDs carried through REST/HTTP JSON.",
                 fontName="Helvetica-Bold", fontSize=7.5, fillColor=c.NAVY, textAnchor="middle"))
    return d


def write_diagram_pdf(path: Path, title: str, subtitle: str, drawing: Drawing) -> None:
    width, height = landscape(A4)
    pdf = canvas.Canvas(str(path), pagesize=(width, height))
    pdf.setTitle(title)
    pdf.setAuthor("GeoInspect project team")
    pdf.setFillColor(c.NAVY)
    pdf.rect(0, height - 14 * mm, width, 14 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(18 * mm, height - 9 * mm, title)
    pdf.setFillColor(c.MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(18 * mm, height - 21 * mm, subtitle)

    max_w = width - 36 * mm
    max_h = height - 48 * mm
    scale = min(max_w / drawing.width, max_h / drawing.height)
    x = (width - drawing.width * scale) / 2
    y = 14 * mm + (max_h - drawing.height * scale) / 2
    pdf.saveState()
    pdf.translate(x, y)
    pdf.scale(scale, scale)
    renderPDF.draw(drawing, pdf, 0, 0)
    pdf.restoreState()
    pdf.setStrokeColor(c.LINE)
    pdf.line(18 * mm, 10 * mm, width - 18 * mm, 10 * mm)
    pdf.setFillColor(c.MUTED)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(18 * mm, 6 * mm, "GeoInspect | Editable source is the matching .drawio file")
    pdf.save()


def split_drawio() -> None:
    DIAGRAMS.mkdir(parents=True, exist_ok=True)
    c.build_drawio()
    combined = c.DRAWIO_PATH
    source_root = ET.parse(combined).getroot()
    mapping = {
        "01 Component Architecture": "01_System_Architecture.drawio",
        "02 Main Assignment Sequence": "02_Main_Assignment_Sequence.drawio",
        "03 Notification Failure and Recovery": "03_Notification_Failure_Sequence.drawio",
        "04 Data Ownership": "04_Data_Ownership.drawio",
    }
    for diagram in source_root.findall("diagram"):
        target_name = mapping[diagram.attrib["name"]]
        new_root = ET.Element("mxfile", source_root.attrib)
        new_root.append(deepcopy(diagram))
        ET.ElementTree(new_root).write(DIAGRAMS / target_name, encoding="utf-8", xml_declaration=True)
    combined.unlink(missing_ok=True)


def build_diagram_pdfs() -> None:
    write_diagram_pdf(
        DIAGRAMS / "01_System_Architecture.pdf",
        "GeoInspect - System Architecture",
        "Four business services, database-per-service ownership, and protocol-labelled communication",
        system_architecture_drawing(),
    )
    write_diagram_pdf(
        DIAGRAMS / "02_Main_Assignment_Sequence.pdf",
        "GeoInspect - Main Assignment Sequence",
        "Happy path: idempotent command, work-order claim, atomic reservation, confirmation, and notification",
        c.sequence_diagram(),
    )
    write_diagram_pdf(
        DIAGRAMS / "03_Notification_Failure_Sequence.pdf",
        "GeoInspect - Notification Failure and Recovery",
        "Timeout/retry behavior leaves the assignment confirmed and exposes a safe recovery operation",
        c.failure_diagram(),
    )
    write_diagram_pdf(
        DIAGRAMS / "04_Data_Ownership.pdf",
        "GeoInspect - Data Ownership",
        "Service-owned schemas and cross-service references carried only through REST APIs",
        data_ownership_drawing(),
    )


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    DIAGRAMS.mkdir(parents=True, exist_ok=True)
    build_short_report()
    split_drawio()
    build_diagram_pdfs()
    print(f"created {REPORT}")
    for path in sorted(DIAGRAMS.iterdir()):
        print(f"created {path}")


if __name__ == "__main__":
    main()
