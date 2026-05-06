"""Generate synthetic PDF contracts for testing.

Creates 30 realistic-looking procurement contracts distributed across
all renewal urgency buckets so every branch of the agent is exercised.
"""
import os
import random
from datetime import date, timedelta
from faker import Faker
from fpdf import FPDF
from fpdf.enums import XPos, YPos

fake = Faker()
OUTPUT_DIR = "data/contracts"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def s(text: str) -> str:
    """Sanitize to latin-1 safe ASCII — fpdf2 core fonts (Helvetica) are latin-1 only."""
    return (text
            .replace("\u2014", "-")   # em dash
            .replace("\u2013", "-")   # en dash
            .replace("\u2019", "'")   # right single quote
            .replace("\u2018", "'")   # left single quote
            .replace("\u201c", '"')   # left double quote
            .replace("\u201d", '"')   # right double quote
            .replace("\u2022", "*")   # bullet
            .encode("latin-1", errors="replace")
            .decode("latin-1"))

CATEGORIES = ["IT Services", "Logistics", "Raw Materials", "Consulting", "Facilities"]
CURRENCIES = ["EUR", "USD", "GBP"]
ESCALATIONS = ["3% annual increase", "CPI-linked adjustment", "Fixed (no escalation)", "Inflation-indexed"]
SLAS = ["2% deduction per SLA breach", "EUR 500/day penalty", "10% service credit", "No SLA penalties"]
AUTO_RENEWAL_LABELS = ["Yes", "No"]

# Five varied clause structures — each tests a different extraction challenge for Claude
CLAUSE_STYLES = [
    # Style A — standard service agreement
    lambda d: [
        ("RECITALS", (
            f"This Service Agreement is entered into as of {d['start_date']} between "
            f"{d['company']} (hereinafter \"Vendor\") and Procurement Co. (hereinafter \"Client\")."
        )),
        ("1. TERM", (
            f"This Agreement shall commence on {d['start_date']} and continue until "
            f"{d['expiry_date']}, unless earlier terminated in accordance with Section 5."
        )),
        ("2. CONTRACT VALUE", (
            f"The total contract value shall not exceed {d['currency']} {d['value']:,} per annum. "
            f"Invoices shall be submitted monthly in arrears."
        )),
        ("3. PRICE ESCALATION", (
            f"Contract pricing is subject to the following adjustment mechanism: "
            f"{d['escalation']}. Adjustments take effect on each anniversary of the Start Date."
        )),
        ("4. AUTO-RENEWAL", (
            f"Auto-renewal: {d['auto_renewal']}. Where automatic renewal applies, "
            f"either party must provide 60 days written notice prior to the Expiry Date "
            f"to prevent renewal."
        )),
        ("5. SERVICE LEVELS & PENALTIES", d['sla']),
        ("6. GOVERNING LAW", "This Agreement is governed by the laws of England and Wales."),
    ],

    # Style B — supply contract using "Termination Date" (label variation test)
    lambda d: [
        ("SUPPLY CONTRACT", (
            f"Supplier: {d['company']}. Buyer: Procurement Co. "
            f"Commencement Date: {d['start_date']}. Termination Date: {d['expiry_date']}."
        )),
        ("COMMERCIAL TERMS", (
            f"Agreed Contract Value: {d['currency']} {d['value']:,}. "
            f"Payment terms: Net 30 days from invoice date."
        )),
        ("PRICE ADJUSTMENT MECHANISM", d['escalation']),
        ("AUTOMATIC RENEWAL CLAUSE", (
            f"Automatic Renewal: {d['auto_renewal']}. "
            f"Notice period to opt out: 45 days before Termination Date."
        )),
        ("SERVICE LEVEL PENALTIES", d['sla']),
        ("DISPUTE RESOLUTION", (
            "Any disputes shall be resolved by binding arbitration under ICC Rules, "
            "with proceedings held in London."
        )),
    ],

    # Style C — framework agreement with pipe separators (label variation test)
    lambda d: [
        ("FRAMEWORK AGREEMENT", (
            f"Vendor: {d['company']} | Client: Procurement Co. | "
            f"Effective: {d['start_date']} | Expiry: {d['expiry_date']}"
        )),
        ("FINANCIAL TERMS", (
            f"Total Contract Value: {d['currency']} {d['value']:,} | "
            f"Price Escalation: {d['escalation']} | "
            f"Renewal Option: {d['auto_renewal']}"
        )),
        ("PERFORMANCE STANDARDS", d['sla']),
        ("GENERAL CONDITIONS", (
            "This framework agreement incorporates the Client's standard terms and conditions "
            "for goods and services procurement, revision 4.2."
        )),
    ],

    # Style D — missing SLA field (edge case: Claude must return null for sla_penalty)
    lambda d: [
        ("MASTER SERVICES AGREEMENT", (
            f"This MSA is made between {d['company']} (\"Service Provider\") and "
            f"Procurement Co. (\"Customer\") with effect from {d['start_date']}."
        )),
        ("CONTRACT PERIOD", (
            f"Contract Expiry: {d['expiry_date']}. "
            f"The parties may extend this agreement by mutual written consent."
        )),
        ("FEES", (
            f"Total Contract Value: {d['currency']} {d['value']:,} per contract year. "
            f"Price Escalation: {d['escalation']}."
        )),
        ("RENEWAL", (
            f"Auto-Renewal: {d['auto_renewal']}."
        )),
        ("SERVICE LEVELS", (
            "Service level requirements are defined in Schedule 2 (Service Level Schedule), "
            "which is incorporated by reference. No financial penalties are specified in this "
            "main agreement."
        )),
    ],

    # Style E — informal memo style, no explicit auto-renewal field (toughest extraction)
    lambda d: [
        ("VENDOR ENGAGEMENT MEMORANDUM", (
            f"Supplier: {d['company']}\n"
            f"Engagement Start: {d['start_date']}\n"
            f"Review Date: {d['expiry_date']}\n"
            f"Approved Budget: {d['currency']} {d['value']:,}"
        )),
        ("COMMERCIAL NOTES", (
            f"Price clause: {d['escalation']}. "
            f"Performance terms: {d['sla']}."
        )),
        ("RENEWAL NOTE", (
            "Renewal terms are to be renegotiated at the Review Date. No automatic "
            "continuation applies unless confirmed in writing by the Procurement Director."
        )),
        ("APPROVALS", (
            f"Approved by: Procurement Director, {d['start_date']}\n"
            "Subject to annual budget review."
        )),
    ],
]


def _make_pdf(data: dict, sections: list) -> FPDF:
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    # ── Header bar (solid dark rectangle + white title) ──────────────────────
    pdf.set_fill_color(30, 50, 80)
    pdf.rect(0, 0, 210, 22, "F")
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(20, 5)
    pdf.cell(0, 12, s("PROCUREMENT CONTRACT"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    # ── Category pill ─────────────────────────────────────────────────────────
    pdf.set_xy(20, 28)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(220, 230, 245)
    pdf.cell(60, 7, s(f"  Category: {data['category']}"), fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # ── Key facts table ───────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(245, 245, 245)
    col_w = 85
    rows = [
        ("Vendor", data["company"]),
        ("Contract Value", f"{data['currency']} {data['value']:,}"),
        ("Start Date", data["start_date"]),
        ("Expiry Date", data["expiry_date"]),
    ]
    for label, val in rows:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(col_w, 7, s(label), border=1, fill=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(col_w, 7, s(val), border=1)
        pdf.ln()
    pdf.ln(6)

    # ── Clause sections ───────────────────────────────────────────────────────
    for heading, body in sections:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(235, 240, 250)
        pdf.cell(0, 7, s(f"  {heading}"), border="B", fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 5, s(body))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    # ── Signature block ───────────────────────────────────────────────────────
    pdf.ln(4)
    pdf.set_draw_color(150, 150, 150)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    sig_y = pdf.get_y()
    # Left signature
    pdf.line(20, sig_y + 12, 85, sig_y + 12)
    pdf.set_xy(20, sig_y + 13)
    pdf.cell(65, 5, s("Authorised Signatory - Vendor"))
    # Right signature
    pdf.line(110, sig_y + 12, 175, sig_y + 12)
    pdf.set_xy(110, sig_y + 13)
    pdf.cell(65, 5, s("Authorised Signatory - Procurement Co."))
    pdf.ln(12)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(0, 5, s(f"Document reference: {data['ref']}  |  Generated: {date.today().isoformat()}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    return pdf


def make_contract(i: int):
    start = fake.date_between(start_date="-2y", end_date="-6m")
    bucket = i % 5
    days = {0: random.randint(5, 28),
            1: random.randint(31, 58),
            2: random.randint(59, 88)}.get(bucket, random.randint(91, 400))
    expiry = date.today() + timedelta(days=days)

    data = {
        "company":      fake.company(),
        "category":     random.choice(CATEGORIES),
        "start_date":   start.isoformat(),
        "expiry_date":  expiry.isoformat(),
        "currency":     random.choice(CURRENCIES),
        "value":        random.randint(50_000, 2_000_000),
        "auto_renewal": random.choice(AUTO_RENEWAL_LABELS),
        "escalation":   random.choice(ESCALATIONS),
        "sla":          random.choice(SLAS),
        "ref":          fake.bothify("PCO-####-??").upper(),
    }

    style_fn = CLAUSE_STYLES[i % len(CLAUSE_STYLES)]
    sections = style_fn(data)

    pdf = _make_pdf(data, sections)
    slug = data["company"].lower().replace(" ", "_").replace(",", "").replace(".", "")[:28]
    fname = f"{OUTPUT_DIR}/{slug}_{i:03d}.pdf"
    pdf.output(fname)
    print(f"  {fname}  (expires: {data['expiry_date']}, days left: {days})")


if __name__ == "__main__":
    N = 30
    print(f"Generating {N} synthetic contracts...")
    for i in range(N):
        make_contract(i)
    print("Done.")
