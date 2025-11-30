import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Data_API import database
import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import desc
from Data_API.database import SessionLocal, Earthquake, AnalysisStat

SLEEP_TIME = 300 # 5 phút

def run_analysis():
    session = SessionLocal()
    try:
        print(f"[{datetime.now()}] Starting analysis...")
        
        # 1. Lấy dữ liệu trong 24h qua
        last_24h = datetime.utcnow() - timedelta(hours=24)
        query = session.query(Earthquake).filter(Earthquake.time >= last_24h)
        
        # Đọc vào Pandas DataFrame cho dễ tính toán
        df = pd.read_sql(query.statement, session.bind)
        
        if df.empty:
            print("-> No data in last 24h to analyze.")
            return

        # 2. Tính toán các chỉ số
        total_events = len(df)
        avg_mag = df['magnitude'].mean()
        max_mag = df['magnitude'].max()
        
        # Tìm ID của trận lớn nhất
        # iloc[0] lấy dòng đầu tiên sau khi sort
        strongest_quake = df.sort_values(by='magnitude', ascending=False).iloc[0]
        strongest_id = strongest_quake['id']

        # 3. Lưu vào bảng analysis_stats
        stat_entry = AnalysisStat(
            total_events_24h=int(total_events),
            avg_magnitude=float(avg_mag),
            max_magnitude=float(max_mag),
            strongest_quake_id=strongest_id,
            timestamp=datetime.utcnow()
        )
        
        session.add(stat_entry)
        session.commit()
        print(f"-> Analysis saved: {total_events} events, Max Mag: {max_mag}")

    except Exception as e:
        print(f"Error during analysis: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    print("Service Analysis Started (Run every 5 mins)...")
    while True:
        run_analysis()
        time.sleep(SLEEP_TIME)