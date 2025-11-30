# FE/Dockerfile
FROM python:3.11-slim
WORKDIR /app

# Sao chép thư mục Frontend
COPY ./FE /app/FE/

# Cài đặt thư viện: Streamlit, Requests, Pandas, Plotly
RUN pip install --no-cache-dir streamlit requests pandas plotly

# Mở port mặc định của Streamlit (8501)
EXPOSE 8501

# Lệnh mặc định (chạy Streamlit)
CMD ["streamlit", "run", "FE/frontend_app.py", "--server.port=8501", "--server.address=0.0.0.0"]