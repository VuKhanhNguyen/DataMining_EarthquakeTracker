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

def run_analysis(custom_start=None, custom_end=None):
    """
    Chạy phân tích dữ liệu
    
    Args:
        custom_start (str): Ngày bắt đầu theo format YYYY-MM-DD (optional)
        custom_end (str): Ngày kết thúc theo format YYYY-MM-DD (optional)
    """
    session = SessionLocal()
    try:
        # Xác định khoảng thời gian phân tích
        if custom_start and custom_end:
            # Custom range từ frontend
            start_date = datetime.strptime(custom_start, '%Y-%m-%d')
            end_date = datetime.strptime(custom_end, '%Y-%m-%d')
            analysis_type = "CUSTOM_RANGE"
            print(f"[{datetime.now()}] Custom range analysis: {custom_start} to {custom_end}")
        else:
            # Default: 24h gần nhất
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(hours=24)
            analysis_type = "LAST_24H"
            print(f"[{datetime.now()}] Starting default 24h analysis...")
        
        # 1. Lấy dữ liệu trong khoảng thời gian
        query = session.query(Earthquake).filter(
            Earthquake.time >= start_date,
            Earthquake.time <= end_date
        )
        
        # Đọc vào Pandas DataFrame cho dễ tính toán
        df = pd.read_sql(query.statement, session.bind)
        
        if df.empty:
            print(f"-> No data in range {start_date} to {end_date} to analyze.")
            return {"error": "No data available for analysis"}

        # 2. Tính toán các chỉ số
        total_events = len(df)
        avg_mag = df['magnitude'].mean()
        max_mag = df['magnitude'].max()
        min_mag = df['magnitude'].min()
        
        # Phân tích độ sâu
        avg_depth = df['depth'].mean()
        max_depth = df['depth'].max()
        
        # Phân tích theo magnitude ranges
        mag_ranges = {
            'very_low': len(df[df['magnitude'] < 3.0]),
            'low': len(df[(df['magnitude'] >= 3.0) & (df['magnitude'] < 4.0)]),
            'moderate': len(df[(df['magnitude'] >= 4.0) & (df['magnitude'] < 5.0)]),
            'high': len(df[(df['magnitude'] >= 5.0) & (df['magnitude'] < 6.0)]),
            'very_high': len(df[df['magnitude'] >= 6.0])
        }
        
        # Tìm ID của trận lớn nhất
        strongest_quake = df.sort_values(by='magnitude', ascending=False).iloc[0]
        strongest_id = strongest_quake['id']
        
        # Phân tích xu hướng (nếu có đủ dữ liệu)
        activity_trend = "stable"
        geological_activity = "Trung bình"
        tectonic_pressure = "Trung bình"
        
        if total_events > 50:
            # Chia dữ liệu thành 2 nửa để so sánh xu hướng
            mid_point = len(df) // 2
            df_sorted = df.sort_values('time')
            # Chia dữ liệu thành 2 nửa để so sánh xu hướng
            first_half_avg = df_sorted.iloc[:mid_point]['magnitude'].mean()
            second_half_avg = df_sorted.iloc[mid_point:]['magnitude'].mean()
            
              # Thêm kiểm tra để tránh chia cho 0 và giá trị quá lớn
            if first_half_avg > 0:
                trend_change = ((second_half_avg - first_half_avg) / first_half_avg) * 100
                # Giới hạn trong khoảng -200% đến +200%
                trend_percentage = max(-200, min(200, trend_change))
                
                # Sử dụng absolute difference nếu % quá lớn
                if abs(trend_change) > 200:
                    abs_diff = abs(second_half_avg - first_half_avg)
                    if abs_diff > 1:
                        trend_percentage = 100 if second_half_avg > first_half_avg else -100
                    else:
                        trend_percentage = (abs_diff * 50) * (1 if second_half_avg > first_half_avg else -1)
            else:
                trend_percentage = 0
            
            if trend_percentage > 20:
                activity_trend = "increasing"
                geological_activity = f"Tăng mạnh ({trend_percentage:.0f}%)"
                tectonic_pressure = "Cao"
            elif trend_percentage > 5:
                activity_trend = "increasing"
                geological_activity = f"Tăng nhẹ ({trend_percentage:.0f}%)"
                tectonic_pressure = "Trung bình"
            elif trend_percentage < -20:
                activity_trend = "decreasing"
                geological_activity = f"Giảm mạnh ({abs(trend_percentage):.0f}%)"
                tectonic_pressure = "Thấp"
            elif trend_percentage < -5:
                activity_trend = "decreasing"
                geological_activity = f"Giảm nhẹ ({abs(trend_percentage):.0f}%)"
                tectonic_pressure = "Thấp"
            else:
                geological_activity = f"Ổn định ({trend_percentage:.0f}%)"

        # 3. Lưu vào bảng analysis_stats với thông tin mở rộng
        stat_entry = AnalysisStat(
            timestamp=datetime.utcnow(),
            analysis_start=start_date,
            analysis_end=end_date,
            total_events=int(total_events),
            avg_magnitude=float(avg_mag),
            max_magnitude=float(max_mag),
            min_magnitude=float(min_mag),
            avg_depth=float(avg_depth),
            strongest_quake_id=strongest_id
        )
        
        session.add(stat_entry)
        session.commit()
        
        print(f"-> Analysis saved: {total_events} events, Max Mag: {max_mag:.2f}")
        print(f"-> Trend: {activity_trend}, Activity: {geological_activity}")
        
        # Trả về kết quả để API có thể sử dụng
        return {
            "total_events": total_events,
            "avg_magnitude": round(avg_mag, 2),
            "max_magnitude": round(max_mag, 2),
            "min_magnitude": round(min_mag, 2),
            "avg_depth": round(avg_depth, 2),
            "max_depth": round(max_depth, 2),
            "strongest_quake_id": strongest_id,
            "magnitude_distribution": mag_ranges,
            "activity_trend": activity_trend,
            "geological_activity": geological_activity,
            "tectonic_pressure": tectonic_pressure,
            "analysis_type": analysis_type,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "recent_activity": f"{total_events} trận trong khoảng thời gian phân tích"
        }

    except Exception as e:
        print(f"Error during analysis: {e}")
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()

def run_analysis_service():
    """Chạy service analysis định kỳ (24h)"""
    print("Service Analysis Started (Run every 5 mins)...")
    while True:
        run_analysis()  # Chạy với default 24h
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'custom' and len(sys.argv) >= 4:
            # Chạy analysis cho custom range
            start_date = sys.argv[2]
            end_date = sys.argv[3]
            result = run_analysis(start_date, end_date)
            print("Analysis result:", result)
        elif command == 'service':
            # Chạy service định kỳ
            run_analysis_service()
        else:
            print("Usage:")
            print("  python service_analysis.py custom 2025-01-01 2025-12-01")
            print("  python service_analysis.py service")
    else:
        # Chạy service thường xuyên (mặc định)
        run_analysis_service()