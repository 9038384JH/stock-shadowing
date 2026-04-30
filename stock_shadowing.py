"""
주식 쉐도잉 & ARK 추적 자동화
──────────────────────────────────────────────
① 국내 주식 쉐도잉  — 매일 오전 09:00 (전일 종가)
② 미국 주식 쉐도잉  — 매일 오전 08:00 (미국 전일 종가)
③ ARK Invest 추적   — 매일 오전 08:00 (전일 매매 내역)
→ 텔레그램 봇으로 자동 발송
"""

import requests
import schedule
import time
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yfinance as yf
import pandas as pd
from pykrx import stock as krx

TELEGRAM_TOKEN   = "여기에_봇_토큰_입력"
TELEGRAM_CHAT_ID = "347730514"

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
            r = requests.post(url, json={
                "chat_id":    TELEGRAM_CHAT_ID,
                "text":       chunk,
                "parse_mode": "HTML",
            }, timeout=10)
            if not r.ok:
                logging.warning(f"Telegram error: {r.text}")
            time.sleep(0.5)
        except Exception as e:
            logging.warning(f"Telegram send failed: {e}")


def run_kr_shadowing():
    logging.info("국내 쉐도잉 시작...")
    try:
        today     = datetime.now(KST)
        prev_day  = (today - timedelta(days=1)).strftime("%Y%m%d")
        df = krx.get_market_ohlcv(prev_day, market="KOSPI")
        df2 = krx.get_market_ohlcv(prev_day, market="KOSDAQ")
        df = pd.concat([df, df2])
        df["거래대금억"] = df["거래대금"] / 1e8
        filtered = df[
            (df["등락률"] >= 15) &
            (df["거래대금억"] >= 500)
        ].copy()
        filtered = filtered.sort_values("등락률", ascending=False)

        if filtered.empty:
            send_telegram(
                f"📊 <b>국내 쉐도잉</b>  {today.strftime('%m/%d')}\n"
                "✅ 조건 충족 종목 없음 (상승률 15%↑ · 거래대금 500억↑)"
            )
            return

        lines = [f"📊 <b>국내 주식 쉐도잉</b>  {today.strftime('%m/%d')} 전일 종가 기준",
                 f"조건: 상승률 15%↑ · 거래대금 500억↑  |  {len(filtered)}개 종목",
                 "─" * 30]

        for code, row in filtered.iterrows():
            name = krx.get_market_ticker_name(code)
            lines.append(
                f"\n<b>{name}</b> ({code})\n"
                f"  상승률: <b>+{row['등락률']:.1f}%</b>  |  "
                f"거래대금: {row['거래대금억']:.0f}억  |  "
                f"종가: {int(row['종가']):,}원"
            )

        lines.append("\n─" * 30)
        lines.append("<i>* 급등 이유는 개별 확인 필요</i>")
        send_telegram("\n".join(lines))
        logging.info(f"국내 쉐도잉 완료: {len(filtered)}개")

    except Exception as e:
        logging.error(f"국내 쉐도잉 오류: {e}")
        send_telegram(f"⚠️ 국내 쉐도잉 오류: {e}")


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
        sp500_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
        try:
            sp500 = pd.read_csv(sp500_url)["Symbol"].tolist()
        except:
            sp500 = []

        extra = [
            "PLTR","TSLA","RKLB","NVDA","AMD","META","GOOGL","MSFT",
            "AMZN","NFLX","CRWD","SNOW","DDOG","NET","SMCI","ARM",
            "IONQ","RGTI","QUBT","LUNR","RDW","ASTS","OKLO","CEG",
            "VST","NRG","GEV","ETN","CARR","PWR","WLDN","ARRY",
        ]
        universe = list(set(sp500[:200] + extra))

        results = []
        for ticker in universe:
            try:
                t    = yf.Ticker(ticker)
                hist = t.history(period="2d")
                if len(hist) < 2:
                    continue
                prev_close = hist["Close"].iloc[-2]
                last_close = hist["Close"].iloc[-1]
                volume     = hist["Volume"].iloc[-1]
                change_pct = (last_close - prev_close) / prev_close * 100
                dollar_vol = last_close * volume
                if change_pct < 8 or dollar_vol < 50_000_000:
                    continue
                info       = t.fast_info
                market_cap = getattr(info, "market_cap", 0) or 0
                if market_cap < 1_000_000_000:
                    continue
                quote_type = getattr(info, "quote_type", "") or ""
                if quote_type.upper() in ["ETF", "MUTUALFUND"]:
                    continue
                sector = t.info.get("sector", "")
                priority = is_priority_sector(sector)
                results.append({
                    "ticker":     ticker,
                    "change":     change_pct,
                    "dollar_vol": dollar_vol / 1e6,
                    "mktcap":     market_cap / 1e9,
                    "sector":     sector,
                    "priority":   priority,
                    "price":      last_close,
                })
            except:
                continue

        if not results:
            send_telegram(
                f"📈 <b>미국 쉐도잉</b>  {today.strftime('%m/%d')}\n"
                "✅ 조건 충족 종목 없음"
            )
            return

        df_res = pd.DataFrame(results).sort_values(
            ["priority", "change"], ascending=[False, False]
        )

        lines = [
            f"📈 <b>미국 주식 쉐도잉</b>  {today.strftime('%m/%d')} 전일 종가 기준",
            f"조건: 상승률 8%↑ · 거래대금 5천만$↑ · 시총 10억$↑  |  {len(df_res)}개 종목",
            "─" * 30
        ]

        for _, row in df_res.iterrows():
            star = "⭐ " if row["priority"] else ""
            sector_tag = f"[{row['priority']}]" if row["priority"] else f"[{row['sector'][:15]}]" if row["sector"] else ""
            lines.append(
                f"\n{star}<b>{row['ticker']}</b>  {sector_tag}\n"
                f"  상승률: <b>+{row['change']:.1f}%</b>  |  "
                f"거래대금: ${row['dollar_vol']:.0f}M  |  "
                f"종가: ${row['price']:.2f}"
            )

        lines.append("\n─" * 30)
        lines.append("<i>⭐ = 우선 섹터 (테크·AI·바이오·우주·에너지·전력)</i>")
        send_telegram("\n".join(lines))
        logging.info(f"미국 쉐도잉 완료: {len(df_res)}개")

    except Exception as e:
        logging.error(f"미국 쉐도잉 오류: {e}")
        send_telegram(f"⚠️ 미국 쉐도잉 오류: {e}")


def run_ark_tracking():
    logging.info("ARK 추적 시작...")
    try:
        today = datetime.now(KST)
        all_changes = []

        for symbol, name in ARK_FUNDS.items():
            try:
                urls_to_try = [
                    f"https://arkfunds.io/api/v2/etf/holdings?symbol={symbol}",
                ]
                df = None
                for u in urls_to_try:
                    try:
                        resp = requests.get(u, timeout=10)
                        if resp.ok:
                            if "json" in resp.headers.get("Content-Type",""):
                                data = resp.json()
                                holdings = data.get("holdings", [])
                                df = pd.DataFrame(holdings)
                            else:
                                from io import StringIO
                                df = pd.read_csv(StringIO(resp.text))
                            break
                    except:
                        continue

                if df is None or df.empty:
                    continue

                if "ticker" in df.columns and "weight" in df.columns:
                    df = df.rename(columns={
                        "ticker": "Ticker",
                        "weight": "Weight(%)",
                        "company": "Company",
                    })
                    top5 = df.nlargest(5, "Weight(%)") if "Weight(%)" in df.columns else df.head(5)
                    all_changes.append({
                        "fund":  symbol,
                        "fname": name,
                        "top5":  top5,
                    })
            except Exception as e:
                logging.warning(f"ARK {symbol} 오류: {e}")
                continue

        if not all_changes:
            send_telegram(
                f"🦆 <b>ARK Invest 추적</b>  {today.strftime('%m/%d')}\n"
                "⚠️ 데이터 수집 실패 → https://ark-funds.com/funds/ 직접 확인"
            )
            return

        lines = [
            f"🦆 <b>ARK Invest 포트 추적</b>  {today.strftime('%m/%d')}",
            "─" * 30
        ]
        for item in all_changes:
            lines.append(f"\n<b>{item['fund']}</b>  {item['fname'][:30]}")
            for _, row in item["top5"].iterrows():
                ticker  = row.get("Ticker", "")
                company = row.get("Company", "")[:20]
                weight  = row.get("Weight(%)", 0)
                lines.append(f"  {ticker:6s} {company:20s}  {weight:.1f}%")

        lines.append("\n─" * 30)
        lines.append("→ 전체: https://ark-funds.com/funds/")
        send_telegram("\n".join(lines))
        logging.info("ARK 추적 완료")

    except Exception as e:
        logging.error(f"ARK 추적 오류: {e}")
        send_telegram(f"⚠️ ARK 추적 오류: {e}")


def run_morning():
    run_us_shadowing()
    time.sleep(2)
    run_ark_tracking()

def run_kr():
    run_kr_shadowing()


if __name__ == "__main__":
    logging.info("🚀 주식 쉐도잉 에이전트 시작")
    send_telegram(
        "🚀 <b>주식 쉐도잉 에이전트 시작</b>\n"
        "① 국내 쉐도잉: 매일 09:00\n"
        "② 미국 쉐도잉: 매일 08:00\n"
        "③ ARK 추적: 매일 08:00"
    )
    schedule.every().day.at("08:00").do(run_morning)
    schedule.every().day.at("09:00").do(run_kr)
    run_kr_shadowing()
    time.sleep(3)
    run_us_shadowing()
    time.sleep(3)
    run_ark_tracking()
    while True:
        schedule.run_pending()
        time.sleep(30)
