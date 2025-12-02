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

def handle_missing_data(df, session):
    """
    Xử lý dữ liệu thiếu bằng cách lấy trung bình của dữ liệu trước và sau
    """
    # Sắp xếp theo thời gian để đảm bảo thứ tự
    df = df.sort_values('time').reset_index(drop=True)
    
    # 1. MAGNITUDE - Quan trọng nhất
    if df['magnitude'].isnull().any():
        mask_null_mag = df['magnitude'].isnull()
        
        for idx in df[mask_null_mag].index:
            # Tìm giá trị trước và sau
            prev_val = None
            next_val = None
            
            # Tìm giá trị không null trước đó
            for i in range(idx-1, -1, -1):
                if pd.notna(df.loc[i, 'magnitude']):
                    prev_val = df.loc[i, 'magnitude']
                    break
            
            # Tìm giá trị không null sau đó
            for i in range(idx+1, len(df)):
                if pd.notna(df.loc[i, 'magnitude']):
                    next_val = df.loc[i, 'magnitude']
                    break
            
            # Fill giá trị
            if prev_val is not None and next_val is not None:
                # Trung bình của trước và sau
                df.loc[idx, 'magnitude'] = (prev_val + next_val) / 2
            elif prev_val is not None:
                # Chỉ có giá trị trước
                df.loc[idx, 'magnitude'] = prev_val
            elif next_val is not None:
                # Chỉ có giá trị sau
                df.loc[idx, 'magnitude'] = next_val
            else:
                # Không có giá trị nào → dùng median toàn bộ
                df.loc[idx, 'magnitude'] = df['magnitude'].median()
    
    # 2. DEPTH - Tương tự với magnitude
    if df['depth'].isnull().any():
        mask_null_depth = df['depth'].isnull()
        
        for idx in df[mask_null_depth].index:
            prev_val = None
            next_val = None
            
            # Tìm depth trước đó
            for i in range(idx-1, -1, -1):
                if pd.notna(df.loc[i, 'depth']):
                    prev_val = df.loc[i, 'depth']
                    break
            
            # Tìm depth sau đó
            for i in range(idx+1, len(df)):
                if pd.notna(df.loc[i, 'depth']):
                    next_val = df.loc[i, 'depth']
                    break
            
            # Fill giá trị
            if prev_val is not None and next_val is not None:
                df.loc[idx, 'depth'] = (prev_val + next_val) / 2
            elif prev_val is not None:
                df.loc[idx, 'depth'] = prev_val
            elif next_val is not None:
                df.loc[idx, 'depth'] = next_val
            else:
                df.loc[idx, 'depth'] = df['depth'].median()
    
    # 3. LATITUDE/LONGITUDE - Nội suy tọa độ
    if df['latitude'].isnull().any() or df['longitude'].isnull().any():
        mask_null_coords = df['latitude'].isnull() | df['longitude'].isnull()
        
        for idx in df[mask_null_coords].index:
            # Xử lý latitude
            if pd.isnull(df.loc[idx, 'latitude']):
                prev_lat = None
                next_lat = None
                
                for i in range(idx-1, -1, -1):
                    if pd.notna(df.loc[i, 'latitude']):
                        prev_lat = df.loc[i, 'latitude']
                        break
                
                for i in range(idx+1, len(df)):
                    if pd.notna(df.loc[i, 'latitude']):
                        next_lat = df.loc[i, 'latitude']
                        break
                
                if prev_lat is not None and next_lat is not None:
                    df.loc[idx, 'latitude'] = (prev_lat + next_lat) / 2
                elif prev_lat is not None:
                    df.loc[idx, 'latitude'] = prev_lat
                elif next_lat is not None:
                    df.loc[idx, 'latitude'] = next_lat
                else:
                    # Thử parse từ place
                    place = df.loc[idx, 'place']
                    if pd.notna(place):
                        estimated_coords = estimate_coordinates_from_place(place)
                        if estimated_coords:
                            df.loc[idx, 'latitude'] = estimated_coords[0]
                            df.loc[idx, 'longitude'] = estimated_coords[1]
                            continue
                    # Không thể xác định → loại bỏ
                    print(f"Loại bỏ {idx}: Không thể xác định tọa độ")
                    df = df.drop(idx)
                    continue
            
            # Xử lý longitude tương tự
            if pd.isnull(df.loc[idx, 'longitude']):
                prev_lon = None
                next_lon = None
                
                for i in range(idx-1, -1, -1):
                    if pd.notna(df.loc[i, 'longitude']):
                        prev_lon = df.loc[i, 'longitude']
                        break
                
                for i in range(idx+1, len(df)):
                    if pd.notna(df.loc[i, 'longitude']):
                        next_lon = df.loc[i, 'longitude']
                        break
                
                if prev_lon is not None and next_lon is not None:
                    df.loc[idx, 'longitude'] = (prev_lon + next_lon) / 2
                elif prev_lon is not None:
                    df.loc[idx, 'longitude'] = prev_lon
                elif next_lon is not None:
                    df.loc[idx, 'longitude'] = next_lon
    
    # 4. CLUSTER_LABEL - Lấy cluster phổ biến nhất trong vùng lân cận
    if df['cluster_label'].isnull().any():
        mask_null_cluster = df['cluster_label'].isnull()
        
        for idx in df[mask_null_cluster].index:
            # Lấy 5 records trước và 5 records sau
            start_idx = max(0, idx-5)
            end_idx = min(len(df), idx+6)
            
            nearby_clusters = df.loc[start_idx:end_idx, 'cluster_label'].dropna()
            
            if not nearby_clusters.empty:
                # Lấy cluster phổ biến nhất
                most_common_cluster = nearby_clusters.mode()
                if not most_common_cluster.empty:
                    df.loc[idx, 'cluster_label'] = most_common_cluster.iloc[0]
                else:
                    df.loc[idx, 'cluster_label'] = -1
            else:
                df.loc[idx, 'cluster_label'] = -1
    
    # 5. TIME - Rất quan trọng, không thể fill
    if df['time'].isnull().any():
        print(f"Loại bỏ {df['time'].isnull().sum()} bản ghi không có dấu thời gian")
        df = df.dropna(subset=['time'])
    
    return df.reset_index(drop=True)

# Thêm hàm helper để fill dữ liệu NULL theo phương pháp interpolation
def interpolate_missing_values(df):
    """
    Hàm bổ sung: Sử dụng interpolation của pandas để fill các giá trị số
    """
    # Sắp xếp theo thời gian
    df = df.sort_values('time').reset_index(drop=True)
    
    # Interpolation cho các cột số
    numeric_cols = ['magnitude', 'depth', 'latitude', 'longitude']
    
    for col in numeric_cols:
        if col in df.columns and df[col].isnull().any():
            # Linear interpolation
            df[col] = df[col].interpolate(method='linear')
            
            # Fill các giá trị đầu/cuối nếu vẫn còn NULL
            df[col] = df[col].fillna(method='bfill').fillna(method='ffill')
    
    return df

def is_oceanic_ridge(lat, lon):
    """Kiểm tra có phải vùng sống núi dưới biển"""
    # Pacific Ridge
    if -60 < lat < 60 and -140 < lon < -100:
        return True
    # Mid-Atlantic Ridge  
    if -60 < lat < 70 and -30 < lon < -10:
        return True
    return False

def is_subduction_zone(lat, lon):
    """Kiểm tra vùng hút chìm (động đất sâu)"""
    # Ring of Fire - Pacific
    if (30 < lat < 60 and 140 < lon < 180) or \
       (-60 < lat < 10 and -180 < lon < -60):
        return True
    # Andes
    if -60 < lat < 10 and -80 < lon < -60:
        return True
    return False

def estimate_coordinates_from_place(place_string):
    """
    Ước lượng tọa độ từ mô tả địa điểm
    """
    if not place_string:
        return None
    
    # Dictionary các vùng địa lý chính
    location_mapping = {
        'Pacific': (0, -170),
        'California': (36, -120),
        'Alaska': (64, -153),
        'Japan': (36, 138),
        'Chile': (-30, -71),
        'Indonesia': (-5, 120),
        'Turkey': (39, 35),
        'Iran': (32, 53),
        'Mexico': (23, -102),
        'Philippines': (13, 122),
        'New Zealand': (-41, 174)
    }
    
    place_upper = place_string.upper()
    
    for region, coords in location_mapping.items():
        if region.upper() in place_upper:
            # Thêm nhiễu nhỏ để tránh trùng lặp chính xác
            lat = coords[0] + np.random.normal(0, 2)
            lon = coords[1] + np.random.normal(0, 3)
            return (lat, lon)
    
    return None

def run_prediction():
    session = SessionLocal()
    try:
        print(f"[{datetime.now()}] Đang chạy mô hình dự đoán: Raw + Cluster + Analysis)...")
        
        # ==========================================
        # BƯỚC 1: LẤY CONTEXT TỪ SERVICE ANALYSIS
        # ==========================================
        # Lấy bản ghi thống kê mới nhất để biết "mức độ hoạt động" hiện tại của trái đất
        latest_stat = session.query(AnalysisStat).order_by(AnalysisStat.timestamp.desc()).first()
        
        # Nếu chưa có data analysis (lần đầu chạy), giả định mức hoạt động là 50 trận/ngày
        current_activity_level = latest_stat.total_events_24h if latest_stat else 50
        print(f"-> Mức độ hoạt động: {current_activity_level} trận/24h")

        # ==========================================
        # BƯỚC 2: LẤY RAW DATA + CLUSTER LABEL
        # ==========================================
        query = session.query(
            Earthquake.magnitude, 
            Earthquake.depth, 
            Earthquake.latitude, 
            Earthquake.longitude,
            Earthquake.cluster_label,
            Earthquake.time,
            Earthquake.place
        ).order_by(Earthquake.time.desc()).limit(2000) # Lấy nhiều data hơn chút để học tốt hơn
        
        df = pd.read_sql(query.statement, session.bind)
        
        if len(df) < 50:
            print("-> Không đủ dữ liệu để huấn luyện mô hình.")
            create_error_predictions(session, f"Không đủ dữ liệu huấn luyện: chỉ có {len(df)} bản ghi")
            return

        # Xử lý dữ liệu thiếu bằng phương pháp interpolation
        print("-> Đang xử lý dữ liệu thiếu bằng phương pháp nội suy (interpolation)...")
        original_count = len(df)
        
        # Sử dụng cả 2 phương pháp
        df = handle_missing_data(df, session)  # Phương pháp trước-sau
        df = interpolate_missing_values(df)    # Phương pháp interpolation
        
        final_count = len(df)
        print(f"-> Dữ liệu đã xử lý: {original_count} -> {final_count} bản ghi")
        
        if len(df) < 50:
            print("-> Không đủ dữ liệu sau khi làm sạch.")
            create_error_predictions(session, f"Dữ liệu sau khi làm sạch quá ít: còn lại {final_count} bản ghi")
            return

        # ==========================================
        # BƯỚC 3: FEATURE ENGINEERING (TRỘN DỮ LIỆU)
        # ==========================================
        # Kỹ thuật: "Broadcasting". Ta gán mức hoạt động hiện tại vào lịch sử 
        # để mô hình học mối liên hệ giữa "Số lượng sự kiện" và "Độ lớn"
        # (Lưu ý: Cách chuẩn nhất là phải lấy activity_level của từng thời điểm trong quá khứ, 
        # nhưng để đơn giản hóa cho đồ án, ta dùng mức hiện tại làm trọng số ngữ cảnh)
        df['activity_level'] = current_activity_level

         # Features cho magnitude prediction
        mag_features = ['depth', 'latitude', 'longitude', 'cluster_label', 'activity_level']
        X_mag = df[mag_features]
        y_mag = df['magnitude']

        # Features cho depth prediction (riêng biệt)
        depth_features = ['magnitude', 'latitude', 'longitude', 'cluster_label', 'activity_level']
        X_depth = df[depth_features]
        y_depth = df['depth']
    
        # ==========================================
        # BƯỚC 4: TRAIN MODEL
        # ==========================================
         # Train model cho magnitude
        mag_model = RandomForestRegressor(n_estimators=100, random_state=42)
        mag_model.fit(X_mag, y_mag)
        # Train model cho depth
        depth_model = RandomForestRegressor(n_estimators=100, random_state=42)
        depth_model.fit(X_depth, y_depth)
        # ==========================================
        # BƯỚC 5: DỰ BÁO CHO NGÀY MAI
        # ==========================================
        # Tạo dữ liệu đầu vào giả định cho ngày mai:
        # - Vị trí: Lấy trung bình vị trí các trận gần đây
        # - Cluster: Lấy vùng hoạt động mạnh nhất (Mode)
        # - Activity Level: Giả định mức hoạt động vẫn tiếp diễn như hôm nay
        
        next_input_mag = {
            'depth': df['depth'].mean(),
            'latitude': df['latitude'].mean(),
            'longitude': df['longitude'].mean(),
            'cluster_label': df['cluster_label'].mode()[0] if not df['cluster_label'].mode().empty else -1,
            'activity_level': current_activity_level 
        }
        
        next_input_mag_df = pd.DataFrame([next_input_mag])
        
        # Dự đoán con số cụ thể
        pred_mag = mag_model.predict(next_input_mag_df)[0]
        mag_confidence = min(0.95, 0.7 + (len(df) / 5000))
        
        
         # Predict depth sử dụng predicted magnitude
        next_input_depth = pd.DataFrame([{
            'magnitude': pred_mag,  # Sử dụng predicted magnitude
            'latitude': df['latitude'].mean(),
            'longitude': df['longitude'].mean(),
            'cluster_label': df['cluster_label'].mode()[0] if not df['cluster_label'].mode().empty else -1,
            'activity_level': current_activity_level
        }])
        
        pred_depth = depth_model.predict(next_input_depth)[0]
        depth_confidence = max(0.6, mag_confidence - 0.15)
        
        # Tính confidence score (giả định tăng lên vì có nhiều dữ liệu hơn)
        confidence = 0.92 

        # Logic Phân loại (Classification)
        risk_label = "Low"
        risk_confidence = 0.75
        
        if pred_mag >= 7.0:
            risk_label = "Critical Alert"
            risk_confidence = 0.95
        elif pred_mag >= 6.0:
            risk_label = "High"
            risk_confidence = 0.9
        elif pred_mag >= 4.5:
            risk_label = "Moderate"
            risk_confidence = 0.85
        elif pred_mag >= 3.0:
            risk_label = "Low"
            risk_confidence = 0.8

        # ==========================================
        # BƯỚC 6: LƯU KẾT QUẢ VÀO DB
        # ==========================================
        target_date = datetime.now().date() + timedelta(days=1)
        
        # Magnitude Prediction
        pred_mag_reg = Prediction(
            prediction_type="REGRESSION",
            predicted_value=float(pred_mag),
            confidence_score=mag_confidence,
            target_date=target_date,
            model_name="RandomForest_Magnitude"
        )
        
        # Depth Prediction (riêng biệt)
        pred_depth_reg = Prediction(
            prediction_type="REGRESSION",
            predicted_value=float(pred_depth),
            confidence_score=depth_confidence,
            target_date=target_date,
            model_name="RandomForest_Depth"
        )
        
        # Risk Classification
        pred_risk_class = Prediction(
            prediction_type="CLASSIFICATION",
            predicted_label=risk_label,
            confidence_score=risk_confidence,
            target_date=target_date,
            model_name="EnhancedRuleBased_Risk"
        )
        
        session.add(pred_mag_reg)
        session.add(pred_depth_reg)
        session.add(pred_risk_class)
        session.commit()
        
        print(f"-> Enhanced Predictions Saved:")
        print(f"   Magnitude: {pred_mag:.2f} (conf: {mag_confidence:.0%})")
        print(f"   Depth: {pred_depth:.1f}km (conf: {depth_confidence:.0%})")
        print(f"   Risk: {risk_label} (conf: {risk_confidence:.0%})")
        print(f"   Context: {current_activity_level} events/24h")

    except Exception as e:
        print(f"Error in prediction: {e}")
        create_error_predictions(session, f"Model training error: {str(e)}")
        session.rollback()
    finally:
        session.close()
def create_error_predictions(session, error_message):
    """Tạo error predictions thay vì fallback data"""
    try:
        target_date = datetime.now().date() + timedelta(days=1)
        
        # Xóa predictions cũ
        session.query(Prediction).filter(Prediction.target_date == target_date).delete()
        
        # Tạo error prediction cho magnitude
        error_mag = Prediction(
            prediction_type="REGRESSION",
            predicted_value=None,
            confidence_score=0.0,
            target_date=target_date,
            model_name=f"ERROR_NO_DATA: {error_message}"
        )
        
        # Tạo error prediction cho depth
        error_depth = Prediction(
            prediction_type="REGRESSION", 
            predicted_value=None,
            confidence_score=0.0,
            target_date=target_date,
            model_name=f"ERROR_NO_DATA: {error_message}"
        )
        
        # Tạo error prediction cho risk
        error_risk = Prediction(
            prediction_type="CLASSIFICATION",
            predicted_label="ERROR - No Data Available",
            confidence_score=0.0,
            target_date=target_date,
            model_name=f"ERROR_NO_DATA: {error_message}"
        )
        
        session.add(error_mag)
        session.add(error_depth)
        session.add(error_risk)
        session.commit()
        
        print(f"-> ERROR PREDICTIONS created: {error_message}")
        
    except Exception as e:
        print(f"Error creating error predictions: {e}")
        session.rollback()
        
def run_prediction_service():
    """Chạy service prediction định kỳ"""
    print("Dịch vụ Dự đoán Bắt đầu...")
    while True:
        run_prediction()
        time.sleep(SLEEP_TIME)

def run_prediction_with_params(custom_start=None, custom_end=None, prediction_days=1, model_type="RandomForest"):
    """
    Chạy prediction với tham số tùy chỉnh
    
    Args:
        custom_start (str): Ngày bắt đầu dữ liệu training (YYYY-MM-DD)
        custom_end (str): Ngày kết thúc dữ liệu training (YYYY-MM-DD)
        prediction_days (int): Số ngày dự đoán vào tương lai
        model_type (str): Loại model ('RandomForest', 'Linear', 'SVM')
    """
    session = SessionLocal()
    try:
        print(f"[{datetime.now()}] Custom Prediction: {model_type} model, {prediction_days} days ahead")
        
        # Xác định khoảng thời gian training data
        if custom_start and custom_end:
            start_date = datetime.strptime(custom_start, '%Y-%m-%d')
            end_date = datetime.strptime(custom_end, '%Y-%m-%d')
            print(f"-> Khoảng thời gian dữ liệu: {custom_start} đến {custom_end}")
            
            query = session.query(
                Earthquake.magnitude, 
                Earthquake.depth, 
                Earthquake.latitude, 
                Earthquake.longitude,
                Earthquake.cluster_label,
                Earthquake.time,
                Earthquake.place
            ).filter(
                Earthquake.time >= start_date,
                Earthquake.time <= end_date
            ).order_by(Earthquake.time.desc())
        else:
            print("-> Sử dụng mặc định: 2000 bản ghi mới nhất")
            query = session.query(
                Earthquake.magnitude, 
                Earthquake.depth, 
                Earthquake.latitude, 
                Earthquake.longitude,
                Earthquake.cluster_label,
                Earthquake.time,
                Earthquake.place
            ).order_by(Earthquake.time.desc()).limit(2000)
        
        df = pd.read_sql(query.statement, session.bind)
        
        if len(df) < 50:
            error_msg = f"Dữ liệu huấn luyện không đủ: {len(df)} bản ghi"
            print(f"-> {error_msg}")
            return {"error": error_msg}

        # Xử lý dữ liệu thiếu
        print("-> Đang xử lý dữ liệu thiếu...")
        original_count = len(df)
        df = handle_missing_data(df, session)
        df = interpolate_missing_values(df)
        final_count = len(df)
        print(f"-> Dữ liệu đã xử lý: {original_count} -> {final_count} bản ghi")
        
        if len(df) < 50:
            error_msg = f"Dữ liệu không đủ sau khi làm sạch: {final_count} bản ghi"
            return {"error": error_msg}

        # Lấy activity level (có thể từ analysis hoặc tính từ data hiện tại)
        latest_stat = session.query(AnalysisStat).order_by(AnalysisStat.timestamp.desc()).first()
        current_activity_level = latest_stat.total_events_24h if latest_stat else len(df)
        
        df['activity_level'] = current_activity_level

        # Chọn model dựa trên tham số
        if model_type == "RandomForest":
            from sklearn.ensemble import RandomForestRegressor
            mag_model = RandomForestRegressor(n_estimators=100, random_state=42)
            depth_model = RandomForestRegressor(n_estimators=100, random_state=42)
        elif model_type == "Linear":
            from sklearn.linear_model import LinearRegression
            mag_model = LinearRegression()
            depth_model = LinearRegression()
        elif model_type == "SVM":
            from sklearn.svm import SVR
            mag_model = SVR(kernel='rbf', C=1.0, gamma='scale')
            depth_model = SVR(kernel='rbf', C=1.0, gamma='scale')
        else:
            return {"error": f"Loại mô hình không xác định: {model_type}"}

        # Training
        mag_features = ['depth', 'latitude', 'longitude', 'cluster_label', 'activity_level']
        depth_features = ['magnitude', 'latitude', 'longitude', 'cluster_label', 'activity_level']
        
        X_mag = df[mag_features]
        y_mag = df['magnitude']
        X_depth = df[depth_features]
        y_depth = df['depth']
        
        mag_model.fit(X_mag, y_mag)
        depth_model.fit(X_depth, y_depth)

        # Prediction cho nhiều ngày
        predictions_results = []
        
        for day_ahead in range(1, prediction_days + 1):
            target_date = datetime.now().date() + timedelta(days=day_ahead)
            
            # Input cho prediction
            next_input_mag = pd.DataFrame([{
                'depth': df['depth'].mean(),
                'latitude': df['latitude'].mean(),
                'longitude': df['longitude'].mean(),
                'cluster_label': df['cluster_label'].mode()[0] if not df['cluster_label'].mode().empty else -1,
                'activity_level': current_activity_level 
            }])
            
            pred_mag = mag_model.predict(next_input_mag)[0]
            mag_confidence = min(0.95, 0.7 + (len(df) / 5000))
            
            # Depth prediction
            next_input_depth = pd.DataFrame([{
                'magnitude': pred_mag,
                'latitude': df['latitude'].mean(),
                'longitude': df['longitude'].mean(),
                'cluster_label': df['cluster_label'].mode()[0] if not df['cluster_label'].mode().empty else -1,
                'activity_level': current_activity_level
            }])
            
            pred_depth = depth_model.predict(next_input_depth)[0]
            depth_confidence = max(0.6, mag_confidence - 0.15)
            
            # Risk classification
            risk_label = "Low"
            risk_confidence = 0.75
            
            if pred_mag >= 7.0:
                risk_label = "Critical Alert"
                risk_confidence = 0.95
            elif pred_mag >= 6.0:
                risk_label = "High"
                risk_confidence = 0.9
            elif pred_mag >= 4.5:
                risk_label = "Moderate"
                risk_confidence = 0.85
            
            # Lưu vào database
            pred_mag_reg = Prediction(
                prediction_type="REGRESSION",
                predicted_value=float(pred_mag),
                confidence_score=mag_confidence,
                target_date=target_date,
                model_name=f"{model_type}_Magnitude_Custom"
            )
            
            pred_depth_reg = Prediction(
                prediction_type="REGRESSION",
                predicted_value=float(pred_depth),
                confidence_score=depth_confidence,
                target_date=target_date,
                model_name=f"{model_type}_Depth_Custom"
            )
            
            pred_risk_class = Prediction(
                prediction_type="CLASSIFICATION",
                predicted_label=risk_label,
                confidence_score=risk_confidence,
                target_date=target_date,
                model_name=f"Enhanced_{model_type}_Risk"
            )
            
            session.add(pred_mag_reg)
            session.add(pred_depth_reg)
            session.add(pred_risk_class)
            
            predictions_results.append({
                "date": target_date.isoformat(),
                "magnitude": round(pred_mag, 2),
                "depth": round(pred_depth, 1),
                "risk": risk_label,
                "confidence": {
                    "magnitude": round(mag_confidence, 2),
                    "depth": round(depth_confidence, 2),
                    "risk": round(risk_confidence, 2)
                }
            })

        session.commit()
        
        print(f"-> Dự đoán Tùy chỉnh Hoàn thành:")
        print(f"   Mô hình: {model_type}")
        print(f"   Dữ liệu huấn luyện: {final_count} bản ghi")
        print(f"   Dự đoán: {prediction_days} ngày tới")
        
        return {
            "status": "success",
            "model_type": model_type,
            "training_records": final_count,
            "prediction_days": prediction_days,
            "predictions": predictions_results,
            "training_period": f"{custom_start} to {custom_end}" if custom_start and custom_end else "latest_data"
        }

    except Exception as e:
        print(f"Lỗi trong dự đoán tùy chỉnh: {e}")
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()
        
        
        
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'custom' and len(sys.argv) >= 4:
            # Custom prediction với time range
            start_date = sys.argv[2]
            end_date = sys.argv[3]
            prediction_days = int(sys.argv[4]) if len(sys.argv) >= 5 else 1
            model_type = sys.argv[5] if len(sys.argv) >= 6 else "RandomForest"
            
            result = run_prediction_with_params(start_date, end_date, prediction_days, model_type)
            print("Kết quả Dự đoán:", result)
            
        elif command == 'model' and len(sys.argv) >= 3:
            # Test model khác nhau
            model_type = sys.argv[2]
            prediction_days = int(sys.argv[3]) if len(sys.argv) >= 4 else 1
            
            result = run_prediction_with_params(prediction_days=prediction_days, model_type=model_type)
            print("Kết quả Dự đoán:", result)
            
        elif command == 'days' and len(sys.argv) >= 3:
            # Predict nhiều ngày
            prediction_days = int(sys.argv[2])
            result = run_prediction_with_params(prediction_days=prediction_days)
            print("Kết quả Dự đoán:", result)
            
        elif command == 'run':
            # Chạy prediction một lần
            run_prediction()
            
        elif command == 'service':
            # Chạy service định kỳ
            run_prediction_service()
            
        else:
            print("Usage:")
            print("  python service_prediction.py custom 2024-01-01 2024-12-01 [days] [model]")
            print("  python service_prediction.py model RandomForest [days]")
            print("  python service_prediction.py days 7")
            print("  python service_prediction.py run")
            print("  python service_prediction.py service")
            print("")
            print("Models: RandomForest, Linear, SVM")
            print("Examples:")
            print("  python service_prediction.py custom 2024-01-01 2024-12-01 3 SVM")
            print("  python service_prediction.py model Linear 5")
            print("  python service_prediction.py days 14")
    else:
        # Chạy service thường xuyên (mặc định)
        run_prediction_service()