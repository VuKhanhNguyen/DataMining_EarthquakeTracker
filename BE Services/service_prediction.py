import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from database import SessionLocal, Earthquake, Prediction

SLEEP_TIME = 300 # 5 phút

def run_prediction():
    session = SessionLocal()
    try:
        print(f"[{datetime.now()}] Running Prediction Model...")
        
        # 1. Lấy dữ liệu lịch sử để train
        # Lấy 1000 trận gần nhất
        query = session.query(Earthquake.magnitude, Earthquake.depth, Earthquake.latitude, Earthquake.longitude)\
                       .order_by(Earthquake.time.desc()).limit(1000)
        df = pd.read_sql(query.statement, session.bind)
        
        if len(df) < 50:
            print("-> Not enough data to train model.")
            return

        # 2. Feature Engineering đơn giản (Demo)
        # Giả sử ta muốn dự đoán Magnitude dựa trên Depth và Vị trí (Lat/Lon)
        X = df[['depth', 'latitude', 'longitude']]
        y = df['magnitude']
        
        # 3. Train Model (Random Forest)
        model = RandomForestRegressor(n_estimators=50, random_state=42)
        model.fit(X, y)
        
        # 4. Dự báo cho tương lai (Giả định input cho ngày mai)
        # Lấy trung bình vị trí của các trận gần nhất để dự báo rủi ro tại khu vực đó
        avg_depth = df['depth'].mean()
        avg_lat = df['latitude'].mean()
        avg_lon = df['longitude'].mean()
        
        # Input cho mô hình
        next_input = [[avg_depth, avg_lat, avg_lon]] # Scikit-learn yêu cầu mảng 2D
        
        # Predict
        pred_mag = model.predict(next_input)[0]
        confidence = 0.85 # Giả định confidence score
        
        # Logic Classification (Phân loại rủi ro dựa trên độ lớn dự báo)
        risk_label = "Safe"
        if pred_mag >= 5.0:
            risk_label = "Moderate Risk"
        if pred_mag >= 7.0:
            risk_label = "High Risk - Warning"

        # 5. Lưu kết quả vào bảng predictions
        target_date = datetime.now().date() + timedelta(days=1) # Dự báo cho ngày mai
        
        # Lưu kết quả số (Regression)
        pred_reg = Prediction(
            prediction_type="REGRESSION",
            predicted_value=float(pred_mag),
            confidence_score=confidence,
            target_date=target_date,
            model_name="RandomForest_v1"
        )
        
        # Lưu kết quả nhãn (Classification)
        pred_class = Prediction(
            prediction_type="CLASSIFICATION",
            predicted_label=risk_label,
            confidence_score=confidence,
            target_date=target_date,
            model_name="RuleBased_v1"
        )
        
        session.add(pred_reg)
        session.add(pred_class)
        session.commit()
        
        print(f"-> Prediction saved: {pred_mag:.2f} mag | Risk: {risk_label}")

    except Exception as e:
        print(f"Error in prediction: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    print("Service Prediction Started (Run every 5 mins)...")
    while True:
        run_prediction()
        time.sleep(SLEEP_TIME)