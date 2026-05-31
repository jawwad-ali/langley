"""
One-shot screenshot capture for the intelligence dossier UI.
Run via: uv run --with playwright python scripts/capture_dossier.py
"""
import time
from playwright.sync_api import sync_playwright

REPORT = {
    "token_address": "So11111111111111111111111111111111111111112",
    "token_symbol": "SOL",
    "verdict": "likely_safe",
    "confidence": 0.95,
    "headline": "Wrapped SOL (SOL) Deemed Likely Safe with Strong Market Indicators",
    "briefing": (
        "Wrapped SOL is likely safe: the Risk Guardian cites deep liquidity, a multi-year "
        "track record, and balanced two-sided trading, and the on-chain forensics corroborate "
        "this with renounced mint and freeze authorities and a fixed supply."
    ),
    "agreement": "corroborating",
    "key_points": [
        "Deep liquidity (~$28M) supports easy entry and exit.",
        "Balanced 24h trading (~9.7k buys / 9.8k sells) signals an active two-sided market.",
        "Mint and freeze authorities are renounced — supply is fixed and wallets cannot be frozen.",
        "Established for ~2.9 years, indicating market maturity.",
        "No disqualifying risk signals were found.",
    ],
    "risk_signals": [
        {
            "category": "liquidity",
            "level": "info",
            "title": "Deep liquidity",
            "detail": "Multi-million USD liquidity supports easy entry and exit.",
            "evidence": [{"field": "liquidity_usd", "observed_value": "28337777.42"}],
        },
        {
            "category": "trading_activity",
            "level": "info",
            "title": "Healthy two-sided trading",
            "detail": "Balanced buys and sells over the last 24h.",
            "evidence": [
                {"field": "buys_24h", "observed_value": "9743"},
                {"field": "sells_24h", "observed_value": "9861"},
            ],
        },
        {
            "category": "age",
            "level": "info",
            "title": "Established token",
            "detail": "Years of continuous trading history.",
            "evidence": [{"field": "age_hours", "observed_value": "25596"}],
        },
    ],
    "forensic_findings": [
        {
            "dimension": "liquidity",
            "observation": "Liquidity of ~$28.3M USD indicates substantial depth for trading.",
            "evidence": [{"field": "liquidity_usd", "observed_value": "28337777.42"}],
        },
        {
            "dimension": "activity",
            "observation": "24h volume of ~$45.9M with 9,743 buys and 9,861 sells.",
            "evidence": [
                {"field": "volume_24h_usd", "observed_value": "45886679.14"},
                {"field": "buys_24h", "observed_value": "9743"},
            ],
        },
        {
            "dimension": "age",
            "observation": "Pair active approximately 25,596 hours (~2.9 years).",
            "evidence": [{"field": "age_hours", "observed_value": "25596"}],
        },
        {
            "dimension": "authorities",
            "observation": "Mint and freeze authorities are renounced; supply is fixed.",
            "evidence": [
                {"field": "mint_authority_renounced", "observed_value": "True"},
                {"field": "freeze_authority_renounced", "observed_value": "True"},
            ],
        },
    ],
    "contributing_agents": ["risk_guardian", "onchain_forensics"],
    "data_provider": "dexscreener+helius",
}

OUTPUT_PATH = "D:/CipherNest-Crypto/docs/screenshots/dossier-intelligence.png"

def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        print("Navigating to http://127.0.0.1:8000 ...")
        page.goto("http://127.0.0.1:8000", wait_until="networkidle", timeout=15000)
        print("Page loaded.")

        # Inject the report via window.renderReport
        print("Calling window.renderReport(REPORT) ...")
        result = page.evaluate("(report) => { window.renderReport(report); return 'ok'; }", REPORT)
        print(f"renderReport returned: {result!r}")

        # Wait for fonts, CSS animations, and any JS transitions to settle
        print("Waiting 2.5s for animations to settle ...")
        time.sleep(2.5)

        # Capture full-page screenshot
        print(f"Saving screenshot to {OUTPUT_PATH} ...")
        page.screenshot(path=OUTPUT_PATH, full_page=True)
        print("Screenshot saved.")

        # Report pixel dimensions
        from PIL import Image  # type: ignore[import]
        img = Image.open(OUTPUT_PATH)
        print(f"Dimensions: {img.width}x{img.height} px")

        browser.close()

if __name__ == "__main__":
    main()
