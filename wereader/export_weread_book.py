#!/usr/bin/env python3
"""Export authorized WeRead page responses through a logged-in browser session."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.async_api import BrowserContext, Page, Response, async_playwright
except ImportError:  # Keep --help and the installation message available without Playwright.
    BrowserContext = Page = Response = None  # type: ignore[assignment,misc]
    async_playwright = None


DEFAULT_BOOK_URL = "https://weread.qq.com/web/reader/800323e07158c8e0800fd55"
READ_PATH = "/web/book/read"
logger = logging.getLogger(__name__)


def save_response(output_dir: Path, sequence: int, response: Response, body: bytes) -> Path:
    """Save response metadata and decoded body without exposing request headers."""
    digest = hashlib.sha256(body).hexdigest()
    try:
        payload = json.loads(body.decode("utf-8"))
        suffix = "json"
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {"body_hex": body.hex(), "encoding": "hex"}
        suffix = "json"

    record = {
        "sequence": sequence,
        "url": response.url,
        "status": response.status,
        "content_sha256": digest,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "body": payload,
    }
    path = output_dir / f"page_{sequence:05d}.{suffix}"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def wait_for_login(page: Page, wait_seconds: int) -> None:
    """Give the user time to complete login if the page is not authenticated."""
    logger.info("Browser opened. Complete login in the browser if required.")
    await page.wait_for_timeout(wait_seconds * 1000)
    logger.info("Current page: url=%s title=%s", page.url, await page.title())


async def visible_content(page: Page) -> str:
    """Return readable content from the rendered reader area."""
    locator = page.locator(".passage-content").first
    try:
        if await locator.is_visible():
            return (await locator.inner_text(timeout=1000)).strip()
    except Exception:
        pass
    return ""


async def has_visible_canvas(page: Page) -> bool:
    """Check whether the reader has a visible canvas with usable dimensions."""
    for index in range(await page.locator(".wr_canvasContainer canvas").count()):
        canvas = page.locator(".wr_canvasContainer canvas").nth(index)
        try:
            if await canvas.is_visible():
                box = await canvas.bounding_box()
                if box and box["width"] > 1 and box["height"] > 1:
                    return True
        except Exception:
            continue
    return False


async def wait_for_rendered_content(page: Page, wait_seconds: int) -> tuple[str, bool]:
    """Wait until text or canvas content is visible, then return its state."""
    deadline = asyncio.get_running_loop().time() + wait_seconds
    while True:
        text = await visible_content(page)
        if text:
            return text, False
        if await has_visible_canvas(page):
            return "", True
        if asyncio.get_running_loop().time() >= deadline:
            return "", False
        await page.wait_for_timeout(500)


async def capture_screenshot(page: Page, path: Path | None = None) -> bytes | None:
    """Capture a screenshot with a viewport fallback when full-page capture times out."""
    try:
        image = await page.screenshot(type="png", full_page=True, timeout=10000)
    except Exception as exc:
        logger.warning("Full-page screenshot failed; using viewport screenshot: %s", exc)
        try:
            image = await page.screenshot(type="png", full_page=False, timeout=10000)
        except Exception as fallback_exc:
            logger.warning("Viewport screenshot failed; continuing without PNG: %s", fallback_exc)
            return None
    if path is not None:
        path.write_bytes(image)
    return image


async def save_rendered_page(
    page: Page,
    output_dir: Path,
    sequence: int,
    save_screenshot: bool,
) -> str:
    """Save the browser-rendered page and readable text."""
    html_path = output_dir / f"page_{sequence:05d}.html"
    text_path = output_dir / f"page_{sequence:05d}.txt"
    text = await visible_content(page)
    html_path.write_text(await page.content(), encoding="utf-8")
    text_path.write_text(text + "\n" if text else "[Canvas-rendered content; see PNG screenshot.]\n", encoding="utf-8")
    if save_screenshot or not text:
        await capture_screenshot(page, output_dir / f"page_{sequence:05d}.png")
    logger.info("Saved rendered page %d: %s and %s", sequence, html_path, text_path)
    return text


async def export_book(
    book_url: str,
    output_dir: Path,
    profile_dir: Path,
    max_pages: int,
    headed: bool,
    login_wait_seconds: int,
    save_json: bool,
    save_screenshot: bool,
    render_wait_seconds: int,
) -> int:
    if async_playwright is None:
        logger.error("Playwright is not installed. Run: python3 -m pip install playwright")
        return 1
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    captured_hashes: set[str] = set()
    captured_count = 0
    last_new_response = asyncio.Event()

    async with async_playwright() as playwright:
        context: BrowserContext = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=not headed,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        async def handle_response(response: Response) -> None:
            nonlocal captured_count
            if urlparse(response.url).path != READ_PATH:
                return
            logger.info("Observed read response: status=%d url=%s", response.status, response.url)
            if response.status != 200:
                return
            try:
                body = await response.body()
            except Exception as exc:  # Playwright may close a response during navigation.
                logger.warning("Could not read response body: %s", exc)
                return
            digest = hashlib.sha256(body).hexdigest()
            if digest in captured_hashes:
                logger.info("Skipped duplicate response: %s", digest[:12])
                return
            captured_hashes.add(digest)
            captured_count += 1
            if save_json:
                path = save_response(output_dir, captured_count, response, body)
                logger.info("Saved response %d: %s", captured_count, path)
            last_new_response.set()

        context.on("response", handle_response)
        await page.goto(book_url, wait_until="domcontentloaded")
        await wait_for_login(page, login_wait_seconds)
        current_text, current_canvas = await wait_for_rendered_content(page, render_wait_seconds)
        if not current_text and not current_canvas:
            logger.error("No visible reader content found; check login and page access.")
            await context.close()
            return 1
        current_image = await capture_screenshot(page)
        current_digest = hashlib.sha256(
            current_image if current_canvas and current_image else current_text.encode("utf-8")
        ).hexdigest()
        await save_rendered_page(page, output_dir, 1, save_screenshot or current_canvas)
        viewport = await page.evaluate("({width: window.innerWidth, height: window.innerHeight})")
        next_x = max(1, int(viewport["width"]) - 80)
        next_y = max(1, int(viewport["height"]) // 2)

        for page_number in range(2, max_pages + 1):
            last_new_response.clear()
            try:
                await page.mouse.click(next_x, next_y)
                await page.keyboard.press("ArrowRight")
            except Exception as exc:
                logger.error("Could not advance to page %d: %s", page_number, exc)
                break
            try:
                await asyncio.wait_for(last_new_response.wait(), timeout=8)
            except asyncio.TimeoutError:
                logger.info("No new interface response after page %d; checking visible content.", page_number)
            await page.wait_for_timeout(500)
            next_text, next_canvas = await wait_for_rendered_content(page, render_wait_seconds)
            if not next_text and not next_canvas:
                logger.info("No visible reader content after page %d; stopping.", page_number)
                break
            next_image = await capture_screenshot(page)
            next_digest = hashlib.sha256(
                next_image if next_canvas and next_image else next_text.encode("utf-8")
            ).hexdigest()
            if next_digest == current_digest:
                logger.info("No visible content change after page %d; stopping.", page_number)
                break
            current_digest = next_digest
            await save_rendered_page(page, output_dir, page_number, save_screenshot or next_canvas)

        await context.close()

    logger.info("Export finished: %d unique response(s) saved.", captured_count)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-url", default=DEFAULT_BOOK_URL)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/bianjq/work/activity/weread_export"),
    )
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=Path("/Users/bianjq/work/activity/weread_browser_profile"),
    )
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--headed", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--save-json", action="store_true", help="Save matching interface responses")
    parser.add_argument("--save-screenshot", action="store_true", help="Save a PNG screenshot for each page")
    parser.add_argument("--render-wait-seconds", type=int, default=15)
    parser.add_argument(
        "--login-wait-seconds",
        type=int,
        default=60,
        help="Seconds to wait for browser login (default: 60)",
    )
    args = parser.parse_args()

    if args.max_pages < 1:
        parser.error("--max-pages must be at least 1")
    if args.login_wait_seconds < 0:
        parser.error("--login-wait-seconds must be non-negative")
    if args.render_wait_seconds < 1:
        parser.error("--render-wait-seconds must be at least 1")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        return asyncio.run(
            export_book(
                args.book_url,
                args.output_dir.resolve(),
                args.profile_dir.resolve(),
                args.max_pages,
                args.headed,
                args.login_wait_seconds,
                args.save_json,
                args.save_screenshot,
                args.render_wait_seconds,
            )
        )
    except Exception as exc:
        logger.error("Export failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
