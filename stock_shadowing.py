import requests
import time
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yfinance as yf
import pandas as pd
from pykrx import stock as krx

TELEGRAM_TOKEN   = "placeholder"
TELEGRAM_CHAT_ID = "placeholder"

KST = ZoneInfo("Asia/Seoul")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

PRIORITY_SECTORS = [
    "Technology", "Software", "Semiconductor", "AI",
    "Biotechnology", "Healthcare", "Aerospace", "Defense",
    "Space", "Energy", "Utilities", "Electric", "Power",
    "Clean Energy", "Renewable"
]

ARK_FUNDS = {
    "ARKK": "ARK Innovation ETF",
    "ARKQ": "ARK Autonomous Technology & Robotics ETF",
    "ARKG": "ARK Genomic Revolution ETF",
    "ARKF": "ARK Fintech Innovation ETF",
    "ARKW": "ARK Next Generation Internet ETF",
}


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    for chunk in chunks:
        try:
            r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML"}, timeout=10)
            if not r.ok:
                logging.warning(f"Telegram error: {r.text}")
            time.sleep(0.5)
        except Exception as e:
            logging.warning(f"Telegram send failed: {e}")


def run_kr_shadowing():
    logging.info("국내 쉐도잉 시작...")
    try:
        today    = datetime.now(KST)
        prev_day = (today - timedelta(days=1)).strftime("%Y%m%d")
        df  = krx.get_market_ohlcv(prev_day, market="KOSPI")
        df2 = krx.get_market_ohlcv(prev_day, market="KOSDAQ")
        df  = pd.concat([df, df2])
        df["거래대금억"] = df["거래대금"] / 1e8
        filtered = df[(df["등락률"] >

def is_priority_sector(sector: str) -> str:
    if not sector:
        return ""
    for s in PRIORITY_SECTORS:
        if s.lower() in sector.lower():
            return s
    return ""


def run_us_shadowing():
    logging.info("미국 쉐도잉 시작...")
    try:
        today = datetime.now(KST)
        try:
            sp500 = pd.read_csv("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv")["Symbol"].tolist()
        except Exception:
            sp500 = []
        extra = ["PLTR","TSLA","RKLB","NVDA","AMD","META","GOOGL","MSFT","AMZN","NFLX","CRWD","SNOW","DDOG","NET","SMCI","ARM","IONQ","RGTI","QUBT","LUNR","ASTS","OKLO","CEG","VST","NRG","GEV","ETN","PWR","ARRY"]
        universe = list(set(sp500[:200] + extra))
        results = []
        for ticker in universe:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="2d")
                if len(hist) < 2:
                    continue
                prev_close = float(hist["Close"].iloc[-2])
                last_close = float(hist["Close"].iloc[-1])
                volume = float(hist["Volume"].iloc[-1])
                change_pct = (last_close - prev_close) / prev_close * 100
                dollar_vol = last_close * volume
                if change_pct < 8 or dollar_vol < 50_000_000:
                    continue
                info = t.fast_info
                market_cap = getattr(info, "market_cap", 0) or 0
                if market_cap < 1_000_000_000:
                    continue
                if (getattr(info, "quote_type", "") or "").upper() in ["ETF","MUTUALFUND"]:
                    continue
                sector = t.info.get("sector", "")
                results.append({"ticker":ticker,"change":change_pct,"dollar_vol":dollar_vol/1e6,"sector":sector,"priority":is_priority_sector(sector),"price":last_close})
            except Exception:
                continue
        if not results:
            send_telegram(f"<b>미국 쉐도잉</b> {today.strftime('%m/%d')}\n조건 충족 없음")
            return
        df_res = pd.DataFrame(results).sort_values(["priority","change"],ascending=[False,False])
        lines = [f"<b>미국 쉐도잉</b> {today.strftime('%m/%d')}",f"상승률 8%+ 거래대금 5천만$+ 시총 10억$+  {len(df_res)}개"]
        for _, row in df_res.iterrows():
            star = "★ " if row["priority"] else ""
            tag = f"[{row['priority']}]" if row["priority"] else f"[{row['sector'][:10]}]"
            lines.append(f"{star}<b>{row['ticker']}</b>{tag} +{row['change']:.1f}%  ${row['dollar_vol']:.0f}M  ${row['price']:.2f}")
        send_telegram("\n".join(lines))
    except Exception as e:
        send_telegram(f"미국 쉐도잉 오류: {e}")


def run_ark_tracking():
    logging.info("ARK 추적 시작...")
    try:
        today = datetime.now(KST)
        all_items = []
        for symbol, fname in ARK_FUNDS.items():
            try:
                resp = requests.get(f"https://arkfunds.io/api/v2/etf/holdings?symbol={symbol}", timeout=10)
                if not resp.ok:
                    continue
                rows = resp.json().get("holdings", [])
                if not rows:
                    continue
                df = pd.DataFrame(rows).rename(columns={"ticker":"Ticker","weight":"Weight","company":"Company"})
                top5 = df.nlargest(5, "Weight") if "Weight" in df.columns else df.head(5)
                all_items.append({"fund":symbol,"fname":fname,"top5":top5})
            except Exception:
                continue
        if not all_items:
            send_telegram(f"<b>ARK 추적</b> {today.strftime('%m/%d')}\n데이터 수집 실패")
            return
        lines = [f"<b>ARK Invest 포트 추적</b> {today.strftime('%m/%d')}"]
        for item in all_items:
            lines.append(f"\n<b>{item['fund']}</b> {item['fname'][:25]}")
            for _, row in item["top5"].iterrows():
                lines.append(f"  {row.get('Ticker',''):6s} {str(row.get('Company',''))[:18]:18s} {row.get('Weight',0):.1f}%")
        lines.append("\nhttps://ark-funds.com/funds/")
        send_telegram("\n".join(lines))
    except Exception as e:
        send_telegram(f"ARK 추적 오류: {e}")
= 15) & (df["거래대금억"] >= 500)].copy()
        filtered = filtered.sort_values("등락률", ascending=False)
        if filtered.empty:
            send_telegram(f"<b>국내 쉐도잉</b> {today.strftime('%m/%d')}\n조건 충족 종목 없음")
            return
        lines = [f"<b>국내 쉐도잉</b> {today.strftime('%m/%d')}", f"상승률 15%+ 거래대금 500억+  {len(filtered)}개"]
        for code, row in filtered.iterrows():
            name = krx.get_market_ticker_name(code)
            lines.append(f"<b>{name}</b>({code}) +{row['등락률']:.1f}%  {row['거래대금억']:.0f}억  {int(row['종가']):,}원")
        send_telegram("\n".join(lines))
    except Exception as e:
        send_telegram(f"국내 쉐도잉 오류: {e}")
