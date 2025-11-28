import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Data_API import database
import time
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from datetime import datetime
from Data_API.database import SessionLocal, Earthquake, ClusterInfo

# Chạy 1 ngày 1 lần. Để test nhanh có thể sửa thành 60s
SLEEP_TIME = 86400 
N_CLUSTERS = 5 # Số lượng cụm muốn chia (ví dụ: chia thế giới thành 5 vùng hoạt động)

def run_clustering():
    session = SessionLocal()
    try:
        print(f"[{datetime.now()}] Starting Clustering (K-Means)...")
        
        # 1. Lấy toàn bộ dữ liệu (hoặc giới hạn 10.000 bản ghi mới nhất để nhanh)
        # Chỉ cần lấy Lat, Lon để phân cụm địa lý
        query = session.query(Earthquake.id, Earthquake.latitude, Earthquake.longitude)
        df = pd.read_sql(query.statement, session.bind)
        
        if len(df) < N_CLUSTERS:
            print("-> Not enough data points to cluster.")
            return

        # 2. Chuẩn bị dữ liệu train
        X = df[['latitude', 'longitude']].values
        
        # 3. Train K-Means
        kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
        kmeans.fit(X)
        
        # Lấy nhãn (0, 1, 2...) gán lại vào DataFrame
        df['cluster_label'] = kmeans.labels_
        
        # 4. Update ngược lại vào Database (Batch Update)
        # Cách này hơi chậm nếu data lớn, nhưng an toàn cho code đơn giản
        print("-> Updating cluster labels to Database...")
        for index, row in df.iterrows():
            session.query(Earthquake).filter(Earthquake.id == row['id']).update(
                {"cluster_label": int(row['cluster_label'])}
            )
            
        # 5. Lưu thông tin tâm cụm vào bảng cluster_info (Optional)
        # Xóa thông tin cụm cũ
        session.query(ClusterInfo).delete()
        
        centers = kmeans.cluster_centers_ # Tọa độ tâm cụm [lat, lon]
        for i, center in enumerate(centers):
            # Logic giả định rủi ro dựa trên số lượng điểm trong cụm
            count_in_cluster = len(df[df['cluster_label'] == i])
            risk = "High" if count_in_cluster > len(df)/N_CLUSTERS else "Medium"
            
            c_info = ClusterInfo(
                cluster_id=i,
                cluster_name=f"Zone {i+1}",
                centroid_lat=float(center[0]),
                centroid_lon=float(center[1]),
                risk_level=risk,
                updated_at=datetime.utcnow()
            )
            session.add(c_info)

        session.commit()
        print("-> Clustering completed & Saved.")

    except Exception as e:
        print(f"Error during clustering: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    print(f"Service Clustering Started (Run every {SLEEP_TIME}s)...")
    while True:
        run_clustering()
        time.sleep(SLEEP_TIME)