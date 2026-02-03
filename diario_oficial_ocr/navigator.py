from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterator, Optional

from playwright.sync_api import Page, sync_playwright

from diario_oficial_ocr.config import BrowserConfig, SiteConfig
from diario_oficial_ocr.utils import Backoff, hash_bytes

logger = logging.getLogger(__name__)


@dataclass
class PageSnapshot:
    date: date
    section: str
    carilla: str
    url: str
    image_bytes: bytes
    image_hash: str
    full_screenshot: bytes


class DiarioOficialNavigator:
    def __init__(self, site: SiteConfig, browser: BrowserConfig) -> None:
        self.site = site
        self.browser = browser

    def iter_date_pages(self, target_date: date) -> Iterator[PageSnapshot]:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.browser.headless, slow_mo=self.browser.slow_mo_ms)
            context = browser.new_context(
                viewport={"width": self.browser.viewport_width, "height": self.browser.viewport_height}
            )
            page = context.new_page()
            page.set_default_timeout(self.browser.navigation_timeout_ms)
            page.goto(self.site.base_url)
            self._ensure_images_view(page)
            self._validate_images_view(page, stage="pre-filter")
            self._apply_filters(page, target_date)

            if self._no_content(page):
                logger.info("No content for %s", target_date)
                browser.close()
                return
            self._validate_images_view(page, stage="post-filter")

            previous_hash: Optional[str] = None
            previous_carilla: Optional[str] = None
            unchanged_count = 0

            while True:
                self._ensure_section(page, target_date)
                snapshot = self._capture_snapshot(page, target_date)
                if not snapshot:
                    logger.warning("No snapshot captured for %s", target_date)
                    break

                yield snapshot

                if previous_hash == snapshot.image_hash and previous_carilla == snapshot.carilla:
                    unchanged_count += 1
                else:
                    unchanged_count = 0

                if unchanged_count >= self.browser.end_of_carillas_attempts:
                    logger.info("Reached end of carillas for %s", target_date)
                    break

                previous_hash = snapshot.image_hash
                previous_carilla = snapshot.carilla

                if not self._advance_carilla(page):
                    logger.info("Unable to advance carilla for %s", target_date)
                    break

            browser.close()

    def _apply_filters(self, page: Page, target_date: date) -> None:
        date_str = target_date.strftime("%d/%m/%Y")
        selectors = self.site.selectors
        backoff = Backoff()
        for attempt in range(self.browser.max_action_retries):
            try:
                page.wait_for_selector(selectors["section_select"], timeout=self.browser.navigation_timeout_ms)
                page.wait_for_selector(selectors["date_input"], timeout=self.browser.navigation_timeout_ms)
                date_input = page.locator(selectors["date_input"]).first
                date_input.fill(date_str)
                section_select = page.locator(selectors["section_select"]).first
                if section_select.count() > 0:
                    try:
                        section_select.select_option(value=self.site.section_value)
                    except Exception:
                        section_select.select_option(label=self.site.section_name)
                else:
                    page.get_by_label("Sección").select_option(value=self.site.section_value)
                self._log_section_options(page)
                selected = page.locator(selectors["section_select"]).first.input_value()
                if selected != self.site.section_value:
                    logger.warning("Section value mismatch. selected=%s expected=%s", selected, self.site.section_value)
                page.locator(selectors["apply_button"]).first.click()
                page.wait_for_timeout(self.browser.action_delay_ms)
                return
            except Exception as exc:
                self._log_ui_state(page, context="apply-filters-failed")
                logger.warning("Retrying apply filters: %s", exc)
                backoff.sleep(attempt)
        raise RuntimeError("Failed to apply filters")

    def _no_content(self, page: Page) -> bool:
        selectors = self.site.selectors
        try:
            if page.locator(selectors["no_content"]).first.is_visible():
                return True
            image_locator = page.locator(selectors["image"]).first
            if image_locator.count() > 0 and not image_locator.is_visible():
                return True
            return False
        except Exception:
            return False

    def _ensure_images_view(self, page: Page) -> None:
        selectors = self.site.selectors
        try:
            link = page.locator(selectors["images_view_link"]).first
            if link.count() > 0 and link.is_visible():
                link.click()
                page.wait_for_timeout(self.browser.action_delay_ms)
        except Exception:
            return

        if not self._has_images_view(page):
            try:
                fallback_url = f"{self.site.base_url.rstrip('/')}/imagenes"
                page.goto(fallback_url)
                page.wait_for_timeout(self.browser.action_delay_ms)
            except Exception:
                return

    def _validate_images_view(self, page: Page, stage: str) -> None:
        selectors = self.site.selectors
        try:
            if not self._has_images_view(page):
                self._log_ui_state(page, context=f"validate-images-view-{stage}")
                raise RuntimeError("Images view not loaded; required controls not found.")
        except Exception as exc:
            raise RuntimeError("Images view not loaded; required controls not found.") from exc

    def _has_images_view(self, page: Page) -> bool:
        selectors = self.site.selectors
        image = page.locator(selectors["image"]).first
        section = page.locator(selectors["section_select"]).first
        carilla = page.locator("select#carilla, select[name='carilla']").first
        next_button = page.locator(selectors["next_carilla"]).first
        return all(
            [
                image.count() > 0,
                section.count() > 0,
                carilla.count() > 0,
                next_button.count() > 0,
            ]
        )

    def _log_section_options(self, page: Page) -> None:
        selectors = self.site.selectors
        try:
            options = page.locator(f"{selectors['section_select']} option")
            values = options.evaluate_all("els => els.slice(0, 4).map(el => el.value)") if options.count() else []
            logger.info("Section options found: count=%s sample=%s", options.count(), values)
        except Exception as exc:
            logger.warning("Failed to log section options: %s", exc)

    def _log_ui_state(self, page: Page, context: str) -> None:
        selectors = self.site.selectors
        try:
            title = page.title()
        except Exception:
            title = ""
        try:
            url = page.url
        except Exception:
            url = ""
        def _exists(selector: str) -> bool:
            try:
                return page.locator(selector).count() > 0
            except Exception:
                return False
        logger.warning(
            "UI state (%s): url=%s title=%s image=%s section=%s carilla=%s next=%s",
            context,
            url,
            title,
            _exists(selectors["image"]),
            _exists(selectors["section_select"]),
            _exists("select#carilla, select[name='carilla']"),
            _exists(selectors["next_carilla"]),
        )

    def _capture_snapshot(self, page: Page, target_date: date) -> Optional[PageSnapshot]:
        selectors = self.site.selectors
        try:
            image_locator = page.locator(selectors["image"]).first
            image_bytes = image_locator.screenshot(type="png")
            image_hash = hash_bytes(image_bytes)
            carilla = self._get_carilla(page)
            full_screenshot = page.screenshot(full_page=True)
            return PageSnapshot(
                date=target_date,
                section=self.site.section_name,
                carilla=carilla,
                url=page.url,
                image_bytes=image_bytes,
                image_hash=image_hash,
                full_screenshot=full_screenshot,
            )
        except Exception as exc:
            logger.warning("Failed to capture snapshot: %s", exc)
            return None

    def _ensure_section(self, page: Page, target_date: date) -> None:
        selectors = self.site.selectors
        try:
            current = page.locator(selectors["section_select"]).input_value()
            if current and current != self.site.section_value:
                logger.info("Section reset detected for %s. Reapplying filters.", target_date)
                self._apply_filters(page, target_date)
        except Exception:
            return

    def _get_carilla(self, page: Page) -> str:
        selectors = self.site.selectors
        try:
            label = page.locator(selectors["carilla_label"]).first.inner_text().strip()
            return label or "1"
        except Exception:
            return "1"

    def _advance_carilla(self, page: Page) -> bool:
        selectors = self.site.selectors
        backoff = Backoff()
        for attempt in range(self.browser.max_action_retries):
            try:
                page.click(selectors["next_carilla"])
                page.wait_for_timeout(self.browser.action_delay_ms)
                return True
            except Exception as exc:
                logger.warning("Retrying advance carilla: %s", exc)
                backoff.sleep(attempt)
        return False
