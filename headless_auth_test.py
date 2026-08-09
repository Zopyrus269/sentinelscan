import os

from playwright.sync_api import sync_playwright

# A short-lived Firebase custom auth token (1hr expiry), signed with the
# project's service account. Never hardcode a real one here -- generate a
# fresh token with `firebase_admin.auth.create_custom_token("test-uid-playwright-001")`
# against a running backend and export it, e.g.:
#   HEADLESS_TEST_TOKEN=<token> pytest headless_auth_test.py
CUSTOM_TOKEN = os.environ.get("HEADLESS_TEST_TOKEN", "")

import pytest

@pytest.mark.skip(reason="Requires live backend server - skipping for CI/CD")
def test_headless_authentication():
    if not CUSTOM_TOKEN:
        raise RuntimeError("Set HEADLESS_TEST_TOKEN to a fresh custom token before running this test.")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"http://localhost:5000/auth-headless-test.html?token={CUSTOM_TOKEN}")
        page.wait_for_function(
            "document.getElementById('status').textContent !== 'not-signed-in'",
            timeout=15000
        )
        status_text = page.text_content("#status")
        print("Sign-in status:", status_text)

        if status_text != "signed-in":
            print("SIGN-IN FAILED, stopping here.")
            browser.close()
            exit(1)

        storage = context.storage_state(path="auth_session.json")
        print("Session saved to auth_session.json")

        page.goto("http://localhost:5000")
        page.wait_for_timeout(2000)

        icon_default = page.query_selector("#profileIconDefault")
        avatar = page.query_selector("#profileAvatar")
        profile_button = page.query_selector("#profileButton")

        print("--- BEFORE clicking profile button ---")
        print("icon_default class:", icon_default.get_attribute("class"))
        print("icon_default computed display:", icon_default.evaluate("el => getComputedStyle(el).display"))
        print("avatar class:", avatar.get_attribute("class"))
        print("avatar computed display:", avatar.evaluate("el => getComputedStyle(el).display"))
        print("avatar src:", avatar.get_attribute("src"))

        page.screenshot(path="profile_icon_before_click.png")

        profile_button.click()
        page.wait_for_timeout(500)

        dropdown = page.query_selector("#profileDropdown")
        email_el = page.query_selector("#profileEmail")
        print("--- AFTER clicking profile button ---")
        print("dropdown class:", dropdown.get_attribute("class"))
        print("dropdown computed display:", dropdown.evaluate("el => getComputedStyle(el).display"))
        print("profileEmail text:", email_el.text_content())

        page.screenshot(path="profile_dropdown_after_click.png")
        print("Screenshots saved: profile_icon_before_click.png, profile_dropdown_after_click.png")

        browser.close()
