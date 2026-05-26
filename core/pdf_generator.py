"""Professional PDF quote generation using ReportLab."""

from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.models import SolutionReport

PRIMARY = HexColor("#1a2744")
ACCENT = HexColor("#2563eb")
SUCCESS = HexColor("#16a34a")
WARNING = HexColor("#dc2626")
LIGHT_BG = HexColor("#f8fafc")
TEXT = HexColor("#1e293b")


def _money(value: float) -> str:
    return f"MYR {value:,.2f}"


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(str(text).replace("\n", "<br/>"), style)


def generate_pdf(report: SolutionReport) -> bytes:
    """Generate a multi-page technical solution proposal as PDF bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", fontSize=28, leading=34, textColor=colors.white, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="CoverSub", fontSize=14, leading=18, textColor=colors.white))
    styles.add(ParagraphStyle(name="H1Navy", fontSize=18, leading=24, textColor=PRIMARY, fontName="Helvetica-Bold", spaceAfter=10))
    styles.add(ParagraphStyle(name="BodyTextDark", fontSize=10, leading=14, textColor=TEXT))
    styles.add(ParagraphStyle(name="SmallDark", fontSize=8, leading=11, textColor=TEXT))
    story = []

    header = Table(
        [[_para("TECHNICAL SOLUTION PROPOSAL", styles["CoverTitle"])], [_para("Prepared by AutoSales Engineer Pro", styles["CoverSub"])]],
        colWidths=[7.2 * inch],
        rowHeights=[0.75 * inch, 0.45 * inch],
    )
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PRIMARY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 20)]))
    story += [header, Spacer(1, 0.5 * inch)]
    story += [
        _para(report.client_name, ParagraphStyle(name="Client", fontSize=22, leading=28, textColor=PRIMARY, fontName="Helvetica-Bold")),
        Spacer(1, 0.2 * inch),
        _para(f"Date generated: {date.today().isoformat()}", styles["BodyTextDark"]),
        Spacer(1, 0.15 * inch),
        _para("CONFIDENTIAL", ParagraphStyle(name="Badge", fontSize=12, textColor=WARNING, fontName="Helvetica-Bold")),
        Spacer(1, 3.7 * inch),
        _para("Powered by Gemini 3.5 Flash with Gemini 2.5 fallback | Groq | Chutes Qwen/DeepSeek with Groq fallback", styles["SmallDark"]),
        PageBreak(),
    ]

    story += [_para("Executive Summary", styles["H1Navy"])]
    client_table = Table(
        [["Client", report.client_name], ["Use case", report.use_case], ["Location", report.delivery_location], ["Date", date.today().isoformat()]],
        colWidths=[1.4 * inch, 5.8 * inch],
    )
    client_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("BACKGROUND", (0, 0), (0, -1), LIGHT_BG), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold")]))
    story += [client_table, Spacer(1, 0.2 * inch)]
    status = "WITHIN BUDGET" if report.within_budget else "OVER BUDGET"
    budget_table = Table(
        [["Budget", _money(report.budget_myr)], ["Total", _money(report.total_price_myr)], ["Utilization", f"{report.budget_utilization_pct:.1f}%"], ["Status", status]],
        colWidths=[2 * inch, 2.2 * inch],
    )
    budget_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG), ("BOX", (0, 0), (-1, -1), 1, ACCENT), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold")]))
    health = Table(
        [
            ["Budget Status", "PASS" if report.within_budget else "FAIL", "Compatibility", "PASS" if report.compatibility_matrix.all_compatible else "FAIL"],
            ["Delivery Feasible", "PASS" if report.delivery_feasible else "FAIL", "Reviewer Approved", "PASS" if report.reviewer_feedback.approved else "FAIL"],
            ["Technical Score", f"{report.reviewer_feedback.technical_score:.1f}/10", "Commercial Score", f"{report.reviewer_feedback.commercial_score:.1f}/10"],
        ],
        colWidths=[1.6 * inch, 1.2 * inch, 1.6 * inch, 1.2 * inch],
    )
    health.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG)]))
    story += [budget_table, Spacer(1, 0.2 * inch), health, Spacer(1, 0.2 * inch), _para(report.executive_summary, styles["BodyTextDark"]), PageBreak()]

    story += [_para("Itemized Bill of Materials", styles["H1Navy"])]
    rows = [["#", "Product", "Qty", "Unit", "URL", "Source", "Subtotal"]]
    for idx, item in enumerate(report.line_items, start=1):
        rows.append([idx, _para(item.product_name, styles["SmallDark"]), item.quantity, _money(item.unit_price_myr), _para(item.product_url, styles["SmallDark"]), item.source_platform, _money(item.subtotal_myr)])
    rows.append(["", "TOTAL", "", "", "", "", _money(report.total_price_myr)])
    bom = Table(rows, colWidths=[0.3 * inch, 1.75 * inch, 0.35 * inch, 0.85 * inch, 1.65 * inch, 0.75 * inch, 0.9 * inch], repeatRows=1)
    bom.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("BACKGROUND", (0, 1), (-1, -2), colors.white), ("BACKGROUND", (0, -1), (-1, -1), PRIMARY), ("TEXTCOLOR", (0, -1), (-1, -1), colors.white), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    story += [bom, Spacer(1, 0.2 * inch), _para(f"TOTAL: {_money(report.total_price_myr)}", styles["H1Navy"]), Spacer(1, 0.25 * inch)]
    story += [_para("Logistics & Cost of Ownership", styles["H1Navy"])]
    tco_rows = [["Product", "Shipping", "SST", "TCO"]]
    for item in report.line_items:
        tco_rows.append([_para(item.product_name, styles["SmallDark"]), _money(item.shipping_fee_myr), _money(item.sst_myr), _money(item.tco_myr)])
    tco_rows.append(["Grand Total TCO", "", "", _money(report.logistics_tco_total_myr)])
    tco = Table(tco_rows, colWidths=[3.3 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch])
    tco.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("BACKGROUND", (0, -1), (-1, -1), PRIMARY), ("TEXTCOLOR", (0, -1), (-1, -1), colors.white)]))
    story += [tco, PageBreak()]

    story += [_para("Technical Review", styles["H1Navy"])]
    matrix_rows = [["Product A", "Product B", "Status", "Reason"]]
    for pair in report.compatibility_matrix.pairs_checked:
        matrix_rows.append([
            pair.get("a_name", pair["a"]),
            pair.get("b_name", pair["b"]),
            "PASS" if pair["compatible"] else "FAIL",
            _para(pair["reason"], styles["SmallDark"]),
        ])
    matrix = Table(matrix_rows, colWidths=[1.4 * inch, 1.4 * inch, 0.7 * inch, 3.3 * inch])
    matrix.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]))
    story += [matrix, Spacer(1, 0.2 * inch), _para("Reviewer Assessment", styles["H1Navy"]), _para(report.reviewer_feedback.overall_assessment, styles["BodyTextDark"])]
    story += [Spacer(1, 0.15 * inch), _para("Risk Flags", styles["H1Navy"])]
    story += [_para(f"- {flag}", styles["BodyTextDark"]) for flag in (report.reviewer_feedback.risk_flags or ["No major risk flags."])]
    story += [Spacer(1, 0.15 * inch), _para("Suggestions", styles["H1Navy"])]
    story += [_para(f"- {suggestion}", styles["BodyTextDark"]) for suggestion in (report.reviewer_feedback.suggestions or ["No additional suggestions."])]
    story += [Spacer(1, 0.15 * inch), _para("Recommendations", styles["H1Navy"])]
    story += [_para(f"- {rec}", styles["BodyTextDark"]) for rec in (report.recommendations or ["Proceed with procurement validation."])]
    story += [PageBreak()]

    story += [_para("Pipeline & Terms", styles["H1Navy"])]
    story += [_para("[Gemini 3.5 Flash -> Gemini 2.5 Flash] -> [Groq Parser] -> [Chutes Qwen -> Groq] -> [Chutes DeepSeek -> Groq]<br/>Visual Analyst -> Parser Agent -> Sales Engineer -> Reviewer Agent", styles["BodyTextDark"])]
    story += [Spacer(1, 0.2 * inch), _para("Reasoning Summary", styles["H1Navy"]), _para(report.reasoning_summary, styles["BodyTextDark"])]
    story += [Spacer(1, 0.2 * inch), _para("Delivery Timeline Estimate", styles["H1Navy"]), _para(report.delivery_timeline_estimate, styles["BodyTextDark"])]
    story += [Spacer(1, 0.2 * inch), _para("Self-Critique Iterations", styles["H1Navy"])]
    for item in report.self_critique_history:
        story.append(_para(f"Iteration {item.iteration}: {'Passed' if item.passed else 'Failed'} - {', '.join(item.issues_found) or 'No issues'}", styles["BodyTextDark"]))
    story += [
        Spacer(1, 0.25 * inch),
        _para("Standard procurement disclaimer: pricing, availability, shipping, taxes, and delivery timelines are estimates and should be validated with vendors before purchase order issuance.", styles["BodyTextDark"]),
        Spacer(1, 0.45 * inch),
        _para("Client: ____________________    Consultant: ____________________    Date: ____________________", styles["BodyTextDark"]),
    ]
    doc.build(story)
    return buffer.getvalue()
