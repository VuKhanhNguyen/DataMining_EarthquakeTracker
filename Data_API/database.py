from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Text, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os


# DATABASE_URL = "mysql+pymysql://root:Nvk_09112004@localhost/earthquake_db"
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://earthquake_user:earthquake_pass@db/earthquake_db")

engine = create_engine(DATABASE_URL, echo=False) # echo=True để xem log SQL
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Earthquake(Base):
    __tablename__ = "earthquakes"

    id = Column(String(50), primary_key=True) 
    place = Column(String(255))
    magnitude = Column(Float)
    mag_type = Column(String(20))
    time = Column(DateTime, index=True)        
    updated = Column(DateTime)                 
    latitude = Column(DECIMAL(10, 6))
    longitude = Column(DECIMAL(11, 6))
    depth = Column(Float)
    url = Column(String(255))
    status = Column(String(50))
    tsunami = Column(Integer, default=0)
    cluster_label = Column(Integer, nullable=True) 
    created_at = Column(DateTime, default=datetime.utcnow)

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Loại dự báo: 'REGRESSION' (số) hoặc 'CLASSIFICATION' (nhãn)
    prediction_type = Column(String(20)) 
    
    predicted_value = Column(Float, nullable=True)       
    predicted_label = Column(String(50), nullable=True)  
    confidence_score = Column(Float, nullable=True)    
    
    target_date = Column(Date)                        
    model_name = Column(String(50))                 

class AnalysisStat(Base):
    __tablename__ = "analysis_stats"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    analysis_start = Column(DateTime)
    analysis_end = Column(DateTime)
    total_events = Column(Integer)
    avg_magnitude = Column(Float)
    max_magnitude = Column(Float)
    min_magnitude = Column(Float)
    avg_depth = Column(Float)
    strongest_quake_id = Column(String(50)) # Có thể FK sang earthquakes.id

class ClusterInfo(Base):
    __tablename__ = "cluster_info"
    
    cluster_id = Column(Integer, primary_key=True)
    cluster_name = Column(String(100))
    centroid_lat = Column(DECIMAL(10, 6))
    centroid_lon = Column(DECIMAL(11, 6))
    risk_level = Column(String(50))
    updated_at = Column(DateTime, default=datetime.utcnow)

# Hàm để tạo bảng tự động nếu chưa có
def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    # Chạy file này trực tiếp để khởi tạo bảng lần đầu
    init_db()
    print("Database tables created successfully!")