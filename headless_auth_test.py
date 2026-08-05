from playwright.sync_api import sync_playwright

CUSTOM_TOKEN = "eyJhbGciOiAiUlMyNTYiLCAidHlwIjogIkpXVCIsICJraWQiOiAiYjhiY2U4MzMwNjE4MGNmNGY4MmM5NzIxYjRmN2E2ODliNWQ2OGU1MCJ9.eyJpc3MiOiAiZmlyZWJhc2UtYWRtaW5zZGstZmJzdmNAc2VudGluZWxzY2FuLTNmODJkLmlhbS5nc2VydmljZWFjY291bnQuY29tIiwgInN1YiI6ICJmaXJlYmFzZS1hZG1pbnNkay1mYnN2Y0BzZW50aW5lbHNjYW4tM2Y4MmQuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLCAiYXVkIjogImh0dHBzOi8vaWRlbnRpdHl0b29sa2l0Lmdvb2dsZWFwaXMuY29tL2dvb2dsZS5pZGVudGl0eS5pZGVudGl0eXRvb2xraXQudjEuSWRlbnRpdHlUb29sa2l0IiwgInVpZCI6ICJ0ZXN0LXVpZC1wbGF5d3JpZ2h0LTAwMSIsICJpYXQiOiAxNzg1OTA5NzA4LCAiZXhwIjogMTc4NTkxMzMwOH0.ReXjfGmVQe5ywuaWtrW-7Ca5pSIjWXbMLiuCtPI6aA0DATzRR5tEBa5lfSO1A4iG8EMLc43Jl97DaaJVd-gItgx7pxGQrPVqX7nKSbQysZ7Krq6XpHILziez7rlTJh_LiaOhjnY3Jo-eBRzerUocXEmEDvqIZUQxw3yKe_cEJE5ASiu7vfJpByHObdYbqfp9JZEk7q8_5wikE4I_w91X01_0bc9Q8ARm2osnMLOn-ohXJ5HOMCs9bC145r-Wiiv6ZPvMlYWrZvykuBvyoqjh3Qn8WuAG9f_cAAtRwpzjP8csWK0Da1KKrE9PaXxYrR6BWeEq2WBemB5f63uRiL7Eiw"

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
