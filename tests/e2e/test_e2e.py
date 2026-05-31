
import pytest

pytest.importorskip("playwright", reason="playwright not installed — run: pip install playwright && playwright install")

from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def browser_context():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


@pytest.fixture()
def page(browser_context):
    pg = browser_context.new_page()
    yield pg
    pg.close()


class TestE2EHomePage:


    def test_page_title_contains_qr_vault(self, page: Page):
        page.goto(BASE_URL)
        expect(page).to_have_title("QR Vault")

    def test_generate_button_is_visible(self, page: Page):
        page.goto(BASE_URL)
        btn = page.get_by_role("button", name="Generate")
        expect(btn).to_be_visible()

    def test_target_url_input_is_present(self, page: Page):
        page.goto(BASE_URL)
        expect(page.locator("#target_url")).to_be_visible()


class TestE2EQRGeneration:


    def test_generate_qr_flow(self, page: Page):
        page.goto(BASE_URL)
        page.fill("#target_url", "https://playwright-test.example.com")
        page.fill("#label", "Playwright E2E")
        page.click("button:has-text('Generate')")
   
        img = page.locator("#qr-img")
        img.wait_for(state="visible", timeout=10_000)
        src = img.get_attribute("src")
        assert src and "/image" in src

    def test_short_code_displayed_after_generation(self, page: Page):
        page.goto(BASE_URL)
        page.fill("#target_url", "https://shortcode-check.example.com")
        page.click("button:has-text('Generate')")
        code_el = page.locator("#qr-code")
        code_el.wait_for(state="visible", timeout=10_000)
        code_text = code_el.inner_text()
        assert len(code_text) == 8

    def test_redirect_url_displayed(self, page: Page):
        page.goto(BASE_URL)
        page.fill("#target_url", "https://redirect-display.example.com")
        page.click("button:has-text('Generate')")
        redirect_link = page.locator("#qr-redirect")
        redirect_link.wait_for(state="visible", timeout=10_000)
        href = redirect_link.get_attribute("href")
        assert href and "redirect" in href


class TestE2EQRList:
   

    def test_list_loads_on_page_open(self, page: Page):
        page.goto(BASE_URL)
    
        page.wait_for_selector("#qr-list", timeout=5_000)
        content = page.locator("#qr-list").inner_text()
        assert len(content) > 0

    def test_refresh_list_button_works(self, page: Page):
        page.goto(BASE_URL)
        page.click("button:has-text('Refresh list')")
        page.wait_for_timeout(1_000)

        error = page.locator("#qr-list p[style*='f87171']")
        assert error.count() == 0


class TestE2EColorCustomization:
   

    def test_custom_fill_color_generates_qr(self, page: Page):
        page.goto(BASE_URL)
        page.fill("#target_url", "https://custom-color.example.com")
   
        page.evaluate("document.getElementById('fill_color').value = '#7c6af7'")
        page.evaluate("document.getElementById('back_color').value = '#f0f0ff'")
        page.click("button:has-text('Generate')")
        img = page.locator("#qr-img")
        img.wait_for(state="visible", timeout=10_000)
        expect(img).to_be_visible()


class TestE2EErrorHandling:


    def test_empty_url_does_not_crash_page(self, page: Page):
        page.goto(BASE_URL)
     
        page.evaluate("document.getElementById('target_url').removeAttribute('required')")
        page.fill("#target_url", "")
        page.click("button:has-text('Generate')")
        page.wait_for_timeout(1_500)
   
        expect(page.locator("h1")).to_be_visible()
