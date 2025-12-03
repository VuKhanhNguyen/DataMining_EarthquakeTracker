import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Data_API import database
import requests
import time
from datetime import datetime, timedelta
from Data_API.database import SessionLocal, init_db, Earthquake
from sqlalchemy.exc import SQLAlchemyError

# URL API của USGS
USGS_API_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson"
SLEEP_TIME = 300  # 5 phút (300 giây)

def fetch_usgs_data():
    try:
        print(f"[{datetime.now()}] Fetching data from USGS...")
        response = requests.get(USGS_API_URL)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching data: Status {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception during fetch: {e}")
        return None
def fetch_historical_data():
    """
    Lấy dữ liệu lịch sử từ nhiều nguồn USGS để có đủ dữ liệu phân tích
    """
    urls = [
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson",
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson"
    ]
    
    all_data = []
    
    for url in urls:
        try:
            print(f"[{datetime.now()}] Đang lấy dữ liệu từ {url}...")
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if data and 'features' in data:
                    all_data.extend(data['features'])
                    print(f"-> Lấy được {len(data['features'])} records")
        except Exception as e:
            print(f"Error fetching {url}: {e}")
    
    return {'features': all_data} if all_data else None

def fetch_custom_range_data(start_date="2025-01-01", end_date="2025-12-01"):
    """
    Lấy dữ liệu trong khoảng thời gian tùy chỉnh từ USGS
    """
    # USGS Query API với custom date range
    query_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        'format': 'geojson',
        'starttime': start_date,
        'endtime': end_date,
        'minmagnitude': 1.0  # Lọc động đất từ 1.0 trở lên
        # Không có limit để lấy tất cả dữ liệu
    }
    
    try:
        print(f"[{datetime.now()}] Đang lấy dữ liệu khoảng thời gian tùy chỉnh: {start_date} đến {end_date}")
        response = requests.get(query_url, params=params)
        if response.status_code == 200:
            data = response.json()
            print(f"-> Lấy được {len(data.get('features', []))} records cho khoảng thời gian tùy chỉnh")
            return data
        else:
            print(f"Lỗi: Status {response.status_code}")
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu khoảng thời gian tùy chỉnh: {e}")
    
    return None

def load_specific_year_data():
    """
    Load dữ liệu từ 1/1/2025 đến 1/12/2025 (11 tháng đầu năm)
    """
    print("=== ĐANG TẢI DỮ LIỆU NĂM 2025 (Tháng 1 đến Tháng 11) ===")
    init_db()
    
    # Chia nhỏ thành các tháng để tránh timeout và lấy tất cả dữ liệu
    months = [
        ("2025-01-01", "2025-02-01"),
        ("2025-02-01", "2025-03-01"), 
        ("2025-03-01", "2025-04-01"),
        ("2025-04-01", "2025-05-01"),
        ("2025-05-01", "2025-06-01"),
        ("2025-06-01", "2025-07-01"),
        ("2025-07-01", "2025-08-01"),
        ("2025-08-01", "2025-09-01"),
        ("2025-09-01", "2025-10-01"),
        ("2025-10-01", "2025-11-01"),
        ("2025-11-01", "2025-12-01")
    ]
    
    total_records = 0
    for start, end in months:
        print(f"\n--- Loading {start} to {end} ---")
        data = fetch_custom_range_data(start, end)
        if data:
            process_and_save(data)
            total_records += len(data.get('features', []))
        time.sleep(2)  # Tránh spam USGS API
    
    print(f"✅ Đã tải {total_records} records từ 1/1/2025 đến 1/12/2025")
    
def process_and_save(data):
    if not data or 'features' not in data:
        return

    session = SessionLocal()
    count_new = 0
    count_update = 0

    try:
        features = data['features']
        for item in features:
            props = item['properties']
            geom = item['geometry']
            
            quake_id = item['id']
            
            # Chuyển đổi timestamp (ms) sang datetime
            # Lưu ý: USGS trả về milisecond, Python cần second
            time_dt = datetime.fromtimestamp(props['time'] / 1000.0) if props['time'] else None
            updated_dt = datetime.fromtimestamp(props['updated'] / 1000.0) if props['updated'] else None
            
            # Tạo object Earthquake
            earthquake = Earthquake(
                id=quake_id,
                place=props.get('place'),
                magnitude=props.get('mag'),
                mag_type=props.get('magType'),
                time=time_dt,
                updated=updated_dt,
                url=props.get('url'),
                status=props.get('status'),
                tsunami=props.get('tsunami'),
                # Geometry coordinates: [longitude, latitude, depth]
                longitude=geom['coordinates'][0],
                latitude=geom['coordinates'][1],
                depth=geom['coordinates'][2]
            )

            # Dùng merge: Nếu ID tồn tại -> Update, Nếu chưa -> Insert
            # Điều này xử lý tốt việc USGS cập nhật lại thông tin động đất cũ
            session.merge(earthquake)
            count_new += 1 # Ở đây đếm chung processed, tách insert/update cần check db trước hơi tốn resource

        session.commit()
        print(f"-> Thành công xử lý {len(features)} records.")
        
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Lỗi Cơ sở dữ liệu: {e}")
    except Exception as e:
        print(f"General Error: {e}")
    finally:
        session.close()

def load_jan_to_dec_2025():
    """
    Lấy toàn bộ dữ liệu từ 1/1/2025 đến 1/12/2025 (không giới hạn records)
    """
    print("=== LOADING COMPLETE DATA: 1/1/2025 to 1/12/2025 ===")
    init_db()
    
    # Load toàn bộ khoảng thời gian một lần
    print("Fetching complete year data without limit...")
    data = fetch_custom_range_data("2025-01-01", "2025-12-01")
    
    if data and data.get('features'):
        total_records = len(data['features'])
        print(f"-> Received {total_records} earthquake records")
        process_and_save(data)
        print(f"✅ Successfully loaded {total_records} records from 1/1/2025 to 1/12/2025")
    else:
        print("❌ Không nhận được dữ liệu hoặc lỗi API")
        # Fallback: try monthly chunks if single request fails
        print(" Thử tải theo từng tháng...")
        load_specific_year_data()

def run_initial_load():
    """
    Chạy 1 lần để tải dữ liệu lịch sử khi lần đầu setup
    """
    print("=== INITIAL HISTORICAL DATA LOAD ===")
    init_db()
    
    historical_data = fetch_historical_data()
    if historical_data:
        process_and_save(historical_data)
        print("✅ Đã tải dữ liệu lịch sử thành công!")
    else:
        print("❌ Không thể tải dữ liệu lịch sử")
def run_service():
    # Đảm bảo bảng đã được tạo trước khi chạy service
    init_db()
    print("Service Data Ingestion Started...")
    print("---------------------------------")

    while True:
        data = fetch_usgs_data()
        if data:
            process_and_save(data)
        
        print(f"Sleeping for {SLEEP_TIME} seconds...")
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'init':
            # Load dữ liệu lịch sử (tuần + tháng gần đây)
            run_initial_load()
        elif command == 'full2025':
            # Load toàn bộ từ 1/1/2025 đến 1/12/2025 (không giới hạn)
            load_jan_to_dec_2025()
        elif command == 'year2025':
            # Load theo chunks monthly
            load_specific_year_data()
        elif command.startswith('custom'):
            # Custom range: python data_ingestion.py custom 2025-01-01 2025-12-01
            if len(sys.argv) >= 4:
                start_date = sys.argv[2]
                end_date = sys.argv[3]
                print(f"Loading custom range: {start_date} to {end_date}")
                init_db()
                data = fetch_custom_range_data(start_date, end_date)
                if data:
                    process_and_save(data)
                    print(f"✅ Loaded {len(data.get('features', []))} records")
                else:
                    print("❌ Không thể tải dữ liệu khoảng thời gian tùy chỉnh")
            else:
                print("Usage: python data_ingestion.py custom YYYY-MM-DD YYYY-MM-DD")
        else:
            print("Commands: init, full2025, year2025, custom")
            print("  full2025 - Load complete 1/1 to 1/12/2025 without limit")
            print("  year2025 - Load by monthly chunks (safer for large data)")
    else:
        # Chạy service thường xuyên
        run_service()

if False:  # Old main block
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'init':
            # Load dữ liệu lịch sử (tuần + tháng gần đây)
            run_initial_load()
        elif command == 'year2025':
            # Load toàn bộ năm 2025
            load_specific_year_data()
        elif command.startswith('custom'):
            # Custom range: python data_ingestion.py custom 2025-01-01 2025-12-01
            if len(sys.argv) >= 4:
                start_date = sys.argv[2]
                end_date = sys.argv[3]
                print(f"Loading custom range: {start_date} to {end_date}")
                init_db()
                data = fetch_custom_range_data(start_date, end_date)
                if data:
                    process_and_save(data)
            else:
                print("Usage: python data_ingestion.py custom YYYY-MM-DD YYYY-MM-DD")
        else:
            print("Unknown command. Use: init, year2025, or custom")
    else:
        # Chạy service thường xuyên
        run_service()