from datetime import datetime
from app.models.enums import GstType


def determine_gst_type(branch_state_code: str, customer_state_code: str | None) -> GstType:
    """Intra-state (same state as branch) -> CGST+SGST. Otherwise -> IGST."""
    if not customer_state_code or customer_state_code == branch_state_code:
        return GstType.INTRA_STATE
    return GstType.INTER_STATE


def compute_line_tax(taxable_value: float, gst_rate: float, gst_type: GstType) -> dict:
    """Returns cgst/sgst/igst amounts for a single invoice line."""
    total_tax = round(taxable_value * gst_rate / 100, 2)
    if gst_type == GstType.INTRA_STATE:
        half = round(total_tax / 2, 2)
        return {"cgst_amount": half, "sgst_amount": total_tax - half, "igst_amount": 0.0}
    return {"cgst_amount": 0.0, "sgst_amount": 0.0, "igst_amount": total_tax}


def financial_year_label(dt: datetime, fy_start_month: int = 4) -> str:
    """April(4)-March FY. Returns e.g. '2025-26' and a short code '2526' for numbering."""
    if dt.month >= fy_start_month:
        start_year = dt.year
    else:
        start_year = dt.year - 1
    end_year = start_year + 1
    return f"{start_year}-{str(end_year)[-2:]}"


def financial_year_short_code(dt: datetime, fy_start_month: int = 4) -> str:
    label = financial_year_label(dt, fy_start_month)  # "2025-26"
    start, end = label.split("-")
    return f"{start[-2:]}{end}"  # "2526"
