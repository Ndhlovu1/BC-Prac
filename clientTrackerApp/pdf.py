"""
PDF generation utilities for Client Tracker.

WeasyPrint renders HTML/CSS to PDF server-side, which lets us reuse the
same Bootstrap-ish styling the rest of the app uses without pulling in
a heavyweight layout engine.
"""
from io import BytesIO

from django.template.loader import render_to_string
from weasyprint import HTML, CSS


def render_pdf(template_name: str, context: dict, *, request=None,
               base_url: str = None) -> bytes:
    """
    Render `template_name` with `context` to PDF and return the bytes.

    Passing `base_url` (or `request=request`) lets WeasyPrint resolve
    relative URLs — critically, client logos stored under MEDIA_URL or
    STATIC_URL.
    """
    html_string = render_to_string(template_name, context, request=request)

    # Resolve relative URLs (logos, static files) against the request host
    if base_url is None and request is not None:
        base_url = request.build_absolute_uri("/")

    html = HTML(string=html_string, base_url=base_url)

    # Landscape A4 + tighter margins for tables; tweak per-template if needed
    pdf_css = CSS(string="""
        @page {
            size: A4 landscape;
            margin: 14mm 12mm 16mm 12mm;
            @bottom-right {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #989898;
            }
            @bottom-left {
                content: "Client Tracker";
                font-size: 9pt;
                color: #989898;
            }
        }
    """)

    buf = BytesIO()
    html.write_pdf(target=buf, stylesheets=[pdf_css])
    return buf.getvalue()


    