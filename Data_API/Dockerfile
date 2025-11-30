# Data_API/Dockerfile
FROM python:3.11-slim
WORKDIR /app

# Sao chép tất cả các thư mục cần thiết cho API (bao gồm cả BE Services)
COPY ./Data_API /app/Data_API/
COPY ./BE_Services /app/BE_Services/

# Cài đặt thư viện: FastAPI, Uvicorn, Pandas, SQLAlchemy, Scikit-learn, etc.
# LƯU Ý: Đây là danh sách tối thiểu, bạn cần bổ sung các thư viện khác (vd: scikit-learn, numpy)
# mà các file trong 'BE Services' sử dụng.
RUN pip install --no-cache-dir fastapi uvicorn[standard] pandas sqlalchemy scikit-learn

# Mở port mặc định của API (8000)
EXPOSE 8000

# Lệnh mặc định (chạy Uvicorn)
CMD ["uvicorn", "Data_API.api_server:app", "--host", "0.0.0.0", "--port", "8000"]