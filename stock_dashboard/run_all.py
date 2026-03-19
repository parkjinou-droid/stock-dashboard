# run_all.py -- encoding: utf-8
import subprocess
import threading
import sys
import time
from notifier import StockWatcher

def run_dashboard():
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", "8501",
        "--server.headless", "false",
        "--browser.gatherUsageStats", "false",
    ])

def run_watcher():
    w = StockWatcher()
    w.start()

if __name__ == "__main__":
    print("=" * 50)
    print("  📊 주식 대시보드 + 알림 시스템 시작!")
    print("=" * 50)
    print("  🌐 대시보드: http://localhost:8501")
    print("  🔔 알림 기준: 변동률 ±2% 이상")
    print("  ⏹  종료: Ctrl+C")
    print("=" * 50)
    t = threading.Thread(target=run_watcher, daemon=True)
    t.start()
    time.sleep(2)
    try:
        run_dashboard()
    except KeyboardInterrupt:
        print("\n👋 종료!")
