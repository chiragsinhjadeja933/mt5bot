"""
Render 5-Minute Health Check & Watchdog Script.
Runs as a scheduled Cron Job (*/5 * * * *) on Render to monitor the MT5 Trading Bot.
"""
import os
import sys
import json
import urllib.request
import urllib.error

TARGET_URL = os.getenv("TARGET_BOT_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.getenv("API_TOKEN", "dev-token-change-me")


def check_system():
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    print(f"[{os.getenv('RENDER_SERVICE_NAME', 'Render-Watchdog')}] Checking MT5 Bot at: {TARGET_URL}")

    # 1. Check Health Endpoint
    try:
        health_req = urllib.request.Request(f"{TARGET_URL}/api/health", headers=headers)
        with urllib.request.urlopen(health_req, timeout=10) as res:
            health_data = json.loads(res.read().decode())
            print(f"[OK] Health check passed: {health_data.get('status')}")
    except Exception as e:
        print(f"[ERROR] Bot health endpoint unreachable: {e}")
        sys.exit(1)

    # 2. Check Basket & MT5 Status
    try:
        basket_req = urllib.request.Request(f"{TARGET_URL}/api/trading/basket", headers=headers)
        with urllib.request.urlopen(basket_req, timeout=10) as res:
            basket = json.loads(res.read().decode())
            print(f"[STATUS] Mode: {basket.get('execution_mode')}")
            print(f"[STATUS] Basket ID: {basket.get('basket_id')}")
            print(f"[STATUS] Positions: {basket.get('position_count')}/{basket.get('max_positions')}")
            print(f"[STATUS] Floating P/L: ${basket.get('floating_pnl')} (Target TP: ${basket.get('basket_tp')})")
            print(f"[STATUS] Progress towards TP: {basket.get('progress_pct')}%")
    except Exception as e:
        print(f"[WARNING] Could not fetch basket status: {e}")

    print("[SUCCESS] 5-minute health & risk check completed cleanly.")


if __name__ == "__main__":
    check_system()
