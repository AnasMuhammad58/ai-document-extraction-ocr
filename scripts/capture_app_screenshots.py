"""Capture genuine screenshots from the locally running Streamlit app."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "app_screenshots"
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:8501"

def wait_ready(page):
    page.goto(URL, wait_until="networkidle", timeout=60_000)
    page.get_by_text("AI Document Extraction", exact=False).first.wait_for(timeout=60_000)
    page.get_by_text("2. Preview", exact=True).wait_for(timeout=60_000)
    page.get_by_text("Filename:", exact=True).wait_for(timeout=60_000)
    page.wait_for_timeout(2_000)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
    wait_ready(page)
    page.screenshot(path=OUT / "01_upload_and_preview.png", full_page=False)

    page.get_by_role("button", name="Extract Document Data").click()
    page.get_by_text("3. Batch summary", exact=True).wait_for(timeout=120_000)
    page.get_by_text("4. Review results", exact=True).scroll_into_view_if_needed()
    page.locator('[data-testid="stDataFrame"]').first.wait_for(timeout=60_000)
    page.wait_for_timeout(2_000)
    page.screenshot(path=OUT / "02_extracted_fields.png", full_page=False)

    page.get_by_text("Validation Results", exact=True).scroll_into_view_if_needed()
    page.wait_for_timeout(1_500)
    page.screenshot(path=OUT / "03_line_items_and_validation.png", full_page=False)

    # Reload, keep the default clean invoice sample, and add a receipt upload.
    page.goto(URL, wait_until="networkidle", timeout=60_000)
    page.locator('input[type="file"]').set_input_files(
        str(ROOT / "data" / "samples" / "rct-0001_digital.pdf")
    )
    page.get_by_text("2. Preview", exact=True).wait_for(timeout=60_000)
    page.get_by_role("button", name="Extract Document Data").click()
    page.get_by_text("3. Batch summary", exact=True).wait_for(timeout=120_000)
    page.get_by_text("5. Download reviewed data", exact=True).wait_for(timeout=60_000)
    page.get_by_text("3. Batch summary", exact=True).scroll_into_view_if_needed()
    page.set_viewport_size({"width": 1440, "height": 3000})
    page.wait_for_timeout(2_000)
    page.screenshot(path=OUT / "04_batch_results_and_exports.png", full_page=False)
    browser.close()

print(f"Saved screenshots to {OUT}")
