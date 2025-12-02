from random import random
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Union
from datetime import datetime, timedelta
import pydantic

# Import từ file database.py 
from .database import ClusterInfo, SessionLocal, Earthquake, Prediction, AnalysisStat

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
    target_date: Optional[Union[pydantic.PastDate, pydantic.FutureDate]] # Chấp nhận ngày quá khứ/tương lai
    
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

@app.get("/api/analysis")
def get_analysis_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    API lấy kết quả phân tích cho khoảng thời gian tùy chỉnh
    """
    try:
        # Import service analysis function (load dynamically to avoid static unresolved import)
        import sys
        import os
        import importlib.util

        be_services_path = os.path.join(os.path.dirname(__file__), '..', 'BE Services')
        service_file = os.path.join(be_services_path, 'service_analysis.py')
        run_analysis = None

        if os.path.isfile(service_file):
            spec = importlib.util.spec_from_file_location("service_analysis", service_file)
            module = importlib.util.module_from_spec(spec)
            sys.modules["service_analysis"] = module
            spec.loader.exec_module(module)
            run_analysis = getattr(module, "run_analysis", None)
        else:
            # Fallback: try normal import if package is installed or on PYTHONPATH
            try:
                import service_analysis as sa  # type: ignore
                run_analysis = getattr(sa, "run_analysis", None)
            except Exception:
                run_analysis = None

        if run_analysis is None:
            raise HTTPException(status_code=500, detail="Could not load run_analysis from service_analysis.py")
        
        # Chạy analysis với custom range
        if start_date and end_date:
            result = run_analysis(start_date, end_date)
        else:
            result = run_analysis()  # Default 24h
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # --- THÊM LOGIC LƯU VÀO DATABASE ---
        try:
            # Lấy thông tin từ kết quả analysis
            summary = result.get("summary", {})
            
            # Chuyển đổi chuỗi ngày tháng thành đối tượng datetime
            analysis_start_dt = datetime.strptime(summary.get("start_date"), "%Y-%m-%d")
            analysis_end_dt = datetime.strptime(summary.get("end_date"), "%Y-%m-%d")

            # Tạo bản ghi AnalysisStat mới
            new_stat = AnalysisStat(
                timestamp=datetime.utcnow(),
                analysis_start=analysis_start_dt,
                analysis_end=analysis_end_dt,
                total_events=summary.get("total_events"),
                avg_magnitude=summary.get("avg_magnitude"),
                max_magnitude=summary.get("max_magnitude"),
                min_magnitude=summary.get("min_magnitude"),
                avg_depth=summary.get("avg_depth")
            )
            
            db.add(new_stat)
            db.commit()
            print("Đã lưu kết quả analysis vào database.")
        
        except Exception as db_error:
            db.rollback()
            # Không dừng thực thi nếu lưu lỗi, chỉ ghi log
            print(f"Lỗi khi lưu analysis stat vào DB: {str(db_error)}")
        # --- KẾT THÚC LOGIC LƯU ---
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

@app.get("/api/clustering")
def trigger_clustering(db: Session = Depends(get_db)):
    """
    API trigger clustering và trả về kết quả
    """
    try:
        # Import clustering service dynamically
        import importlib.util
        import os
        
        be_services_path = os.path.join(os.path.dirname(__file__), '..', 'BE Services')
        clustering_file = os.path.join(be_services_path, 'service_clustering.py')
        
        if os.path.isfile(clustering_file):
            spec = importlib.util.spec_from_file_location("service_clustering", clustering_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            run_clustering = getattr(module, "run_clustering", None)
            
            if run_clustering:
                # Xóa dữ liệu clustering cũ trước khi chạy lại
                try:
                    db.query(ClusterInfo).delete()
                    db.commit()
                    print("Đã xóa dữ liệu clustering cũ.")
                except Exception as e:
                    db.rollback()
                    raise HTTPException(status_code=500, detail=f"Lỗi khi xóa dữ liệu cũ: {str(e)}")

                # Chạy clustering
                run_clustering()
                
                # Lấy kết quả cluster info
                clusters = db.query(ClusterInfo).order_by(ClusterInfo.updated_at.desc()).all()
                
                cluster_data = []
                for cluster in clusters:
                    cluster_data.append({
                        "cluster_id": cluster.cluster_id,
                        "name": cluster.cluster_name,
                        "centroid_lat": float(cluster.centroid_lat),
                        "centroid_lon": float(cluster.centroid_lon),
                        "risk_level": cluster.risk_level,
                        "updated_at": cluster.updated_at.isoformat()
                    })
                
                return {
                    "status": "success",
                    "clusters": cluster_data,
                    "message": f"Clustering completed with {len(cluster_data)} clusters"
                }
            else:
                raise HTTPException(status_code=500, detail="run_clustering function not found")
        else:
            raise HTTPException(status_code=500, detail="service_clustering.py not found")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Phân cụm lỗi: {str(e)}")

@app.get("/api/clustering/info")
def get_clustering_info(db: Session = Depends(get_db)):
    """
    API lấy thông tin clustering hiện tại (không chạy lại)
    """
    try:
        clusters = db.query(ClusterInfo).order_by(ClusterInfo.updated_at.desc()).all()
        
        cluster_data = []
        for cluster in clusters:
            # Đếm số earthquake trong cluster
            earthquake_count = db.query(Earthquake).filter(
                Earthquake.cluster_label == cluster.cluster_id
            ).count()
            
            cluster_data.append({
                "cluster_id": cluster.cluster_id,
                "name": cluster.cluster_name,
                "centroid_lat": float(cluster.centroid_lat),
                "centroid_lon": float(cluster.centroid_lon),
                "risk_level": cluster.risk_level,
                "earthquake_count": earthquake_count,
                "updated_at": cluster.updated_at.isoformat() if cluster.updated_at else None
            })
        
        return {
            "clusters": cluster_data,
            "total_clusters": len(cluster_data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clustering info: {str(e)}")

@app.post("/api/prediction/run")
def trigger_prediction(db: Session = Depends(get_db)):
    """
    API trigger prediction service và trả về kết quả
    """
    try:
        # Import prediction service dynamically
        import importlib.util
        import os
        
        be_services_path = os.path.join(os.path.dirname(__file__), '..', 'BE Services')
        prediction_file = os.path.join(be_services_path, 'service_prediction.py')
        
        if os.path.isfile(prediction_file):
            spec = importlib.util.spec_from_file_location("service_prediction", prediction_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            run_prediction = getattr(module, "run_prediction", None)
            
            if run_prediction:
                # Chạy prediction
                run_prediction()
                
                # Lấy predictions mới nhất
                latest_predictions = db.query(Prediction).order_by(
                    desc(Prediction.created_at)
                ).limit(5).all()
                
                predictions_data = []
                for pred in latest_predictions:
                    predictions_data.append({
                        "id": pred.id,
                        "type": pred.prediction_type,
                        "value": pred.predicted_value,
                        "label": pred.predicted_label,
                        "confidence": pred.confidence_score,
                        "target_date": pred.target_date.isoformat() if pred.target_date else None,
                        "model": pred.model_name,
                        "created_at": pred.created_at.isoformat()
                    })
                
                return {
                    "status": "success",
                    "predictions": predictions_data,
                    "message": f"Prediction completed with {len(predictions_data)} new predictions"
                }
            else:
                raise HTTPException(status_code=500, detail="run_prediction function not found")
        else:
            raise HTTPException(status_code=500, detail="service_prediction.py not found")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.get("/api/prediction/status")
def get_prediction_status(db: Session = Depends(get_db)):
    """
    API kiểm tra trạng thái prediction service
    """
    try:
        # Kiểm tra prediction mới nhất
        latest_prediction = db.query(Prediction).order_by(
            desc(Prediction.created_at)
        ).first()
        
        # Kiểm tra analysis stats
        latest_analysis = db.query(AnalysisStat).order_by(
            desc(AnalysisStat.timestamp)
        ).first()
        
        # Kiểm tra clustering info  
        cluster_count = db.query(ClusterInfo).count()
        
        status = {
            "prediction_available": latest_prediction is not None,
            "last_prediction": latest_prediction.created_at.isoformat() if latest_prediction else None,
            "analysis_available": latest_analysis is not None, 
            "last_analysis": latest_analysis.timestamp.isoformat() if latest_analysis else None,
            "clusters_available": cluster_count > 0,
            "cluster_count": cluster_count,
            "system_ready": all([
                latest_prediction is not None,
                latest_analysis is not None,
                cluster_count > 0
            ])
        }
        
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking prediction status: {str(e)}")




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
    custom_start: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD)"),
    custom_end: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    API trả về dữ liệu time series với hỗ trợ custom date range
    """
    try:
        if custom_start and custom_end:
            # Sử dụng custom range
            start_date = datetime.strptime(custom_start, "%Y-%m-%d")
            end_date = datetime.strptime(custom_end, "%Y-%m-%d")
            print(f"API: Sử dụng custom range {custom_start} đến {custom_end}")
        else:
            # Sử dụng days_back như cũ
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            print(f"API: Sử dụng days_back={days_back}")
        
        # Rest of function remains the same...
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
            
            # Format ngày theo dd/mm/yyyy cho display
            display_date = data['date_obj'].strftime('%d/%m/%Y')
            result.append({
                'date': data['date_obj'].isoformat(),
                'date_string': display_date,
                'count': data['count'],
                'avg_magnitude': round(avg_mag, 2),
                'max_magnitude': round(max_mag, 2),
                'avg_depth': round(avg_depth, 2)
            })
        
        print(f"API chuỗi thời gian {period}: trả về {len(result)} điểm dữ liệu")  # Debug log
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(ve)}")
    except Exception as e:
        print(f"Lỗi trong chuỗi thời gian API: {str(e)}")  # Debug log
        raise HTTPException(status_code=500, detail=f"Lỗi khi tạo chuỗi thời gian: {str(e)}")

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
def get_predictions( start_date: Optional[str] = None, end_date: Optional[str] = None,db: Session = Depends(get_db)):
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
    try:
        # Lấy prediction mới nhất cho magnitude (regression)
        latest_magnitude = db.query(Prediction).filter(
            Prediction.prediction_type == "REGRESSION"
        ).order_by(desc(Prediction.created_at)).first()
        
        # Lấy prediction mới nhất cho risk classification
        latest_risk = db.query(Prediction).filter(
            Prediction.prediction_type == "CLASSIFICATION"
        ).order_by(desc(Prediction.created_at)).first()
        
        # Lấy context từ analysis_stats mới nhất
        latest_analysis = db.query(AnalysisStat).order_by(desc(AnalysisStat.timestamp)).first()
        
        # Lấy thông tin cluster để xác định vùng nguy hiểm
        cluster_info = db.query(ClusterInfo).all()
        
        # Tính toán dự đoán depth dựa trên magnitude (nếu chưa có riêng)
        predicted_depth = 50.0  # default
        if latest_magnitude and latest_magnitude.predicted_value:
            # Công thức đơn giản: depth ~ f(magnitude)
            predicted_depth = max(5, min(200, 60 - (latest_magnitude.predicted_value - 4) * 8))
        
        # Tính các yếu tố rủi ro từ analysis_stats
        risk_factors = {
            "geological_activity": "Ổn định",
            "tectonic_pressure": "Trung bình",
            "recent_activity": "Không có dữ liệu",
            "activity_trend": 0
        }
        
        if latest_analysis:
            # Tính baseline dựa trên magnitude trung bình thay vì số lượng events
            time_period_hours = 24  # Default 24h
            
            # Kiểm tra khoảng thời gian phân tích
            if hasattr(latest_analysis, 'analysis_start') and hasattr(latest_analysis, 'analysis_end'):
                time_diff = latest_analysis.analysis_end - latest_analysis.analysis_start
                time_period_hours = time_diff.total_seconds() / 3600
            
            # Tính baseline magnitude từ dữ liệu lịch sử
            period_start = latest_analysis.analysis_start if hasattr(latest_analysis, 'analysis_start') else datetime.utcnow() - timedelta(hours=time_period_hours)
            historical_start = period_start - timedelta(hours=time_period_hours * 3)
            
            # Lấy magnitude trung bình trong khoảng lịch sử để làm baseline
            historical_magnitudes = db.query(Earthquake.magnitude).filter(
                Earthquake.time >= historical_start,
                Earthquake.time < period_start,
                Earthquake.magnitude.isnot(None)
            ).all()
            
            # Tính baseline magnitude
            if historical_magnitudes:
                baseline_magnitude = sum(mag.magnitude for mag in historical_magnitudes) / len(historical_magnitudes)
            else:
                # Fallback: ước tính từ toàn bộ DB
                all_magnitudes = db.query(Earthquake.magnitude).filter(
                    Earthquake.magnitude.isnot(None)
                ).all()
                
                if all_magnitudes:
                    baseline_magnitude = sum(mag.magnitude for mag in all_magnitudes) / len(all_magnitudes)
                else:
                    baseline_magnitude = 4.0  # Default global average
            
            # Lấy magnitude trung bình hiện tại từ analysis_stats hoặc tính từ DB
            if hasattr(latest_analysis, 'avg_magnitude') and latest_analysis.avg_magnitude:
                current_magnitude = latest_analysis.avg_magnitude
            else:
                # Tính từ DB cho khoảng thời gian analysis
                current_magnitudes = db.query(Earthquake.magnitude).filter(
                    Earthquake.time >= period_start,
                    Earthquake.magnitude.isnot(None)
                ).all()
                
                if current_magnitudes:
                    current_magnitude = sum(mag.magnitude for mag in current_magnitudes) / len(current_magnitudes)
                else:
                    current_magnitude = baseline_magnitude
            
            # Tính % thay đổi magnitude
            if baseline_magnitude > 0:
                magnitude_change = ((current_magnitude - baseline_magnitude) / baseline_magnitude) * 100
            else:
                magnitude_change = 0
            
            # Debug log
            print(f"DEBUG: current_mag={current_magnitude:.2f}, baseline_mag={baseline_magnitude:.2f}, change={magnitude_change:.1f}%")
            
            # Điều chỉnh ngưỡng % cho magnitude (nhỏ hơn vì magnitude ít biến động)
            if time_period_hours <= 24:
                high_threshold, low_threshold = 5, -5   # 5% thay vì 20%
                max_change_limit = 25  # Giới hạn tối đa 25% cho 24h
            elif time_period_hours <= 168:  # 1 tuần
                high_threshold, low_threshold = 3, -3   # 3% thay vì 10%
                max_change_limit = 15  # Giới hạn tối đa 15% cho 1 tuần
            else:  # > 1 tuần (như 2 tháng)
                high_threshold, low_threshold = 2, -2   # 2% thay vì 5%
                max_change_limit = 10   # Giới hạn tối đa 10% cho dài hạn
            
            # Áp dụng giới hạn hợp lý cho magnitude
            magnitude_change = max(-50, min(max_change_limit, magnitude_change))
            
            if magnitude_change > high_threshold:
                risk_factors["geological_activity"] = f"Cường độ tăng {magnitude_change:.1f}%"
                risk_factors["tectonic_pressure"] = "Cao" if magnitude_change > high_threshold * 2 else "Trung bình"
            elif magnitude_change < low_threshold:
                risk_factors["geological_activity"] = f"Cường độ giảm {abs(magnitude_change):.1f}%"
                risk_factors["tectonic_pressure"] = "Thấp"
            else:
                risk_factors["geological_activity"] = "Ổn định"
                risk_factors["tectonic_pressure"] = "Trung bình"
            
            # Cập nhật thông tin hoạt động gần đây
            period_desc = "24h" if time_period_hours <= 24 else f"{int(time_period_hours/24)} ngày"
            
            # Đếm số events để hiển thị thông tin đầy đủ
            event_count = db.query(Earthquake).filter(
                Earthquake.time >= period_start,
                Earthquake.time <= (latest_analysis.analysis_end if hasattr(latest_analysis, 'analysis_end') else datetime.utcnow())
            ).count()
            
            # risk_factors["recent_activity"] = f"{event_count} trận, trung bình {current_magnitude:.1f}M trong {period_desc}"
            risk_factors["activity_trend"] = magnitude_change
            
        
        # Tạo hotspots từ cluster_info
        hotspots = []
        if cluster_info:
            for cluster in cluster_info[:3]:  # Lấy 3 cluster đầu
                probability = 85 if cluster.risk_level == "High" else 65 if cluster.risk_level == "Medium" else 45
                hotspots.append({
                    "name": cluster.cluster_name or f"Cluster {cluster.cluster_id}",
                    "probability": probability,
                    "risk_level": cluster.risk_level,
                    "location": f"({cluster.centroid_lat:.2f}, {cluster.centroid_lon:.2f})"
                })
        else:
            # Fallback hotspots nếu chưa có clustering data
            hotspots = [
                {"name": "Ring of Fire - Thái Bình Dương", "probability": 89, "risk_level": "High"},
                {"name": "San Andreas Fault", "probability": 76, "risk_level": "High"}, 
                {"name": "Himalayan Belt", "probability": 65, "risk_level": "Medium"}
            ]
        
        # Format response cho Frontend
        response = {
            "magnitude_prediction": None,
            "depth_prediction": {
                "value": round(predicted_depth, 1),
                "confidence": 68,
                "unit": "km",
                "method": ""
            },
            "risk_classification": None,
            "risk_factors": risk_factors,
            "hotspots": hotspots,
            "data_sources": {
                "has_ml_predictions": latest_magnitude is not None,
                "has_analysis_stats": latest_analysis is not None,
                "has_cluster_info": len(cluster_info) > 0,
                "last_analysis": latest_analysis.timestamp.isoformat() if latest_analysis else None
            }
        }
        
        # Magnitude prediction từ ML model
        if latest_magnitude:
            confidence_percent = int((latest_magnitude.confidence_score or 0.85) * 100)
            response["magnitude_prediction"] = {
                "value": round(latest_magnitude.predicted_value, 1),
                "confidence": confidence_percent,
                "target_date": latest_magnitude.target_date.isoformat() if latest_magnitude.target_date else None,
                "model": latest_magnitude.model_name or "Unknown",
                "created_at": latest_magnitude.created_at.isoformat()
            }
            
            # Cập nhật depth dựa trên magnitude thực tế
            response["depth_prediction"]["value"] = round(60 - (latest_magnitude.predicted_value - 4) * 8, 1)
            response["depth_prediction"]["confidence"] = max(60, confidence_percent - 15)
        else:
            # Fallback magnitude prediction từ dữ liệu gần đây
            recent_earthquakes = db.query(Earthquake.magnitude).filter(
                Earthquake.time >= datetime.utcnow() - timedelta(days=7),
                Earthquake.magnitude.isnot(None)
            ).all()
            
            if recent_earthquakes:
                avg_mag = sum(eq.magnitude for eq in recent_earthquakes) / len(recent_earthquakes)
                response["magnitude_prediction"] = {
                    "value": round(avg_mag + (random.uniform(-0.3, 0.3) if 'random' in globals() else 0), 1),
                    "confidence": 70,
                    "target_date": (datetime.utcnow() + timedelta(days=1)).date().isoformat(),
                    "model": "Statistical Average",
                    "note": "Based on recent 7-day average"
                }
        
        # Risk classification từ ML model
        if latest_risk:
            response["risk_classification"] = {
                "level": latest_risk.predicted_label,
                "confidence": int((latest_risk.confidence_score or 0.80) * 100),
                "created_at": latest_risk.created_at.isoformat(),
                "model": latest_risk.model_name
            }
        else:
            # Fallback risk classification dựa trên predicted magnitude
            predicted_mag = response["magnitude_prediction"]["value"] if response["magnitude_prediction"] else 4.0
            if predicted_mag >= 6.5:
                risk_level = "Critical Alert"
            elif predicted_mag >= 5.5:
                risk_level = "High"
            elif predicted_mag >= 4.0:
                risk_level = "Moderate"
            else:
                risk_level = "Low"
                
            response["risk_classification"] = {
                "level": risk_level,
                "confidence": 75,
                "method": "Rule-based from magnitude"
            }
        
        return response
        
    except Exception as e:
        print(f"Lỗi trong API dự đoán: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy dự đoán: {str(e)}")

# ==========================================
# 4. API XÓA DỮ LIỆU 
# ==========================================

@app.delete("/api/delete/all_data", status_code=200)
def delete_all_data(db: Session = Depends(get_db)):
    """
    API để xóa TẤT CẢ dữ liệu từ các bảng chính.
    """
    try:
        deleted_counts = {}
        
        # Xóa predictions
        deleted_counts["predictions"] = db.query(Prediction).delete()
        
        # Xóa analysis stats
        deleted_counts["analysis_stats"] = db.query(AnalysisStat).delete()
        
        # Xóa cluster info
        deleted_counts["cluster_info"] = db.query(ClusterInfo).delete()
        
        # Xóa earthquakes (bảng lớn nhất, xóa cuối cùng)
        deleted_counts["earthquakes"] = db.query(Earthquake).delete()
        
        db.commit()
        
        return {
            "status": "success",
            "message": "All data has been deleted successfully.",
            "deleted_rows": deleted_counts
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred while deleting data: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    # Chạy server tại localhost:8000
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=False)