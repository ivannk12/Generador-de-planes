from __future__ import annotations

from typing import Any, Dict

from .pdf_service import html_to_pdf_bytes
from .progress_renderer import render_progress_html


async def generate_progress_pdf_bytes(cfg: Dict[str, Any]) -> bytes:
    html = render_progress_html(cfg)
    return await html_to_pdf_bytes(
        html,
        landscape=False,
        margin={"top": "10mm", "right": "10mm", "bottom": "10mm", "left": "10mm"},
    )
