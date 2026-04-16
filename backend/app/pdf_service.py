from __future__ import annotations

from typing import Dict

from playwright.async_api import async_playwright

DEFAULT_MARGIN = {"top": "8mm", "right": "8mm", "bottom": "8mm", "left": "8mm"}
PLAYWRIGHT_INSTALL_HINT = (
    "No se pudo generar el PDF con Playwright. "
    "Verifica que Chromium esté instalado con "
    "`cd backend && source .venv/bin/activate && python -m playwright install chromium`."
)


async def html_to_pdf_bytes(
    html: str,
    landscape: bool = True,
    margin: Dict[str, str] | None = None,
) -> bytes:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1600, "height": 900})
                await page.set_content(html, wait_until="networkidle")
                return await page.pdf(
                    format="A4",
                    landscape=landscape,
                    print_background=True,
                    margin=margin or DEFAULT_MARGIN,
                )
            finally:
                await browser.close()
    except Exception as exc:
        raise RuntimeError(PLAYWRIGHT_INSTALL_HINT) from exc
