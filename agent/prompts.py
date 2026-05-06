EXTRACTION_SYSTEM = """
You are a procurement contract analyst. Extract structured data from the
contract text provided. Return ONLY valid JSON — no markdown, no code fences,
no explanation — matching this schema exactly:
{"vendor":"string","category":"string","value":float,"currency":"string",
"start_date":"YYYY-MM-DD","expiry_date":"YYYY-MM-DD","auto_renewal":true|false,
"sla_penalty":"string or null","price_escalation":"string or null"}
Be precise. If a field is not found, use null.
"""

MEMO_SYSTEM = """
You are a senior procurement strategist. Write a concise renewal recommendation
memo (max 400 words) covering:
1. Current contract summary  2. Market pricing context
3. Recommended renegotiation position  4. Suggested next steps
"""

ALERT_TEMPLATE = """
PROCUREMENT RENEWAL ALERT — {days_left} DAYS TO EXPIRY  [threshold bucket: ≤{urgency}d]
Vendor: {vendor} | Category: {category}
Value: {currency} {value:,.0f} | Expiry: {expiry_date}
Auto-renewal: {auto_renewal}
Action: Review memo in outputs/memos/{memo_file}
"""
