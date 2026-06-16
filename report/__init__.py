"""SMA-Report report package -- branded, seller-ready report generation."""

from .report import generate_report, render_html, REPORTLAB_AVAILABLE

__all__ = ["generate_report", "render_html", "REPORTLAB_AVAILABLE"]
