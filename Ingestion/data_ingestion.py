import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Data_API import database
import requests
import time
from datetime import datetime
from Data_API.database import SessionLocal, init_db, Earthquake
from sqlalchemy.exc import SQLAlchemyError

# URL API của USGS (Lấy tất cả động đất trong 24h qua)
USGS_API_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
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
        print(f"-> Successfully processed {len(features)} records.")
        
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Database Error: {e}")
    except Exception as e:
        print(f"General Error: {e}")
    finally:
        session.close()

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
    run_service()