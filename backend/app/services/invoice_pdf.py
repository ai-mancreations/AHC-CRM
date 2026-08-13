from jinja2 import Environment, BaseLoader
from app.models.invoice import Invoice
from app.models.core import Branch
from app.models.appointment import Customer

INVOICE_TEMPLATE = """
<html>
<head>
<style>
  body { font-family: 'Helvetica', sans-serif; color: #1a1a1a; font-size: 12px; }
  .header { display: flex; justify-content: space-between; border-bottom: 2px solid #C9A227; padding-bottom: 12px; }
  .title { color: #0B0B0D; font-size: 22px; font-weight: bold; }
  .accent { color: #C9A227; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; font-size: 11px; }
  th { background: #f4f0e6; }
  .totals { margin-top: 12px; width: 260px; margin-left: auto; }
  .totals td { border: none; padding: 3px 8px; }
  .grand { font-weight: bold; font-size: 14px; border-top: 1px solid #C9A227; }
</style>
</head>
<body>
  <div class="header">
    <div>
      <div class="title">American <span class="accent">Hair Club</span></div>
      <div>{{ branch.name }} Branch</div>
      <div>{{ branch.address }}, {{ branch.city }}, {{ branch.state }}</div>
      <div>GSTIN: {{ branch.gstin }}</div>
    </div>
    <div>
      <div><strong>Invoice #:</strong> {{ invoice.invoice_number }}</div>
      <div><strong>FY:</strong> {{ invoice.financial_year }}</div>
      <div><strong>Date:</strong> {{ invoice.issued_at.strftime('%d-%b-%Y') }}</div>
      <div><strong>Status:</strong> {{ invoice.status.value }}</div>
    </div>
  </div>

  <div style="margin-top:12px;">
    <strong>Bill To:</strong> {{ customer.name }}<br/>
    {{ customer.phone }}{% if customer.email %} | {{ customer.email }}{% endif %}<br/>
    {% if customer.address %}{{ customer.address }}{% endif %}
  </div>

  <table>
    <thead>
      <tr><th>Description</th><th>HSN/SAC</th><th>Qty</th><th>Unit Price</th><th>Taxable Value</th><th>GST %</th><th>CGST</th><th>SGST</th><th>IGST</th><th>Total</th></tr>
    </thead>
    <tbody>
      {% for line in invoice.lines %}
      <tr>
        <td>{{ line.description }}</td>
        <td>{{ line.hsn_sac_code }}</td>
        <td>{{ line.qty }}</td>
        <td>{{ "%.2f"|format(line.unit_price) }}</td>
        <td>{{ "%.2f"|format(line.taxable_value) }}</td>
        <td>{{ line.gst_rate }}%</td>
        <td>{{ "%.2f"|format(line.cgst_amount) }}</td>
        <td>{{ "%.2f"|format(line.sgst_amount) }}</td>
        <td>{{ "%.2f"|format(line.igst_amount) }}</td>
        <td>{{ "%.2f"|format(line.line_total) }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <table class="totals">
    <tr><td>Subtotal</td><td>₹{{ "%.2f"|format(invoice.subtotal) }}</td></tr>
    <tr><td>CGST</td><td>₹{{ "%.2f"|format(invoice.total_cgst) }}</td></tr>
    <tr><td>SGST</td><td>₹{{ "%.2f"|format(invoice.total_sgst) }}</td></tr>
    <tr><td>IGST</td><td>₹{{ "%.2f"|format(invoice.total_igst) }}</td></tr>
    <tr class="grand"><td>Grand Total</td><td>₹{{ "%.2f"|format(invoice.grand_total) }}</td></tr>
    <tr><td>Amount Paid</td><td>₹{{ "%.2f"|format(invoice.amount_paid) }}</td></tr>
    <tr><td>Balance Due</td><td>₹{{ "%.2f"|format(invoice.balance_due) }}</td></tr>
  </table>
</body>
</html>
"""


def render_invoice_html(invoice: Invoice, branch: Branch, customer: Customer) -> str:
    env = Environment(loader=BaseLoader())
    template = env.from_string(INVOICE_TEMPLATE)
    return template.render(invoice=invoice, branch=branch, customer=customer)


def render_invoice_pdf_bytes(invoice: Invoice, branch: Branch, customer: Customer) -> bytes:
    # Imported lazily: weasyprint pulls in system libs (pango/cairo) not always
    # present in every environment; keep the rest of the app importable without it.
    from weasyprint import HTML

    html = render_invoice_html(invoice, branch, customer)
    return HTML(string=html).write_pdf()


async def upload_invoice_pdf(invoice: Invoice, branch: Branch, customer: Customer) -> str:
    """Renders the PDF and uploads to Cloudinary, returning the secure URL.
    Falls back to a data-less placeholder if Cloudinary isn't configured."""
    from app.core.config import get_settings
    settings = get_settings()

    pdf_bytes = render_invoice_pdf_bytes(invoice, branch, customer)

    if not settings.CLOUDINARY_CLOUD_NAME:
        return ""  # not configured in this environment; caller should handle gracefully

    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )
    result = cloudinary.uploader.upload(
        pdf_bytes,
        resource_type="raw",
        public_id=f"invoices/{invoice.invoice_number.replace('/', '_')}",
        overwrite=True,
    )
    return result.get("secure_url", "")
