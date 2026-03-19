# notifier.py -- encoding: utf-8
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime

def send_alert(title, message):
    try:
        from plyer import notification
        notification.notify(title=title, message=message,
                            app_name="주식알림", timeout=10)
    except:
        print("알림: " + title)
        print(message)

# ── 미국 지수: Yahoo Finance ───────────────────────────────
US_WATCHLIST = {
    "^DJI":  "Dow Jones",
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq",
}

# ── 한국 지수: 네이버 금융 (KRX 데이터 실시간 반영) ──────────
KR_WATCHLIST = {
    "KOSPI":  "KOSPI",
    "KOSDAQ": "KOSDAQ",
}

WATCHLIST = {**US_WATCHLIST, "KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ"}
ALERT_THRESHOLD = 2.0


def get_kospi_naver(index_type="KOSPI"):
    """네이버 금융에서 KOSPI / KOSDAQ 실시간 데이터 가져오기"""
    try:
        code = "KOSPI" if index_type == "KOSPI" else "KOSDAQ"
        url  = f"https://finance.naver.com/sise/sise_index.nhn?code={code}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res  = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")

        # 현재 지수
        price_tag = soup.select_one("#now_value")
        change_tag = soup.select_one("#change_value")
        rate_tag   = soup.select_one("#change_rate")

        if price_tag:
            price  = float(price_tag.text.replace(",", ""))
            change_text = change_tag.text.replace(",", "").strip() if change_tag else "0"
            rate_text   = rate_tag.text.replace("%", "").replace(",", "").strip() if rate_tag else "0"

            # 상승/하락 부호 판단
            is_down = "하락" in res.text or "fall" in res.text.lower()
            change  = -float(change_text) if is_down else float(change_text)
            rate    = -float(rate_text)   if is_down else float(rate_text)

            return {
                "price":  price,
                "change": change,
                "pct":    rate,
                "prev":   round(price - change, 2),
                "source": "네이버금융(KRX)",
            }
    except Exception as e:
        print(f"네이버 금융 조회 실패: {e}")
    return None


def get_us_stats(ticker):
    """Yahoo Finance에서 미국 지수 가져오기"""
    try:
        t    = yf.Ticker(ticker)
        info = t.fast_info
        hist = t.history(period="2d", interval="1d")
        cur  = float(info.last_price) if info.last_price else 0
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else cur
        chg  = cur - prev
        pct  = (chg / prev * 100) if prev else 0
        return {
            "price":  cur,
            "change": chg,
            "pct":    pct,
            "prev":   prev,
            "source": "Yahoo Finance",
        }
    except Exception as e:
        print(f"{ticker} 조회 실패: {e}")
        return None


class StockWatcher:
    def __init__(self):
        self.alert_cooldown = {}
        self.running = False

    def check_all(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 점검중...")

        # 미국 지수
        for ticker, name in US_WATCHLIST.items():
            s = get_us_stats(ticker)
            if s is None:
                continue
            print(f"  {name:12s} | {s['price']:>10,.2f} | {s['pct']:+.2f}% ({s['source']})")
            self._check_alert(ticker, name, s)

        # 한국 지수
        for code, name in KR_WATCHLIST.items():
            s = get_kospi_naver(code)
            if s is None:
                continue
            print(f"  {name:12s} | {s['price']:>10,.2f} | {s['pct']:+.2f}% ({s['source']})")
            self._check_alert(code, name, s)

    def _check_alert(self, key, name, s):
        cooldown_ok = (time.time() - self.alert_cooldown.get(key, 0)) > 1800
        if abs(s["pct"]) >= ALERT_THRESHOLD and cooldown_ok:
            self.alert_cooldown[key] = time.time()
            direction = "상승" if s["pct"] > 0 else "하락"
            send_alert(
                f"🚨 {name} {direction} {abs(s['pct']):.1f}%!",
                f"현재가: {s['price']:,.2f}\n변동률: {s['pct']:+.2f}%\n시각: {datetime.now().strftime('%H:%M:%S')}"
            )

    def start(self):
        self.running = True
        print("🔍 감시 시작!")
        while self.running:
            self.check_all()
            time.sleep(60)

    def stop(self):
        self.running = False
