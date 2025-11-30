# Ingestion/Dockerfile
# Sử dụng Python 3.11 chính thức
FROM python:3.11-slim

# Thiết lập thư mục làm việc bên trong container
WORKDIR /app

# Sao chép các thư mục cần thiết
# Copy Data_API ra ngoài Ingestion để path import Data_API.database hoạt động
COPY ./Data_API /app/Data_API/
COPY ./Ingestion /app/Ingestion/

# Cài đặt thư viện: requests, SQLAlchemy
# Bạn sẽ cần bổ sung thư viện cho database (vd: psycopg2-binary cho Postgres)
RUN pip install --no-cache-dir requests sqlalchemy

# Lệnh mặc định khi container chạy
CMD ["python", "Ingestion/data_ingestion.py"]