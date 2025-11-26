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

# ==========================================
# 3. API ENDPOINTS
# ==========================================

@app.get("/")
def read_root():
    return {"message": "Welcome to Earthquake Tracker API. Go to /docs for Swagger UI"}

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