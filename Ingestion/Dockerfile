# Ingestion/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY ./Data_API /app/Data_API/
COPY ./Ingestion /app/Ingestion/

# Cài đặt thư viện: requests, SQLAlchemy và DRIVER MySQL (pymysql)
RUN pip install --no-cache-dir \
    requests \
    sqlalchemy \
    pymysql    # <<< ĐÃ THÊM DRIVER CHO MYSQL

CMD ["python", "-u", "Ingestion/data_ingestion.py"]