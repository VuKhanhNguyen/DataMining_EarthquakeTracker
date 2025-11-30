import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

# ==========================================
# 1. CẤU HÌNH TRANG & CSS TÙY CHỈNH
# ==========================================
st.set_page_config(
    page_title="USGS Earthquake Tracker",
    page_icon="🌍",
    layout="wide"
)

# Chèn CSS tùy chỉnh (Hack CSS trong Streamlit)
st.markdown("""
<style>
    .main {
        background-color: #f5f5f5;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    h1, h2, h3 {
        color: #2c3e50;
    }
</style>
""", unsafe_allow_html=True)

# URL API (Trỏ về Terminal 2 đang chạy)
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

# ==========================================
# 2. HÀM GỌI API
# ==========================================
def get_earthquakes(days_back=30, min_mag=0):
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    try:
        response = requests.get(
            f"{API_URL}/earthquakes",
            params={"start_date": start_date, "min_magnitude": min_mag, "limit": 5000}
        )
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            if not df.empty:
                df['time'] = pd.to_datetime(df['time'])
            return df
        return pd.DataFrame()
    except:
        st.error("❌ Không kết nối được với API Server. Hãy kiểm tra Terminal 2!")
        return pd.DataFrame()

def get_predictions():
    try:
        response = requests.get(f"{API_URL}/predictions/latest")
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

# ==========================================
# 3. SIDEBAR (BỘ LỌC)
# ==========================================
st.sidebar.title("🛠️ Bộ lọc dữ liệu")
days_filter = st.sidebar.slider("Dữ liệu trong bao nhiêu ngày qua?", 1, 365, 30)
mag_filter = st.sidebar.slider("Độ lớn tối thiểu", 0.0, 9.0, 2.5)
st.sidebar.markdown("---")
st.sidebar.info("Hệ thống cập nhật mỗi 5 phút.")

# Load dữ liệu
df = get_earthquakes(days_back=days_filter, min_mag=mag_filter)

# ==========================================
# 4. GIAO DIỆN CHÍNH
# ==========================================
st.title("🌍 Dashboard Theo Dõi Động Đất (USGS)")

# --- Phần hiển thị KPI ---
if not df.empty:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng số trận", len(df))
    col2.metric("Độ lớn TB", f"{df['magnitude'].mean():.2f}")
    col3.metric("Trận lớn nhất", f"{df['magnitude'].max()}")
    col4.metric("Độ sâu TB", f"{df['depth'].mean():.1f} km")
else:
    st.warning("Chưa có dữ liệu. Vui lòng chạy data_ingestion.py trước!")

# --- Phần Tabs chức năng ---
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Bản đồ & Cluster", "📈 Phân tích Xu hướng", "📊 Tương quan", "🤖 Dự báo AI"])

with tab1:
    st.subheader("Bản đồ phân bố động đất")
    if not df.empty:
        # Nếu đã có cột cluster_label từ service clustering, dùng nó để tô màu
        color_col = 'cluster_label' if 'cluster_label' in df.columns and df['cluster_label'].notnull().any() else 'magnitude'
        
        fig_map = px.scatter_mapbox(
            df, 
            lat="latitude", 
            lon="longitude", 
            color=color_col,
            size="magnitude",
            hover_name="place",
            hover_data=["time", "depth", "magnitude"],
            zoom=1, 
            height=600,
            mapbox_style="open-street-map",
            color_continuous_scale=px.colors.sequential.Viridis,
            title="Vị trí và Phân cụm (Cluster) Động đất"
        )
        st.plotly_chart(fig_map, use_container_width=True)

with tab2:
    st.subheader("Phân tích theo thời gian")
    if not df.empty:
        # Chọn khung thời gian re-sampling
        resample_type = st.radio("Gom nhóm theo:", ["Ngày (D)", "Tuần (W)", "Tháng (M)"], horizontal=True)
        rule = 'D' if "Ngày" in resample_type else ('W' if "Tuần" in resample_type else 'M')
        
        # Resample dữ liệu
        df_resampled = df.set_index('time').resample(rule).agg({
            'id': 'count', 
            'magnitude': 'mean'
        }).rename(columns={'id': 'count'})
        
        # Chart 1: Line Chart (Số lượng & Trend)
        st.markdown("#### 1. Xu hướng số lượng theo thời gian")
        fig_line = px.line(df_resampled, y="count", title=f"Số lượng động đất theo {resample_type}")
        # Thêm trendline đơn giản (Rolling average)
        df_resampled['trend'] = df_resampled['count'].rolling(window=3).mean()
        fig_line.add_scatter(x=df_resampled.index, y=df_resampled['trend'], mode='lines', name='Trend (Moving Avg)')
        st.plotly_chart(fig_line, use_container_width=True)
        
        # Chart 2: Histogram Phân phối độ lớn
        st.markdown("#### 2. Phân phối độ lớn (Histogram)")
        fig_hist = px.histogram(df, x="magnitude", nbins=20, title="Tần suất các độ lớn")
        st.plotly_chart(fig_hist, use_container_width=True)

with tab3:
    st.subheader("Ma trận tương quan & Scatter")
    if not df.empty:
        col_left, col_right = st.columns(2)
        
        with col_left:
            # Chart 3: Scatter Plot (Depth vs Magnitude)
            fig_scatter = px.scatter(
                df, x="depth", y="magnitude", 
                color="magnitude", 
                title="Tương quan Độ sâu vs Độ lớn",
                trendline="ols" # Vẽ đường hồi quy tuyến tính
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
            
        with col_right:
            # Chart 4: Heatmap Correlation
            corr_matrix = df[['magnitude', 'depth', 'latitude', 'longitude']].corr()
            fig_corr = px.imshow(
                corr_matrix, 
                text_auto=True, 
                aspect="auto",
                color_continuous_scale='RdBu_r',
                title="Ma trận tương quan (Correlation Matrix)"
            )
            st.plotly_chart(fig_corr, use_container_width=True)

with tab4:
    st.subheader("🤖 Dự báo cho ngày mai (Prediction)")
    preds = get_predictions()
    
    if preds:
        # Tách danh sách thành Regression và Classification
        reg_pred = next((p for p in preds if p['prediction_type'] == 'REGRESSION'), None)
        class_pred = next((p for p in preds if p['prediction_type'] == 'CLASSIFICATION'), None)
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("### Dự báo Độ lớn Tối đa")
            if reg_pred:
                val = reg_pred['predicted_value']
                delta_color = "normal" if val < 5 else "inverse"
                st.metric(
                    label=f"Ngày: {reg_pred['target_date']}", 
                    value=f"{val:.2f} Richter",
                    delta="Dự báo AI",
                    delta_color=delta_color
                )
                st.caption(f"Độ tin cậy: {reg_pred.get('confidence_score', 0)*100:.0f}% | Model: {reg_pred.get('model_name')}")
            else:
                st.info("Đang chờ model chạy...")

        with c2:
            st.markdown("### Cảnh báo Rủi ro")
            if class_pred:
                label = class_pred['predicted_label']
                if "High" in label or "Critical" in label:
                    st.error(f"⚠️ {label}")
                elif "Moderate" in label:
                    st.warning(f"⚡ {label}")
                else:
                    st.success(f"✅ {label}")
                st.caption(f"Phân loại dựa trên dữ liệu Cluster & Analysis")
            else:
                st.info("Đang chờ phân loại...")
                
    else:
        st.info("Chưa có dữ liệu dự báo. Hãy chạy file service_prediction.py!")

# Footer
st.markdown("---")
st.markdown("Example Project by Gemini - Earthquake Tracker Architecture")