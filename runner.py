"""
GitHub Actions용 실행 스크립트
schedule 없이 1회만 실행하고 종료
"""
import sys
import os

import stock_shadowing as s

s.TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
s.TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

mode = sys.argv[1] if len(sys.argv) > 1 else "all"

if mode == "kr":
    s.run_kr_shadowing()
elif mode == "us_and_ark":
    s.run_us_shadowing()
    s.run_ark_tracking()
else:
    s.run_kr_shadowing()
    s.run_us_shadowing()
    s.run_ark_tracking()
