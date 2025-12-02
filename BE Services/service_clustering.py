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

def get_zone_name(lat, lon):
    """
    Xác định tên zone dựa trên tọa độ trung tâm cụm
    """
    # Định nghĩa các vùng địa lý chính với phạm vi mở rộng
    
    # Bắc Mỹ (bao gồm Alaska, Canada, USA, Mexico)
    if lat >= 15 and lat <= 75 and lon >= -170 and lon <= -50:
        return "North America"
    
    # Nam Mỹ (từ Colombia đến Argentina)
    elif lat >= -60 and lat <= 15 and lon >= -85 and lon <= -30:
        return "South America"
    
    # Châu Âu (bao gồm Nga châu Âu)
    elif lat >= 35 and lat <= 75 and lon >= -10 and lon <= 60:
        return "Europe"
    
    # Châu Phi
    elif lat >= -40 and lat <= 40 and lon >= -20 and lon <= 55:
        return "Africa"
    
    # Châu Á (bao gồm Trung Quốc, Ấn Độ, Trung Á)
    elif lat >= -10 and lat <= 55 and lon >= 55 and lon <= 145:
        return "Asia"
    
    # Đông Nam Á & Indonesia
    elif lat >= -15 and lat <= 25 and lon >= 90 and lon <= 145:
        return "Southeast Asia"
    
    # Nhật Bản - Hàn Quốc - Đông Bắc Á
    elif lat >= 25 and lat <= 50 and lon >= 120 and lon <= 150:
        return "East Asia"
    
    # Châu Đại Dương (Australia, New Zealand, Pacific Islands)
    elif lat >= -50 and lat <= 0 and lon >= 110 and lon <= 180:
        return "Oceania"
    elif lat >= -50 and lat <= 0 and lon >= -180 and lon <= -160:
        return "Oceania"
    
    # Thái Bình Dương (Trung tâm)
    elif lat >= -30 and lat <= 30 and lon >= 150 and lon <= -120:
        return "Pacific Ocean"
    elif lat >= -30 and lat <= 30 and lon >= -180 and lon <= -120:
        return "Pacific Ocean"
    
    # Đại Tây Dương
    elif lat >= -60 and lat <= 70 and lon >= -60 and lon <= 20:
        return "Atlantic Ocean"
    
    # Ấn Độ Dương
    elif lat >= -60 and lat <= 30 and lon >= 20 and lon <= 120:
        return "Indian Ocean"
    
    # Bắc Cực
    elif lat >= 70:
        return "Arctic Region"
    
    # Nam Cực
    elif lat <= -60:
        return "Antarctic Region"
    
    # Trường hợp còn lại - với tên mô tả rõ ràng hơn
    else:
        # Xác định hướng địa lý
        ns = "North" if lat > 0 else "South"
        ew = "East" if lon > 0 else "West"
        
        # Xác định khu vực đại dương gần nhất
        if abs(lon) > 30 and abs(lon) < 120:
            ocean = "Indian Ocean"
        elif abs(lon) >= 120:
            ocean = "Pacific Ocean"
        else:
            ocean = "Atlantic Ocean"
        
        return f"{ocean} - {ns}{ew} ({lat:.1f}, {lon:.1f})"

def run_clustering():
    session = SessionLocal()
    try:
        print(f"[{datetime.now()}] Bắt đầu Clustering (K-Means)...")
        
        # 1. Lấy toàn bộ dữ liệu (hoặc giới hạn 10.000 bản ghi mới nhất để nhanh)
        # Chỉ cần lấy Lat, Lon để phân cụm địa lý
        query = session.query(Earthquake.id, Earthquake.latitude, Earthquake.longitude)
        df = pd.read_sql(query.statement, session.bind)
        
        if len(df) < N_CLUSTERS:
            print("-> Không đủ dữ liệu để phân cụm.")
            return

        # 2. Chuẩn bị dữ liệu train
        X = df[['latitude', 'longitude']].values
        
        # 3. Train K-Means
        kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
        kmeans.fit(X)
        
        # Lấy nhãn (0, 1, 2...) gán lại vào DataFrame
        df['cluster_label'] = kmeans.labels_
        
        # 4. Update ngược lại vào Database (Batch Update)
        
        print("-> Đang cập nhật nhãn cụm vào Database...")
        for index, row in df.iterrows():
            session.query(Earthquake).filter(Earthquake.id == row['id']).update(
                {"cluster_label": int(row['cluster_label'])}
            )
            
        # 5. Lưu thông tin tâm cụm vào bảng cluster_info (Optional)
        # Xóa thông tin cụm cũ
        session.query(ClusterInfo).delete()
        session.commit()
        
        centers = kmeans.cluster_centers_ # Tọa độ tâm cụm [lat, lon]
        #cluster_results = []
        for i, center in enumerate(centers):
            # Logic giả định rủi ro dựa trên số lượng điểm trong cụm
            count_in_cluster = len(df[df['cluster_label'] == i])
            risk = "High" if count_in_cluster > len(df)/N_CLUSTERS else "Medium"
            
            zone_name = get_zone_name(center[0], center[1])
            c_info = ClusterInfo(
                cluster_id=i,
                cluster_name=zone_name,
                centroid_lat=float(center[0]),
                centroid_lon=float(center[1]),
                risk_level=risk,
                updated_at=datetime.utcnow()
            )
            session.add(c_info)

        session.commit()
        print("-> Phân cụm hoàn thành & Đã lưu.")

    except Exception as e:
        print(f"Lỗi trong quá trình phân cụm: {e}")
        session.rollback()
    finally:
        session.close()

def run_clustering_service():
    """Chạy service clustering định kỳ"""
    print(f"Dịch vụ Phân cụm Bắt đầu (Chạy mỗi {SLEEP_TIME}s)...")
    while True:
        run_clustering()
        time.sleep(SLEEP_TIME)

def run_clustering_with_params(custom_start=None, custom_end=None, n_clusters=None):
    """
    Chạy clustering với tham số tùy chỉnh
    
    Args:
        custom_start (str): Ngày bắt đầu theo format YYYY-MM-DD (optional)
        custom_end (str): Ngày kết thúc theo format YYYY-MM-DD (optional)
        n_clusters (int): Số lượng cụm (optional)
    """
    session = SessionLocal()
    try:
        # Sử dụng n_clusters custom hoặc mặc định
        num_clusters = n_clusters if n_clusters else N_CLUSTERS
        
        print(f"[{datetime.now()}] Đang chạy Phân cụm Tùy chỉnh với {num_clusters} cụm...")
        
        # 1. Lấy dữ liệu theo khoảng thời gian (nếu có)
        if custom_start and custom_end:
            start_date = datetime.strptime(custom_start, '%Y-%m-%d')
            end_date = datetime.strptime(custom_end, '%Y-%m-%d')
            
            print(f"-> Khoảng thời gian tùy chỉnh: {custom_start} đến {custom_end}")
            query = session.query(Earthquake.id, Earthquake.latitude, Earthquake.longitude).filter(
                Earthquake.time >= start_date,
                Earthquake.time <= end_date
            )
        else:
            print("-> Sử dụng tất cả dữ liệu có sẵn")
            query = session.query(Earthquake.id, Earthquake.latitude, Earthquake.longitude)
        
        # Đọc vào DataFrame
        df = pd.read_sql(query.statement, session.bind)
        
        if len(df) < num_clusters:
            print(f"-> Không đủ dữ liệu để tạo {num_clusters} cụm. Có: {len(df)}")
            return {"error": f"Cần ít nhất {num_clusters} điểm dữ liệu, nhưng chỉ có {len(df)}"}

        # 2. Chuẩn bị dữ liệu train
        X = df[['latitude', 'longitude']].values
        
        # 3. Train K-Means với số cluster tùy chỉnh
        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
        kmeans.fit(X)
        
        # Lấy nhãn gán lại vào DataFrame
        df['cluster_label'] = kmeans.labels_
        
        # 4. Update ngược lại vào Database
        print("-> Đang cập nhật nhãn cụm vào Database...")
        for index, row in df.iterrows():
            session.query(Earthquake).filter(Earthquake.id == row['id']).update(
                {"cluster_label": int(row['cluster_label'])}
            )
            
        # 5. Lưu thông tin tâm cụm
        # Xóa thông tin cụm cũ
        session.query(ClusterInfo).delete()
        session.commit()
        centers = kmeans.cluster_centers_
        cluster_results = []
        
        for i, center in enumerate(centers):
            count_in_cluster = len(df[df['cluster_label'] == i])
            risk = "High" if count_in_cluster > len(df)/num_clusters else "Medium"
            
            zone_name = get_zone_name(center[0], center[1])
            c_info = ClusterInfo(
                cluster_id=i,
                cluster_name=zone_name,
                centroid_lat=float(center[0]),
                centroid_lon=float(center[1]),
                risk_level=risk,
                updated_at=datetime.utcnow()
            )
            session.add(c_info)
            
            cluster_results.append({
                "cluster_id": i,
                "name": zone_name,
                "centroid": [float(center[0]), float(center[1])],
                "risk_level": risk,
                "earthquake_count": count_in_cluster
            })

        session.commit()
        print(f"-> Phân cụm Tùy chỉnh hoàn thành với {num_clusters} cụm.")
        
        return {
            "status": "success",
            "clusters": cluster_results,
            "total_earthquakes": len(df),
            "n_clusters": num_clusters,
            "time_range": f"{custom_start} to {custom_end}" if custom_start and custom_end else "all_data"
        }

    except Exception as e:
        print(f"Lỗi trong quá trình phân cụm tùy chỉnh: {e}")
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'custom' and len(sys.argv) >= 4:
            # Clustering với custom time range
            start_date = sys.argv[2]
            end_date = sys.argv[3]
            n_clusters = int(sys.argv[4]) if len(sys.argv) >= 5 else N_CLUSTERS
            
            result = run_clustering_with_params(start_date, end_date, n_clusters)
            print("Kết quả phân cụm:", result)
            
        elif command == 'clusters' and len(sys.argv) >= 3:
            # Clustering với số cụm tùy chỉnh (all data)
            n_clusters = int(sys.argv[2])
            result = run_clustering_with_params(n_clusters=n_clusters)
            print("Kết quả phân cụm:", result)
            
        elif command == 'run':
            # Chạy clustering một lần với config mặc định
            run_clustering()
            
        elif command == 'service':
            # Chạy service định kỳ
            run_clustering_service()
            
        else:
            print("Usage:")
            print("  python service_clustering.py custom 2024-01-01 2024-12-01 [n_clusters]")
            print("  python service_clustering.py clusters 8")
            print("  python service_clustering.py run")
            print("  python service_clustering.py service")
            print("")
            print("Examples:")
            print("  python service_clustering.py custom 2024-01-01 2024-12-01 7")
            print("  python service_clustering.py clusters 10")
    else:
        # Chạy service thường xuyên (mặc định)
        run_clustering_service()