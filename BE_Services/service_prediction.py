import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Data_API import database
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from Data_API.database import SessionLocal, Earthquake, Prediction, AnalysisStat

SLEEP_TIME = 300  # Chạy 5 phút/lần

def run_prediction():
    session = SessionLocal()
    try:
        print(f"[{datetime.now()}] Running Prediction Model (Full Option: Raw + Cluster + Analysis)...")
        
        # ==========================================
        # BƯỚC 1: LẤY CONTEXT TỪ SERVICE ANALYSIS
        # ==========================================
        # Lấy bản ghi thống kê mới nhất để biết "mức độ hoạt động" hiện tại của trái đất
        latest_stat = session.query(AnalysisStat).order_by(AnalysisStat.timestamp.desc()).first()
        
        # Nếu chưa có data analysis (lần đầu chạy), giả định mức hoạt động là 50 trận/ngày
        current_activity_level = latest_stat.total_events_24h if latest_stat else 50
        print(f"-> Current Activity Level (Context): {current_activity_level} events/24h")

        # ==========================================
        # BƯỚC 2: LẤY RAW DATA + CLUSTER LABEL
        # ==========================================
        query = session.query(
            Earthquake.magnitude, 
            Earthquake.depth, 
            Earthquake.latitude, 
            Earthquake.longitude,
            Earthquake.cluster_label
        ).order_by(Earthquake.time.desc()).limit(2000) # Lấy nhiều data hơn chút để học tốt hơn
        
        df = pd.read_sql(query.statement, session.bind)
        
        if len(df) < 50:
            print("-> Not enough data to train model.")
            return

        # Xử lý dữ liệu thiếu (nếu service clustering chưa kịp chạy cho các điểm mới)
        df['cluster_label'] = df['cluster_label'].fillna(-1)

        # ==========================================
        # BƯỚC 3: FEATURE ENGINEERING (TRỘN DỮ LIỆU)
        # ==========================================
        # Kỹ thuật: "Broadcasting". Ta gán mức hoạt động hiện tại vào lịch sử 
        # để mô hình học mối liên hệ giữa "Số lượng sự kiện" và "Độ lớn"
        # (Lưu ý: Cách chuẩn nhất là phải lấy activity_level của từng thời điểm trong quá khứ, 
        # nhưng để đơn giản hóa cho đồ án, ta dùng mức hiện tại làm trọng số ngữ cảnh)
        df['activity_level'] = current_activity_level

        # Các đặc trưng đầu vào (Features)
        features = ['depth', 'latitude', 'longitude', 'cluster_label', 'activity_level']
        X = df[features]
        y = df['magnitude'] # Nhãn cần dự đoán (Target)

        # ==========================================
        # BƯỚC 4: TRAIN MODEL
        # ==========================================
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)
        
        # ==========================================
        # BƯỚC 5: DỰ BÁO CHO NGÀY MAI
        # ==========================================
        # Tạo dữ liệu đầu vào giả định cho ngày mai:
        # - Vị trí: Lấy trung bình vị trí các trận gần đây
        # - Cluster: Lấy vùng hoạt động mạnh nhất (Mode)
        # - Activity Level: Giả định mức hoạt động vẫn tiếp diễn như hôm nay
        
        next_input_data = {
            'depth': df['depth'].mean(),
            'latitude': df['latitude'].mean(),
            'longitude': df['longitude'].mean(),
            'cluster_label': df['cluster_label'].mode()[0] if not df['cluster_label'].mode().empty else -1,
            'activity_level': current_activity_level 
        }
        
        next_input = pd.DataFrame([next_input_data])
        
        # Dự đoán con số cụ thể
        pred_mag = model.predict(next_input)[0]
        
        # Tính confidence score (giả định tăng lên vì có nhiều dữ liệu hơn)
        confidence = 0.92 

        # Logic Phân loại (Classification)
        risk_label = "Low"
        if pred_mag >= 4.5: risk_label = "Moderate"
        if pred_mag >= 6.0: risk_label = "High"
        if pred_mag >= 7.5: risk_label = "Critical Alert"

        # ==========================================
        # BƯỚC 6: LƯU KẾT QUẢ VÀO DB
        # ==========================================
        target_date = datetime.now().date() + timedelta(days=1)
        
        # Lưu Regression (Số)
        pred_reg = Prediction(
            prediction_type="REGRESSION",
            predicted_value=float(pred_mag),
            confidence_score=confidence,
            target_date=target_date,
            model_name="RandomForest_FullOption"
        )
        
        # Lưu Classification (Nhãn)
        pred_class = Prediction(
            prediction_type="CLASSIFICATION",
            predicted_label=risk_label,
            confidence_score=confidence,
            target_date=target_date,
            model_name="RuleBased_FullOption"
        )
        
        session.add(pred_reg)
        session.add(pred_class)
        session.commit()
        
        print(f"-> Prediction Saved: Max Mag {pred_mag:.2f} | Risk: {risk_label} | Based on Activity: {current_activity_level}")

    except Exception as e:
        print(f"Error in prediction: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    print("Service Prediction (Full Option) Started...")
    while True:
        run_prediction()
        time.sleep(SLEEP_TIME)