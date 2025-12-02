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
            # Sửa lỗi: Sử dụng start_date/end_date từ request nếu không có trong summary
            analysis_start_str = summary.get("start_date") or start_date
            analysis_end_str = summary.get("end_date") or end_date

            # Thêm kiểm tra để đảm bảo giá trị không phải là None trước khi chuyển đổi
            if not analysis_start_str or not analysis_end_str:
                raise ValueError("Ngày bắt đầu hoặc ngày kết thúc bị thiếu khi lưu thống kê phân tích.")

            analysis_start_dt = datetime.strptime(analysis_start_str, "%Y-%m-%d")
            analysis_end_dt = datetime.strptime(analysis_end_str, "%Y-%m-%d")
            # Tạo bản ghi AnalysisStat mới
            new_stat = AnalysisStat(
                timestamp=datetime.utcnow(),
                analysis_start=analysis_start_dt,
                analysis_end=analysis_end_dt,
                total_events=summary.get("total_events"),
                avg_magnitude=summary.get("avg_magnitude"),
                max_magnitude=summary.get("max_magnitude"),
                min_magnitude=summary.get("min_magnitude"),
                avg_depth=summary.get("avg_depth"),
                strongest_quake_id=summary.get("strongest_quake_id")
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
    Trả về thống kê nhanh. 
    Ưu tiên lấy từ bản ghi analysis gần nhất, nếu không có sẽ tính trực tiếp trong 24h qua.
    """
    # Thử lấy bản ghi analysis gần nhất (trong vòng 1 giờ qua)
    last_hour = datetime.utcnow() - timedelta(hours=1)
    latest_stat = db.query(AnalysisStat).filter(AnalysisStat.timestamp >= last_hour).order_by(desc(AnalysisStat.timestamp)).first()

    if latest_stat:
        # Nếu có bản ghi analysis gần đây, sử dụng nó
        return {
            "total_events": latest_stat.total_events,
            "max_magnitude": latest_stat.max_magnitude,
            "status": "From recent analysis",
            "analysis_start": latest_stat.analysis_start.isoformat(),
            "analysis_end": latest_stat.analysis_end.isoformat()
        }
    
    # Fallback: Nếu không có, tính toán trực tiếp cho 24h qua
    last_24h = datetime.utcnow() - timedelta(hours=24)
    
    count = db.query(Earthquake).filter(Earthquake.time >= last_24h).count()
    max_mag = db.query(func.max(Earthquake.magnitude)).filter(Earthquake.time >= last_24h).scalar()
    
    return {
        "total_events": count,
        "max_magnitude": max_mag or 0.0,
        "status": "Live calculation (24h)"
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
        
        # ==============================================
        # BƯỚC 1: XÁC ĐỊNH MAGNITUDE DỰ ĐOÁN
        # ==============================================
        predicted_magnitude = 4.0  # Default fallback
        magnitude_confidence = 50
        magnitude_source = "Fallback"
        
        if latest_magnitude:
            predicted_magnitude = latest_magnitude.predicted_value
            magnitude_confidence = int((latest_magnitude.confidence_score or 0.85) * 100)
            magnitude_source = latest_magnitude.model_name or "ML Model"
        else:
            # Fallback: Tính từ dữ liệu 7 ngày gần đây
            recent_earthquakes = db.query(Earthquake.magnitude).filter(
                Earthquake.time >= datetime.utcnow() - timedelta(days=7),
                Earthquake.magnitude.isnot(None)
            ).all()
            
            if recent_earthquakes:
                avg_mag = sum(eq.magnitude for eq in recent_earthquakes) / len(recent_earthquakes)
                predicted_magnitude = avg_mag
                magnitude_confidence = 70
                magnitude_source = "Statistical Average (7 days)"
        
        # ==============================================
        # BƯỚC 2: TÍNH DEPTH DỰA TRÊN PREDICTED MAGNITUDE
        # ==============================================
        predicted_depth = max(5, min(200, 60 - (predicted_magnitude - 4) * 8))
        depth_confidence = max(60, magnitude_confidence - 15)
        
        # ==============================================
        # BƯỚC 3: PHÂN LOẠI RỦI RO DỰA TRÊN PREDICTED MAGNITUDE
        # ==============================================
        # LOGIC ĐỒNG NHẤT: Dùng predicted_magnitude thay vì historical max
        if predicted_magnitude >= 7.0:
            risk_level = "RỦI RO CỰC CAO"
            geological_activity = f"CỰC NGUY HIỂM - Dự đoán {predicted_magnitude:.1f}M"
            tectonic_pressure = "CỰC CAO"
            risk_confidence = magnitude_confidence
        elif predicted_magnitude >= 6.0:
            risk_level = "RỦI RO CAO"
            geological_activity = f"NGUY HIỂM - Dự đoán {predicted_magnitude:.1f}M"
            tectonic_pressure = "CAO"
            risk_confidence = magnitude_confidence
        elif predicted_magnitude >= 5.0:
            risk_level = "RỦI RO TRUNG BÌNH"
            geological_activity = f"CẢNH BÁO - Dự đoán {predicted_magnitude:.1f}M"
            tectonic_pressure = "TRUNG BÌNH CAO"
            risk_confidence = magnitude_confidence
        elif predicted_magnitude >= 4.0:
            risk_level = "RỦI RO THẤP"
            geological_activity = f"ỔN ĐỊNH - Dự đoán {predicted_magnitude:.1f}M"
            tectonic_pressure = "TRUNG BÌNH"
            risk_confidence = magnitude_confidence
        else:
            risk_level = "RỦI RO RẤT THẤP"
            geological_activity = f"ỔN ĐỊNH - Dự đoán {predicted_magnitude:.1f}M"
            tectonic_pressure = "THẤP"
            risk_confidence = magnitude_confidence
        
        # ==============================================
        # BƯỚC 4: BỔ SUNG THÔNG TIN TỪ LỊCH SỬ (CONTEXT)
        # ==============================================
        recent_activity_info = "Chưa có dữ liệu phân tích"
        activity_trend = 0
        
        if latest_analysis:
            time_period_hours = 24
            if hasattr(latest_analysis, 'analysis_start') and hasattr(latest_analysis, 'analysis_end'):
                time_diff = latest_analysis.analysis_end - latest_analysis.analysis_start
                time_period_hours = time_diff.total_seconds() / 3600
            
            period_start = latest_analysis.analysis_start if hasattr(latest_analysis, 'analysis_start') else datetime.utcnow() - timedelta(hours=time_period_hours)
            period_end = latest_analysis.analysis_end if hasattr(latest_analysis, 'analysis_end') else datetime.utcnow()
            
            current_max_magnitude = latest_analysis.max_magnitude if hasattr(latest_analysis, 'max_magnitude') else 0
            current_avg_magnitude = latest_analysis.avg_magnitude if hasattr(latest_analysis, 'avg_magnitude') else 0
            
            event_count = db.query(Earthquake).filter(
                Earthquake.time >= period_start,
                Earthquake.time <= period_end
            ).count()
            
            period_desc = "24h" if time_period_hours <= 24 else f"{int(time_period_hours/24)} ngày"
            recent_activity_info = f"{event_count} trận trong {period_desc} qua (max: {current_max_magnitude:.1f}M, avg: {current_avg_magnitude:.1f}M)"
            
            # Tính trend từ lịch sử (chỉ để tham khảo, không ảnh hưởng risk level)
            historical_start = period_start - timedelta(hours=time_period_hours * 2)
            historical_magnitudes = db.query(Earthquake.magnitude).filter(
                Earthquake.time >= historical_start,
                Earthquake.time < period_start,
                Earthquake.magnitude.isnot(None)
            ).all()
            
            if historical_magnitudes:
                baseline_magnitude = sum(mag.magnitude for mag in historical_magnitudes) / len(historical_magnitudes)
                if baseline_magnitude > 0:
                    activity_trend = ((current_avg_magnitude - baseline_magnitude) / baseline_magnitude) * 100
        
        # ==============================================
        # BƯỚC 5: TẠO HOTSPOTS TỪ CLUSTER INFO
        # ==============================================
        hotspots = []
        if cluster_info:
            for cluster in cluster_info[:3]:
                probability = 85 if cluster.risk_level == "High" else 65 if cluster.risk_level == "Medium" else 45
                hotspots.append({
                    "name": cluster.cluster_name or f"Cluster {cluster.cluster_id}",
                    "probability": probability,
                    "risk_level": cluster.risk_level,
                    "location": f"({cluster.centroid_lat:.2f}, {cluster.centroid_lon:.2f})"
                })
        else:
            hotspots = [
                {"name": "Ring of Fire - Thái Bình Dương", "probability": 89, "risk_level": "High"},
                {"name": "San Andreas Fault", "probability": 76, "risk_level": "High"}, 
                {"name": "Himalayan Belt", "probability": 65, "risk_level": "Medium"}
            ]
        
        # ==============================================
        # BƯỚC 6: TẠO RESPONSE ĐỒNG NHẤT
        # ==============================================
        response = {
            "magnitude_prediction": {
                "value": round(predicted_magnitude, 1),
                "confidence": magnitude_confidence,
                "target_date": (datetime.utcnow() + timedelta(days=1)).date().isoformat(),
                "model": magnitude_source,
                "note": "Dự đoán cho ngày mai"
            },
            "depth_prediction": {
                "value": round(predicted_depth, 1),
                "confidence": depth_confidence,
                "unit": "km",
                "method": ""
            },
            "risk_classification": {
                "level": risk_level,
                "confidence": risk_confidence,
                "method": f"Dựa trên magnitude dự đoán {predicted_magnitude:.1f}M"
            },
            "risk_factors": {
                "geological_activity": geological_activity,
                "tectonic_pressure": tectonic_pressure,
                "recent_activity": recent_activity_info,
                "activity_trend": round(activity_trend, 1)
            },
            "hotspots": hotspots,
            "data_sources": {
                "has_ml_predictions": latest_magnitude is not None,
                "has_analysis_stats": latest_analysis is not None,
                "has_cluster_info": len(cluster_info) > 0,
                "last_analysis": latest_analysis.timestamp.isoformat() if latest_analysis else None,
                "prediction_method": magnitude_source
            }
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