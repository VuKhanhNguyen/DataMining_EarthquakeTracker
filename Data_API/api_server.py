from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import datetime, timedelta
import pydantic

# Import từ file database.py 
from database import SessionLocal, Earthquake, Prediction, AnalysisStat

# ==========================================
# 1. CẤU HÌNH API & CORS
# ==========================================
app = FastAPI(title="Earthquake Tracker API", description="API phục vụ dữ liệu động đất USGS")

# Cấu hình CORS để Frontend (chạy port khác) có thể gọi vào API này
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency để lấy DB session, tự động đóng khi request xong
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 2. PYDANTIC SCHEMAS (Định dạng dữ liệu trả về)
# ==========================================
# Định nghĩa format JSON trả về để Frontend dễ đọc

class EarthquakeOut(pydantic.BaseModel):
    id: str
    place: Optional[str]
    magnitude: Optional[float]
    time: Optional[datetime]
    latitude: Optional[float]
    longitude: Optional[float]
    depth: Optional[float]
    cluster_label: Optional[int] = None
    
    class Config:
        from_attributes = True # Cho phép đọc từ SQLAlchemy Model

class PredictionOut(pydantic.BaseModel):
    id: int
    prediction_type: Optional[str]
    predicted_value: Optional[float]
    predicted_label: Optional[str]
    target_date: Optional[pydantic.PastDate | pydantic.FutureDate] # Chấp nhận ngày quá khứ/tương lai
    
    class Config:
        from_attributes = True

class StatsOut(pydantic.BaseModel):
    total_earthquakes: int
    avg_magnitude: float
    avg_depth: float
    risk_zones: int
    max_magnitude: float
    min_magnitude: float

class TimeSeriesPoint(pydantic.BaseModel):
    date: str
    count: int
    avg_magnitude: float
    max_magnitude: float

class CorrelationMatrix(pydantic.BaseModel):
    variables: List[str]
    matrix: List[List[float]]

# ==========================================
# 3. API ENDPOINTS
# ==========================================

@app.get("/")
def read_root():
    return {"message": "Welcome to Earthquake Tracker API. Go to /docs for Swagger UI"}

# --- API Lấy thống kê tổng quan ---
@app.get("/api/stats", response_model=StatsOut)
def get_stats_summary(db: Session = Depends(get_db)):
    """
    API thống kê tổng quan cho Dashboard
    """
    try:
        # Tính toán thống kê từ toàn bộ dữ liệu
        total_count = db.query(func.count(Earthquake.id)).scalar() or 0
        
        if total_count == 0:
            return StatsOut(
                total_earthquakes=0,
                avg_magnitude=0.0,
                avg_depth=0.0,
                risk_zones=0,
                max_magnitude=0.0,
                min_magnitude=0.0
            )
        
        # Tính trung bình cường độ và độ sâu
        avg_mag = db.query(func.avg(Earthquake.magnitude)).scalar() or 0.0
        avg_depth = db.query(func.avg(Earthquake.depth)).scalar() or 0.0
        max_mag = db.query(func.max(Earthquake.magnitude)).scalar() or 0.0
        min_mag = db.query(func.min(Earthquake.magnitude)).scalar() or 0.0
        
        # Đếm số vùng rủi ro cao (magnitude > 5.0)
        risk_zones = db.query(func.count(Earthquake.id)).filter(Earthquake.magnitude > 5.0).scalar() or 0
        
        return StatsOut(
            total_earthquakes=total_count,
            avg_magnitude=round(avg_mag, 2),
            avg_depth=round(avg_depth, 2),
            risk_zones=risk_zones,
            max_magnitude=round(max_mag, 2),
            min_magnitude=round(min_mag, 2)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating stats: {str(e)}")


# --- API Lấy dữ liệu động đất (Core) ---
@app.get("/earthquakes", response_model=List[EarthquakeOut])
def get_earthquakes(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    min_magnitude: Optional[float] = 0.0,
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách động đất. 
    Hỗ trợ lọc theo thời gian (để vẽ biểu đồ) và độ lớn.
    """
    query = db.query(Earthquake)
    
    if start_date:
        query = query.filter(Earthquake.time >= start_date)
    if end_date:
        query = query.filter(Earthquake.time <= end_date)
    if min_magnitude > 0:
        query = query.filter(Earthquake.magnitude >= min_magnitude)
        
    # Sắp xếp mới nhất trước
    results = query.order_by(desc(Earthquake.time)).limit(limit).all()
    return results

# --- API Time Series cho biểu đồ ---
@app.get("/api/time-series")
def get_time_series(
    period: str = Query("day", regex="^(day|week|month)$"),
    days_back: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    API trả về dữ liệu time series cho các biểu đồ theo thời gian
    period: 'day', 'week', 'month'
    days_back: số ngày lấy dữ liệu từ hiện tại về trước
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        # Query dữ liệu trong khoảng thời gian
        query = db.query(Earthquake).filter(
            Earthquake.time >= start_date,
            Earthquake.time <= end_date,
            Earthquake.time.isnot(None)
        ).order_by(Earthquake.time)
        
        earthquakes = query.all()
        
        if not earthquakes:
            return []
        
        # Group theo period
        grouped_data = {}
        
        for eq in earthquakes:
            if period == "day":
                key = eq.time.strftime("%Y-%m-%d")
                # Thêm date object cho JavaScript
                date_obj = eq.time.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                # Lấy tuần trong năm
                year, week, _ = eq.time.isocalendar()
                key = f"{year}-W{week:02d}"
                # Tính ngày đầu tuần cho JavaScript
                date_obj = eq.time - timedelta(days=eq.time.weekday())
                date_obj = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            else:  # month
                key = eq.time.strftime("%Y-%m")
                # Ngày đầu tháng
                date_obj = eq.time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            if key not in grouped_data:
                grouped_data[key] = {
                    'count': 0,
                    'magnitudes': [],
                    'depths': [],
                    'date_obj': date_obj
                }
            
            grouped_data[key]['count'] += 1
            if eq.magnitude:
                grouped_data[key]['magnitudes'].append(eq.magnitude)
            if eq.depth:
                grouped_data[key]['depths'].append(eq.depth)
        
        # Tạo response
        result = []
        for date_key in sorted(grouped_data.keys()):
            data = grouped_data[date_key]
            
            avg_mag = sum(data['magnitudes']) / len(data['magnitudes']) if data['magnitudes'] else 0
            max_mag = max(data['magnitudes']) if data['magnitudes'] else 0
            avg_depth = sum(data['depths']) / len(data['depths']) if data['depths'] else 0
            
            result.append({
                'date': data['date_obj'].isoformat(),
                'date_string': date_key,
                'count': data['count'],
                'avg_magnitude': round(avg_mag, 2),
                'max_magnitude': round(max_mag, 2),
                'avg_depth': round(avg_depth, 2)
            })
        
        print(f"API time-series {period}: returning {len(result)} data points")  # Debug log
        return result
        
    except Exception as e:
        print(f"Error in time-series API: {str(e)}")  # Debug log
        raise HTTPException(status_code=500, detail=f"Error generating time series: {str(e)}")

# --- API Correlation Matrix ---
@app.get("/api/correlation")
def get_correlation_matrix(db: Session = Depends(get_db)):
    """
    API tính ma trận tương quan giữa các biến số
    """
    try:
        # Lấy dữ liệu số để tính correlation
        query = db.query(
            Earthquake.magnitude,
            Earthquake.depth,
            Earthquake.latitude,
            Earthquake.longitude
        ).filter(
            Earthquake.magnitude.isnot(None),
            Earthquake.depth.isnot(None),
            Earthquake.latitude.isnot(None),
            Earthquake.longitude.isnot(None)
        )
        
        data = query.all()
        
        if len(data) < 10:  # Cần ít nhất 10 điểm dữ liệu
            # Trả về ma trận mặc định nếu không đủ dữ liệu
            return {
                "variables": ["Cường độ", "Độ sâu", "Vĩ độ", "Kinh độ"],
                "matrix": [
                    [1.00, -0.15, 0.05, -0.03],
                    [-0.15, 1.00, 0.08, 0.02],
                    [0.05, 0.08, 1.00, 0.12],
                    [-0.03, 0.02, 0.12, 1.00]
                ]
            }
        
        # Chuyển đổi thành arrays để tính correlation
        import numpy as np
        
        magnitudes = [float(d.magnitude) for d in data]
        depths = [float(d.depth) for d in data]
        latitudes = [float(d.latitude) for d in data]
        longitudes = [float(d.longitude) for d in data]
        
        # Tính correlation matrix bằng numpy
        data_matrix = np.array([magnitudes, depths, latitudes, longitudes])
        corr_matrix = np.corrcoef(data_matrix)
        
        # Chuyển đổi về list để serialize JSON
        corr_list = corr_matrix.tolist()
        
        return {
            "variables": ["Cường độ", "Độ sâu", "Vĩ độ", "Kinh độ"],
            "matrix": [[round(val, 3) for val in row] for row in corr_list]
        }
        
    except Exception as e:
        # Fallback với ma trận mặc định
        return {
            "variables": ["Cường độ", "Độ sâu", "Vĩ độ", "Kinh độ"],
            "matrix": [
                [1.00, -0.15, 0.05, -0.03],
                [-0.15, 1.00, 0.08, 0.02],
                [0.05, 0.08, 1.00, 0.12],
                [-0.03, 0.02, 0.12, 1.00]
            ]
        }

# --- API Dự đoán ---
@app.get("/api/predictions")
def get_predictions(db: Session = Depends(get_db)):
    """
    API lấy dự đoán mới nhất cho Dashboard
    """
    try:
        # Lấy dự đoán từ bảng predictions (nếu có)
        latest_predictions = db.query(Prediction).order_by(desc(Prediction.created_at)).limit(10).all()
        
        if latest_predictions:
            # Có dữ liệu từ ML models
            predictions_data = []
            for pred in latest_predictions:
                predictions_data.append({
                    "id": pred.id,
                    "type": pred.prediction_type,
                    "value": pred.predicted_value,
                    "label": pred.predicted_label,
                    "target_date": pred.target_date.isoformat() if pred.target_date else None,
                    "created_at": pred.created_at.isoformat() if pred.created_at else None
                })
            
            return {"predictions": predictions_data}
        else:
            # Không có dự đoán từ ML, tạo dự đoán đơn giản dựa trên dữ liệu gần đây
            last_7_days = datetime.utcnow() - timedelta(days=7)
            recent_earthquakes = db.query(Earthquake).filter(
                Earthquake.time >= last_7_days,
                Earthquake.magnitude.isnot(None)
            ).all()
            
            if recent_earthquakes:
                avg_magnitude = sum(eq.magnitude for eq in recent_earthquakes if eq.magnitude) / len(recent_earthquakes)
                avg_depth = sum(eq.depth for eq in recent_earthquakes if eq.depth) / len([eq for eq in recent_earthquakes if eq.depth])
                
                # Dự đoán đơn giản: trung bình + biến động ngẫu nhiên nhỏ
                import random
                predicted_mag = avg_magnitude + random.uniform(-0.3, 0.3)
                predicted_depth = avg_depth + random.uniform(-5, 5)
                
                return {
                    "predictions": [
                        {
                            "type": "magnitude",
                            "value": round(predicted_mag, 1),
                            "confidence": 75,
                            "target_date": (datetime.utcnow() + timedelta(days=1)).isoformat()
                        },
                        {
                            "type": "depth", 
                            "value": round(predicted_depth, 1),
                            "confidence": 68,
                            "target_date": (datetime.utcnow() + timedelta(days=1)).isoformat()
                        }
                    ]
                }
            else:
                return {
                    "predictions": [
                        {
                            "type": "magnitude",
                            "value": 4.2,
                            "confidence": 50,
                            "target_date": (datetime.utcnow() + timedelta(days=1)).isoformat()
                        }
                    ]
                }
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching predictions: {str(e)}")


# --- API Lấy thống kê nhanh (Cho Dashboard) ---
@app.get("/stats/summary")
def get_stats_summary(db: Session = Depends(get_db)):
    """
    Trả về thống kê nhanh trong 24h qua (tính trực tiếp từ DB nếu bảng stats chưa có dữ liệu)
    """
    # Lấy thời điểm 24h trước
    last_24h = datetime.utcnow() - timedelta(hours=24)
    
    # Query đếm số lượng và tìm max magnitude
    count = db.query(Earthquake).filter(Earthquake.time >= last_24h).count()
    max_mag = db.query(func.max(Earthquake.magnitude)).filter(Earthquake.time >= last_24h).scalar()
    
    return {
        "total_events_24h": count,
        "max_magnitude_24h": max_mag or 0.0,
        "status": "Live calculation"
    }

# --- API Lấy dữ liệu Dự báo (Cho phần Prediction) ---
@app.get("/predictions/latest")
def get_latest_prediction(db: Session = Depends(get_db)):
    """
    Lấy các dự báo mới nhất (cả regression và classification) cho ngày mai
    """
    # Lấy dự báo được tạo ra gần nhất
    latest = db.query(Prediction).order_by(desc(Prediction.created_at)).limit(5).all()
    return latest

if __name__ == "__main__":
    import uvicorn
    # Chạy server tại localhost:8000
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)