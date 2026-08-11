from playwright.sync_api import sync_playwright

def fetch_with_browser(url: str) -> dict:
    """
    Fetches the given URL using a headless Chromium browser via Playwright.
    Returns a dictionary containing status_code, headers, cookies, and text.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            try:
                response = page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                if response:
                    status_code = response.status
                    headers = response.headers
                else:
                    status_code = 0
                    headers = {}
                    
                cookies = page.context.cookies()
                text = page.content()
                
            except Exception as e:
                # E.g. TimeoutError or net::ERR_CONNECTION_TIMED_OUT
                status_code = 0
                headers = {}
                cookies = []
                text = ""
                
            return {
                "status_code": status_code,
                "headers": headers,
                "cookies": cookies,
                "text": text
            }
        finally:
            browser.close()
