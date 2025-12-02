# 🌍 DataMining_EarthquakeTracker

Một hệ thống toàn diện để giám sát, phân tích và dự đoán hoạt động động đất toàn cầu bằng cách sử dụng các kỹ thuật khai phá dữ liệu và học máy. Dự án này cung cấp một dashboard trực quan để theo dõi các trận động đất trong thời gian thực, phân tích xu hướng và dự đoán các sự kiện trong tương lai.


---

## ✨ Các tính năng chính

-   **📊 Dashboard trực quan**: Giao diện người dùng hiện đại được xây dựng bằng HTML, CSS và Chart.js để hiển thị dữ liệu động đất. Xem tại [FE/index.html](FE/index.html).
-   **🚀 API mạnh mẽ**: Backend FastAPI cung cấp các endpoint để lấy dữ liệu thống kê, phân tích, phân cụm và dự đoán. Xem tại [Data_API/api_server.py](Data_API/api_server.py).
-   **⛏️ Thu thập dữ liệu**: Tự động lấy dữ liệu động đất mới nhất. Xem tại [Ingestion/data_ingestion.py](Ingestion/data_ingestion.py).
-   **🧠 Phân tích & Học máy**:
    -   **Phân tích thống kê**: Cung cấp các số liệu thống kê tổng hợp về hoạt động động đất.
    -   **Phân cụm địa lý**: Sử dụng K-Means để xác định các cụm động đất và vùng rủi ro. Xem tại [BE Services/service_clustering.py](BE Services/service_clustering.py).
    -   **Mô hình dự đoán**: Dự đoán cường độ và rủi ro của các trận động đất trong tương lai.
-   **🐳 Triển khai với Docker**: Toàn bộ ứng dụng được đóng gói để dễ dàng thiết lập và triển khai với Docker Compose. Xem tại [docker/docker-compose.yml](docker/docker-compose.yml).

---

## 🛠️ Công nghệ sử dụng

-   **Backend**: Python, FastAPI, SQLAlchemy
-   **Phân tích dữ liệu**: Pandas, NumPy, Scikit-learn
-   **Frontend**: HTML, CSS, JavaScript, Chart.js
-   **Cơ sở dữ liệu**: MySQL
-   **Triển khai**: Docker, Docker Compose

---

## 📂 Cấu trúc thư mục

Đây là tổng quan về cấu trúc của dự án:

```bash
.
├── BE Services/
│   ├── service_analysis.py     # Script phân tích dữ liệu
│   ├── service_clustering.py   # Script phân cụm K-Means
│   └── service_prediction.py   # Script dự đoán
├── Data_API/
│   ├── api_server.py           # Máy chủ FastAPI chính
│   └── database.py             # Cấu hình và mô hình SQLAlchemy
├── docker/
│   ├── docker-compose.yml      # Định nghĩa các service cho Docker
│   ├── dockerFile              # Dockerfile đa giai đoạn
│   └── requirement.txt         # Các gói Python cần thiết
├── FE/
│   ├── frontend_app.py         # (Nếu có) Backend cho Frontend
│   ├── index.html              # Giao diện người dùng chính
│   ├── templatemo-graph-page.css # CSS cho trang
│   └── templatemo-graph-script.js # Logic JavaScript cho dashboard
├── Ingestion/
│   └── data_ingestion.py       # Script thu thập dữ liệu
└── README.md                   # Tài liệu dự án
```

---

## 🚀 Bắt đầu

Để chạy dự án này trên máy của bạn, hãy đảm bảo bạn đã cài đặt Docker và Docker Compose.

1.  **Clone repository:**
    ```sh
    git clone <your-repo-url>
    cd DataMining_EarthquakeTracker
    ```

2.  **Chạy với Docker Compose:**
    Lệnh này sẽ build các images và khởi chạy tất cả các services (database, backend, frontend, và các script xử lý dữ liệu).

    ```sh
    docker-compose up --build
    ```

3.  **Truy cập ứng dụng:**
    -   **Frontend Dashboard**: Mở trình duyệt và truy cập `http://localhost:8080`
    -   **Backend API Docs**: Truy cập `http://localhost:8000/docs` để xem tài liệu Swagger UI.

---

## 👥 Đội ngũ phát triển

| Tên thành viên         | Mã sinh viên   |
| :--------------------- | :------------- |
| *(Nguyễn Vũ Khanh)*    | 22115053122118 |
| *(Lê Thị Trà Giang)*   | 22115053122111 |
| *(Nguyễn Văn Phong)*   | 22115053122130 |
| *(Trần Công Hiếu)*     | 22115053122113 |

Cảm ơn bạn đã xem dự án này!