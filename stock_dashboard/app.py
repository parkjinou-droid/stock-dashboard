# app.py -- encoding: utf-8
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time

st.set_page_config(page_title="주식 대시보드", page_icon="📊", layout="wide")

st.markdown('''
<style>
.card {
    background: linear-gradient(135deg, #1e2130, #2d3250);
    border-radius: 12px; padding: 20px; text-align: center;
    border: 1px solid #3d4166; margin-bottom: 10px;
}
.cname  { color: #a0aec0; font-size: 0.85rem; margin-bottom:4px; }
.cprice { color: #e2e8f0; font-size: 1.6rem; font-weight: bold; }
.csource { color: #4a5568; font-size: 0.72rem; margin-top:6px; }
</style>
''', unsafe_allow_html=True)

with st.sidebar:
    st.title("설정")
    st.markdown("---")
    refresh = st.slider("새로고침 주기(초)", 30, 300, 60, 30)
    thr     = st.slider("알림 변동률(%)", 0.5, 5.0, 2.0, 0.5)
    period  = st.selectbox("차트 기간", ["1d","5d","1mo","3mo"], index=1,
                format_func=lambda x: {"1d":"오늘","5d":"5일","1mo":"1개월","3mo":"3개월"}[x])
    if st.button("지금 새로고침"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.markdown(f"""
**데이터 출처**
- Dow / S&P500 / Nasdaq : Yahoo Finance
- KOSPI : 네이버금융 (KRX)

**마지막 업데이트**
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")

st.title("글로벌 지수 실시간 대시보드")
st.caption(f"자동 새로고침: {refresh}초마다  |  알림 기준: +/-{thr}% 변동시 알림")
st.markdown("---")


@st.cache_data(ttl=30)
def get_kospi_naver(code="KOSPI"):
    """네이버 금융 -> KRX 실시간 (change_value_and_rate ID 사용)"""
    try:
        url = f"https://finance.naver.com/sise/sise_index.nhn?code={code}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")

        # 현재가
        price_tag = soup.select_one("#now_value")
        price = float(price_tag.text.replace(",", "").strip()) if price_tag else 0

        change_val = 0.0
        rate_val   = 0.0

        # #change_value_and_rate 에서 읽기
        # 실제 텍스트 예시: "170.17  -2.87%상승"
        # 마이너스 부호가 있으면 하락, 없으면 상승
        cr_tag = soup.select_one("#change_value_and_rate")
        if cr_tag:
            cr_text = cr_tag.text.strip()
            # 부호 포함 숫자와 퍼센트 추출
            # 패턴: (부호포함숫자) (부호포함퍼센트)%
            m = re.search(r'(-?[\d,]+\.?\d*)\s+(-?[\d.]+)%', cr_text)
            if m:
                change_val = float(m.group(1).replace(",", ""))
                rate_val   = float(m.group(2))

        # fallback: yfinance 로 계산
        if change_val == 0.0 and price > 0:
            ticker = "^KS11" if code == "KOSPI" else "^KQ11"
            hist = yf.Ticker(ticker).history(period="2d", interval="1d")
            if len(hist) >= 2:
                prev       = float(hist["Close"].iloc[-2])
                change_val = round(price - prev, 2)
                rate_val   = round((change_val / prev) * 100, 2)

        return {
            "price":  price,
            "change": change_val,
            "pct":    rate_val,
            "prev":   round(price - change_val, 2),
            "high":   0.0,
            "low":    0.0,
            "source": "네이버금융(KRX)",
        }

    except Exception as e:
        try:
            ticker = "^KS11" if code == "KOSPI" else "^KQ11"
            t    = yf.Ticker(ticker)
            info = t.fast_info
            hist = t.history(period="2d", interval="1d")
            cur  = float(info.last_price) if info.last_price else 0
            prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else cur
            chg  = cur - prev
            pct  = (chg / prev * 100) if prev else 0
            return {"price":cur,"change":chg,"pct":pct,"prev":prev,
                    "high":0.0,"low":0.0,"source":"Yahoo Finance (대체)"}
        except:
            return {"price":0,"change":0,"pct":0,"prev":0,
                    "high":0,"low":0,"source":"오류"}


@st.cache_data(ttl=30)
def get_us_stats(ticker):
    try:
        t    = yf.Ticker(ticker)
        info = t.fast_info
        hist = t.history(period="2d", interval="1d")
        cur  = float(info.last_price) if info.last_price else 0
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else cur
        chg  = cur - prev
        pct  = (chg / prev * 100) if prev else 0
        return {"price":cur,"change":chg,"pct":pct,"prev":prev,
                "high":float(info.year_high or 0),
                "low":float(info.year_low or 0),
                "source":"Yahoo Finance"}
    except:
        return {"price":0,"change":0,"pct":0,"prev":0,
                "high":0,"low":0,"source":"오류"}


INDICES = [
    {"key": "^DJI",  "name": "Dow Jones", "type": "us"},
    {"key": "^GSPC", "name": "S&P 500",   "type": "us"},
    {"key": "^IXIC", "name": "Nasdaq",    "type": "us"},
    {"key": "KOSPI", "name": "KOSPI",     "type": "kr"},
]

cols   = st.columns(4)
alerts = []

for i, idx in enumerate(INDICES):
    s = get_kospi_naver(idx["key"]) if idx["type"] == "kr" else get_us_stats(idx["key"])
    color = "#00d4aa" if s["pct"] >= 0 else "#ff6b6b"
    arrow = "▲" if s["pct"] >= 0 else "▼"
    if abs(s["pct"]) >= thr:
        alerts.append(idx["name"])
    with cols[i]:
        st.markdown(f'''
        <div class="card">
            <div class="cname">{idx["name"]}</div>
            <div class="cprice">{s["price"]:,.2f}</div>
            <div style="color:{color};font-size:1.1rem;margin-top:6px;">
                {arrow} {abs(s["pct"]):.2f}% ({s["change"]:+,.2f})
            </div>
            <div style="color:#718096;font-size:0.78rem;margin-top:6px;">
                전일종가: {s["prev"]:,.2f}
            </div>
            <div class="csource">{s["source"]}</div>
        </div>''', unsafe_allow_html=True)

if alerts:
    st.warning(f"변동률 {thr}% 초과 종목: {', '.join(alerts)}")

st.markdown("---")

st.subheader("지수 차트")
interval = "15m" if period in ["1d","5d"] else "1d"
tab1, tab2, tab3, tab4 = st.tabs(["Dow Jones", "S&P 500", "Nasdaq", "KOSPI"])

def draw_us_chart(ticker, name):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            st.error("데이터 없음")
            return
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            vertical_spacing=0.05, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name=name,
            increasing_line_color="#00d4aa", decreasing_line_color="#ff6b6b"
        ), row=1, col=1)
        if len(df) >= 20:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["Close"].rolling(20).mean(),
                line=dict(color="#f6c90e", width=1.5), name="MA20"
            ), row=1, col=1)
        colors = ["#00d4aa" if c >= o else "#ff6b6b"
                  for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            marker_color=colors, name="거래량", opacity=0.7
        ), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=500,
            xaxis_rangeslider_visible=False,
            paper_bgcolor="#1e2130", plot_bgcolor="#1e2130")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("데이터 출처: Yahoo Finance")
    except Exception as e:
        st.error(f"차트 오류: {e}")

def draw_kospi_chart():
    try:
        df = yf.download("^KS11", period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            st.error("KOSPI 차트 데이터 없음")
            return
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            vertical_spacing=0.05, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="KOSPI",
            increasing_line_color="#00d4aa", decreasing_line_color="#ff6b6b"
        ), row=1, col=1)
        if len(df) >= 20:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["Close"].rolling(20).mean(),
                line=dict(color="#f6c90e", width=1.5), name="MA20"
            ), row=1, col=1)
        colors = ["#00d4aa" if c >= o else "#ff6b6b"
                  for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            marker_color=colors, name="거래량", opacity=0.7
        ), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=500,
            xaxis_rangeslider_visible=False,
            paper_bgcolor="#1e2130", plot_bgcolor="#1e2130")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("현재가: 네이버금융(KRX)  |  차트: Yahoo Finance(^KS11)")
    except Exception as e:
        st.error(f"KOSPI 차트 오류: {e}")

with tab1: draw_us_chart("^DJI",  "Dow Jones")
with tab2: draw_us_chart("^GSPC", "S&P 500")
with tab3: draw_us_chart("^IXIC", "Nasdaq")
with tab4: draw_kospi_chart()

st.markdown("---")
st.subheader("상세 지수 정보")
rows = []
for idx in INDICES:
    s = get_kospi_naver(idx["key"]) if idx["type"] == "kr" else get_us_stats(idx["key"])
    rows.append({
        "지수":       idx["name"],
        "현재가":     f"{s['price']:,.2f}",
        "전일비":     f"{s['change']:+,.2f}",
        "등락률":     f"{s['pct']:+.2f}%",
        "52주최고":   f"{s['high']:,.2f}" if s["high"] else "-",
        "52주최저":   f"{s['low']:,.2f}"  if s["low"]  else "-",
        "데이터출처": s["source"],
        "상태":       "알림" if abs(s["pct"]) >= thr else "정상",
    })
st.dataframe(pd.DataFrame(rows).set_index("지수"),
             use_container_width=True, height=220)

time.sleep(refresh)
st.rerun()
