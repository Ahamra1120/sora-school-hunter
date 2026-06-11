"""Playwright helper untuk scraping website yang butuh JavaScript."""
import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext


_browser: Browser | None = None
_context: BrowserContext | None = None


async def get_browser() -> BrowserContext:
    global _browser, _context
    if _context is None:
        p = await async_playwright().start()
        _browser = await p.chromium.launch(headless=True)
        _context = await _browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="id-ID",
        )
    return _context


async def fetch_with_js(url: str, timeout_ms: int = 15_000) -> str:
    """Buka URL dengan browser headless, return HTML setelah JS dirender."""
    ctx = await get_browser()
    page = await ctx.new_page()
    try:
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)  # tunggu konten dinamis
        html = await page.content()
        return html
    except Exception:
        return ""
    finally:
        await page.close()


async def close_browser():
    global _browser, _context
    if _browser:
        await _browser.close()
        _browser = None
        _context = None
