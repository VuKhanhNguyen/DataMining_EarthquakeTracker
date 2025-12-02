const API_BASE_URL = 'http://127.0.0.1:8000';

let lineChart, scatterChart, histogramChart, trendChart, seasonalChart;
let currentPeriod = 'day';
let currentResample = 'week';

let earthquakeData = {
    daily: [],
    weekly: [],
    monthly: []
};

let timeWindowStart = 0;
let timeWindowSize = 30; 
let maxTimeWindowStart = 0;

let customDateRange = {
    startDate: '2025-01-01',
    endDate: '2025-12-01',
    isActive: false
};

function formatDateVN(date) {
    if (typeof date === 'string') {
        date = new Date(date);
    }
    return date.toLocaleDateString('vi-VN', {
        day: '2-digit',
        month: '2-digit', 
        year: 'numeric'
    });
}

window.debugAPI = async function(period = 'week', days = 84) {
    try {
        console.log(`=== DEBUGGING API: ${period} ===`);
        const response = await fetch(`${API_BASE_URL}/api/time-series?period=${period}&days_back=${days}`);
        
        if (response.ok) {
            const data = await response.json();
            console.log(`API Response for ${period}:`, {
                status: response.status,
                dataLength: data.length,
                sampleData: data.slice(0, 3)
            });
            return data;
        } else {
            console.error(`API Error: ${response.status}`);
            return null;
        }
    } catch (error) {
        console.error('Debug API Error:', error);
        return null;
    }
};

document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
    loadInitialData();
    setupEventListeners();
});

async function loadInitialData() {
    try {
        await loadStats();
        await loadTimeSeriesData();
        initializeCharts();
        await loadCorrelationMatrix();
        await loadPredictions();
    } catch (error) {
        console.error('❌ Không thể tải dữ liệu ban đầu:', error);
        showGlobalError('Không thể kết nối đến API server. Hãy đảm bảo rằng các BE Service đang chạy.');
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(JSON.stringify(errorData));
        }
        
        const stats = await response.json();
        
        animateValue('totalEarthquakes', 0, stats.total_earthquakes, 2000);
        animateValue('avgMagnitude', 0, stats.avg_magnitude, 2000, 1);
        animateValue('avgDepth', 0, stats.avg_depth, 2000, 1, ' km');
        animateValue('riskZones', 0, stats.risk_zones, 2000);
        
    } catch (error) {
        console.error('❌ STATS API ERROR:', error);
        showAPIError('Statistics', error);

        document.getElementById('totalEarthquakes').textContent = 'ERROR';
        document.getElementById('avgMagnitude').textContent = 'N/A';
        document.getElementById('avgDepth').textContent = 'N/A';
        document.getElementById('riskZones').textContent = 'N/A';
    }
}

async function loadTimeSeriesData() {
    try {
        const periods = ['day', 'week', 'month'];
        const daysBacks = { day: 30, week: 84, month: 365 };
        let hasAnyData = false;

        for (const period of periods) {
            try {
                const response = await fetch(
                    `${API_BASE_URL}/api/time-series?period=${period}&days_back=${daysBacks[period]}`
                );
                
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(JSON.stringify(errorData));
                }
                
                const data = await response.json();
                const keyName = period === 'day' ? 'daily' : 
                              period === 'week' ? 'weekly' : 'monthly';
                
                earthquakeData[keyName] = data.map(item => ({
                    date: new Date(item.date),
                    count: item.count || 0,
                    magnitude: item.avg_magnitude || 0,
                    max_magnitude: item.max_magnitude || 0,
                    depth: item.avg_depth || 0
                }));
                hasAnyData = true;
                console.log(`✅ Loaded ${period} data:`, data.length, 'items');
                
            } catch (periodError) {
                console.error(`❌ Error loading ${period} data:`, periodError);
                earthquakeData[keyName] = [];
            }
        }
        
        if (!hasAnyData) {
            throw new Error('Không có dữ liệu chuỗi thời gian cho bất kỳ khoảng thời gian nào');
        }
        
    } catch (error) {
        console.error('❌ LỖi TIME SERIES API:', error);
        showAPIError('Time Series', error);

        earthquakeData = { daily: [], weekly: [], monthly: [] };
    }
}

function generateFallbackTimeSeriesData() {
    console.log('Đang tạo dữ liệu chuỗi thời gian dự phòng toàn diện...');
    

    earthquakeData = {
        daily: generateSampleData(30, 'day'),
        weekly: generateSampleData(12, 'week'), 
        monthly: generateSampleData(12, 'month')
    };
    
    ['daily', 'weekly', 'monthly'].forEach(period => {
        earthquakeData[period].forEach((item, index) => {
            if (period === 'weekly') {
                const dayOfWeek = index % 7;
                item.count = Math.floor(item.count * (0.7 + 0.3 * Math.sin(dayOfWeek * Math.PI / 3.5)));
            } else if (period === 'monthly') {
                item.count = Math.floor(item.count * (0.8 + 0.4 * Math.sin(index * Math.PI / 6)));
            }
            
            if (item.magnitude < 2) item.magnitude = 2 + Math.random();
            if (item.magnitude > 7) item.magnitude = 6 + Math.random();
        });
    });
    
    console.log('Dữ liệu chuỗi thời gian dự phòng toàn diện đã được tạo:', {
        daily: earthquakeData.daily.length,
        weekly: earthquakeData.weekly.length,
        monthly: earthquakeData.monthly.length
    });
    
    Object.keys(earthquakeData).forEach(key => {
        console.log(`${key} sample:`, earthquakeData[key].slice(0, 3).map(d => ({
            date: d.date.toLocaleDateString('vi-VN'),
            count: d.count,
            magnitude: d.magnitude.toFixed(1)
        })));
    });
}

async function loadCorrelationMatrix() {
     try {
        const response = await fetch(`${API_BASE_URL}/api/correlation`);
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(JSON.stringify(errorData));
        }
        
        const correlationData = await response.json();
        renderCorrelationMatrix(correlationData);
        console.log('✅ Ma trận tương quan thực đã được tải');
        
    } catch (error) {
        console.error('❌ LỖI API Ma trận tương quan:', error);
        showAPIError('Ma trận tương quan', error);
        
        const correlationMatrix = document.getElementById('correlationMatrix');
        if (correlationMatrix) {
            correlationMatrix.innerHTML = `
                <div style="
                    grid-column: 1 / -1;
                    background: rgba(255, 68, 68, 0.1);
                    border: 2px dashed #ff4444;
                    border-radius: 10px;
                    padding: 40px;
                    text-align: center;
                    color: #ff4444;
                    font-weight: bold;
                ">
                    ❌ LỖI DỮ LIỆU TƯƠNG QUAN<br>
                    <span style="font-size: 14px; opacity: 0.8;">
                        Không có dữ liệu tương quan từ API
                    </span>
                </div>
            `;
        }
    }
}

async function loadPredictions() {
    try {
        const response = await fetch('http://localhost:8000/predictions/latest');
        const data = await response.json();
        
        console.log('Prediction data:', data); 
     
        if (data.magnitude_prediction) {
            document.getElementById('predictedMagnitude').textContent = data.magnitude_prediction.value;
         
            const confidenceBar = document.querySelector('.prediction-card .confidence-fill');
            if (confidenceBar) {
                confidenceBar.style.width = data.magnitude_prediction.confidence + '%';
            }
            const confidenceText = document.querySelector('.prediction-card .confidence-text');
            if (confidenceText) {
                confidenceText.textContent = `Độ tin cậy: ${data.magnitude_prediction.confidence}%`;
            }
        }
 
        if (data.risk_classification) {
            const riskLevelElement = document.getElementById('riskLevel');
            if (riskLevelElement) {
                riskLevelElement.querySelector('.risk-text').textContent = data.risk_classification.level;
                
     
                riskLevelElement.className = 'risk-level';
                if (data.risk_classification.level.includes('CỰC CAO')) {
                    riskLevelElement.classList.add('extreme');
                } else if (data.risk_classification.level.includes('CAO')) {
                    riskLevelElement.classList.add('high');
                } else if (data.risk_classification.level.includes('TRUNG BÌNH')) {
                    riskLevelElement.classList.add('medium');
                } else {
                    riskLevelElement.classList.add('low');
                }
            }
        }
   
        if (data.risk_factors) {
            const riskDetails = document.querySelector('.risk-details .risk-factors');
            if (riskDetails) {
                const factors = riskDetails.querySelectorAll('.factor-value');
                if (factors.length >= 2) {
                    factors[0].textContent = data.risk_factors.geological_activity || 'N/A';
                    factors[1].textContent = data.risk_factors.tectonic_pressure || 'N/A';
                }
            }
        }
 
        if (data.depth_prediction) {
            document.getElementById('predictedDepth').textContent = data.depth_prediction.value;
            const depthCard = document.querySelectorAll('.prediction-card')[2];
            if (depthCard) {
                const confidenceBar = depthCard.querySelector('.confidence-fill');
                if (confidenceBar) {
                    confidenceBar.style.width = data.depth_prediction.confidence + '%';
                }
                const confidenceText = depthCard.querySelector('.confidence-text');
                if (confidenceText) {
                    confidenceText.textContent = `Độ tin cậy: ${data.depth_prediction.confidence}%`;
                }
            }
        }
  
        if (data.hotspots && data.hotspots.length > 0) {
            const hotspotList = document.querySelector('.hotspot-list');
            if (hotspotList) {
                hotspotList.innerHTML = '';
                data.hotspots.forEach(hotspot => {
                    const hotspotItem = document.createElement('div');
                    hotspotItem.className = 'hotspot-item';
                    hotspotItem.innerHTML = `
                        <span class="hotspot-name">${hotspot.name}</span>
                        <span class="hotspot-prob">${hotspot.probability}%</span>
                    `;
                    hotspotList.appendChild(hotspotItem);
                });
            }
        }
        
    } catch (error) {
        console.error('Error loading predictions:', error);
    }
}

function showAPIError(apiType, error) {
    let errorDetails = {};
    try {
        errorDetails = JSON.parse(error.message).detail;
    } catch {
        errorDetails = { message: error.message };
    }
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'api-error-notification';
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #ff4444, #cc0000);
        color: white;
        padding: 20px;
        border-radius: 10px;
        max-width: 400px;
        z-index: 9999;
        box-shadow: 0 4px 20px rgba(255, 68, 68, 0.4);
        animation: slideInRight 0.5s ease-out;
    `;
    
    errorDiv.innerHTML = `
        <div style="font-size: 16px; font-weight: bold; margin-bottom: 10px;">
            ❌ ${apiType.toUpperCase()} API ERROR
        </div>
        <div style="font-size: 14px; margin-bottom: 10px;">
            ${errorDetails.message || 'Unknown API error'}
        </div>
        <div style="font-size: 12px; opacity: 0.8;">
            ${errorDetails.suggestion || 'Vui lòng kiểm tra dịch vụ backend'}
        </div>
        <button onclick="this.parentElement.remove()" style="
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 8px 15px;
            margin-top: 15px;
            border-radius: 5px;
            cursor: pointer;
            float: right;
        ">Close</button>
        <div style="clear: both;"></div>
    `;
    
    document.body.appendChild(errorDiv);
    
    setTimeout(() => {
        if (errorDiv.parentElement) {
            errorDiv.style.animation = 'slideOutRight 0.5s ease-in';
            setTimeout(() => errorDiv.remove(), 500);
        }
    }, 15000);
}

function showChartError(canvas, message) {
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    ctx.fillStyle = '#ff4444';
    ctx.font = 'bold 18px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('❌ NO DATA', canvas.width / 2, canvas.height / 2 - 10);
    
    ctx.fillStyle = '#a0a0a0';
    ctx.font = '14px Arial';
    ctx.fillText(message, canvas.width / 2, canvas.height / 2 + 20);
    
    ctx.font = '12px Arial';
    ctx.fillText('Chạy data_ingestion.py để thu thập dữ liệu động đất', canvas.width / 2, canvas.height / 2 + 50);
}

function showPredictionError() {

    const magElement = document.getElementById('predictedMagnitude');
    if (magElement) {
        magElement.textContent = '?.?';
        magElement.style.color = '#ff4444';
    }
    
    const depthElement = document.getElementById('predictedDepth');
    if (depthElement) {
        depthElement.textContent = '?.?';
        depthElement.style.color = '#ff4444';
    }
    
    const riskLevel = document.getElementById('riskLevel');
    if (riskLevel) {
        riskLevel.className = 'risk-level error';
        const riskText = riskLevel.querySelector('.risk-text');
        if (riskText) riskText.textContent = 'NO DATA';
    }
    
    const confidenceBars = document.querySelectorAll('.confidence-fill');
    const confidenceTexts = document.querySelectorAll('.confidence-text');
    
    confidenceBars.forEach(bar => {
        bar.style.width = '0%';
        bar.style.backgroundColor = '#ff4444';
    });
    
    confidenceTexts.forEach(text => {
        text.textContent = 'Model Error - No Training Data';
        text.style.color = '#ff4444';
    });
}

function showGlobalError(message) {
    const main = document.querySelector('main') || document.body;
    const errorBanner = document.createElement('div');
    errorBanner.className = 'global-error-banner';
    errorBanner.style.cssText = `
        background: linear-gradient(135deg, #ff4444, #cc0000);
        color: white;
        padding: 20px;
        text-align: center;
        font-size: 18px;
        font-weight: bold;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 10000;
        box-shadow: 0 4px 20px rgba(255, 68, 68, 0.5);
    `;
    
    errorBanner.innerHTML = `
        ⚠️ SYSTEM ERROR: ${message}
        <div style="font-size: 14px; margin-top: 10px; opacity: 0.9;">
            Vui lòng đảm bảo rằng máy chủ API backend đang chạy trên cổng 8000
        </div>
    `;
    
    document.body.insertBefore(errorBanner, document.body.firstChild);
    document.body.style.paddingTop = '80px';
}

const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    .risk-level.error {
        background: linear-gradient(135deg, #ff4444, #cc0000);
        color: white;
    }
`;
document.head.appendChild(style);

function initializeNavigation() {
    const hamburger = document.getElementById('hamburger');
    const navLinksMobile = document.getElementById('navLinksMobile');
    const mobileLinks = navLinksMobile.querySelectorAll('a');

    hamburger.addEventListener('click', function () {
        hamburger.classList.toggle('active');
        navLinksMobile.classList.toggle('active');
    });

    mobileLinks.forEach(link => {
        link.addEventListener('click', function () {
            hamburger.classList.remove('active');
            navLinksMobile.classList.remove('active');
        });
    });

    window.addEventListener('scroll', function () {
        hamburger.classList.remove('active');
        navLinksMobile.classList.remove('active');
    });

    window.addEventListener('scroll', function () {
        const navbar = document.getElementById('navbar');
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-links a');
    const mobileNavLinks = document.querySelectorAll('.nav-links-mobile a');

    function updateActiveNav() {
        const scrollY = window.pageYOffset;

        sections.forEach(section => {
            const sectionHeight = section.offsetHeight;
            const sectionTop = section.offsetTop - 100;
            const sectionId = section.getAttribute('id');

            if (scrollY > sectionTop && scrollY <= sectionTop + sectionHeight) {
                navLinks.forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === `#${sectionId}`) {
                        link.classList.add('active');
                    }
                });

                mobileNavLinks.forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === `#${sectionId}`) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }

    window.addEventListener('scroll', updateActiveNav);

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

function generateSampleData(count, period) {
    const data = [];
    const now = new Date();
    
    console.log(`Đang tạo ${count} điểm dữ liệu mẫu cho khoảng thời gian: ${period}`);
    
    for (let i = count - 1; i >= 0; i--) {
        const date = new Date(now);
        
        if (period === 'day') {
            date.setDate(date.getDate() - i);
        } else if (period === 'week') {
            date.setDate(date.getDate() - (i * 7));
        } else if (period === 'month') {
            date.setMonth(date.getMonth() - i);
        }
        
        const baseMagnitude = 3 + Math.random() * 4; 
        const magnitude = Math.round(baseMagnitude * 10) / 10; 
        const depth = 10 + Math.random() * 150;
        
        let count;
        if (period === 'day') {
            count = Math.floor(Math.random() * 20) + 5; 
        } else if (period === 'week') {
            count = Math.floor(Math.random() * 100) + 20; 
        } else {
            count = Math.floor(Math.random() * 400) + 50; 
        }
        
        data.push({
            date: date,
            magnitude: magnitude,
            depth: Math.round(depth * 10) / 10,
            count: count,
            latitude: (Math.random() - 0.5) * 180,
            longitude: (Math.random() - 0.5) * 360
        });
    }
    
    return data;
}

function initializeCharts() {
    setTimeout(() => {
        initializeLineChart();
        initializeScatterChart();
        initializeHistogramChart();
        initializeTrendChart();
        initializeSeasonalChart();
    }, 100);
}

function initializeLineChart() {
    const canvas = document.getElementById('lineChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const keyMapping = { day: 'daily', week: 'weekly', month: 'monthly' };
    const data = earthquakeData[keyMapping[currentPeriod]] || [];
    
    if (data.length === 0) {
        showChartError(canvas, 'Không có dữ liệu động đất');
        return;
    }
    
    if (lineChart) lineChart.destroy();
    
    lineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date.toLocaleDateString('vi-VN')),
            datasets: [{
                label: 'Số lượng động đất',
                data: data.map(d => d.count),
                borderColor: '#ff4444',
                backgroundColor: 'rgba(255, 68, 68, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#a0a0a0' }
                },
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#a0a0a0' }
                }
            }
        }
    });
}

function initializeScatterChart() {
    const canvas = document.getElementById('scatterChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const keyMapping = { day: 'daily', week: 'weekly', month: 'monthly' };
    const data = earthquakeData[keyMapping[currentPeriod]] || [];
    
    if (data.length === 0) {
        showChartError(canvas, 'Không có dữ liệu động đất cho biểu đồ phân tán');
        return;
    }
    
    if (scatterChart) scatterChart.destroy();
    
    scatterChart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Động đất',
                data: data.map(d => ({
                    x: d.magnitude,
                    y: d.depth
                })),
                backgroundColor: 'rgba(255, 68, 68, 0.6)',
                borderColor: '#ff4444',
                borderWidth: 2,
                pointRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    title: { display: true, text: 'Độ sâu (km)', color: '#ffffff' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#a0a0a0' }
                },
                x: {
                    title: { display: true, text: 'Cường độ', color: '#ffffff' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#a0a0a0' }
                }
            }
        }
    });
}

function initializeHistogramChart() {
     const canvas = document.getElementById('histogramChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const keyMapping = { day: 'daily', week: 'weekly', month: 'monthly' };
    const data = earthquakeData[keyMapping[currentPeriod]] || [];
    
    if (data.length === 0) {
        showChartError(canvas, 'Không có dữ liệu cho biểu đồ phân phối cường độ');
        return;
    }
    
    const bins = [0, 2, 3, 4, 5, 6, 7, 8];
    const binCounts = new Array(bins.length - 1).fill(0);
    
    data.forEach(d => {
        for (let i = 0; i < bins.length - 1; i++) {
            if (d.magnitude >= bins[i] && d.magnitude < bins[i + 1]) {
                binCounts[i]++;
                break;
            }
        }
    });
    
    if (histogramChart) histogramChart.destroy();
    
    histogramChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: bins.slice(0, -1).map((bin, i) => `${bin}-${bins[i + 1]}`),
            datasets: [{
                label: 'Số lượng động đất',
                data: binCounts,
                backgroundColor: 'rgba(255, 68, 68, 0.7)',
                borderColor: '#ff4444',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Tần suất', color: '#ffffff' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#a0a0a0' }
                },
                x: {
                    title: { display: true, text: 'Khoảng cường độ', color: '#ffffff' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#a0a0a0' }
                }
            }
        }
    });
}

function initializeTrendChart() {
    const canvas = document.getElementById('trendChart');
    if (!canvas) {
        console.error('trendChart canvas không tìm thấy');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    const data = earthquakeData[currentResample === 'week' ? 'weekly' : 'monthly'] || [];
    
    if (data.length === 0) {
        console.warn('❌ Không có dữ liệu cho biểu đồ xu hướng');
        showChartError(canvas, `Không có dữ liệu ${currentResample} cho phân tích xu hướng`);
        return;
    }
    
    const movingAvg = calculateMovingAverage(data.map(d => d.magnitude), 1);
    
    if (trendChart) {
        trendChart.destroy();
    }
    
    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date.toLocaleDateString('vi-VN')),
            datasets: [
                {
                    label: 'Cường độ trung bình',
                    data: data.map(d => d.magnitude),
                    borderColor: '#ff8800',
                    backgroundColor: 'rgba(255, 136, 0, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4
                },
                {
                    label: 'Xu hướng',
                    data: movingAvg,
                    borderColor: '#ff4444',
                    backgroundColor: 'transparent',
                    borderWidth: 3,
                    fill: false,
                    tension: 0.4,
                    borderDash: [5, 5]
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    labels: {
                        color: '#ffffff'
                    }
                }
            },
            scales: {
                y: {
                    title: {
                        display: true,
                        text: 'Cường độ trung bình',
                        color: '#ffffff'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#a0a0a0'
                    }
                },
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#a0a0a0'
                    }
                }
            }
        }
    });
}

function initializeSeasonalChart() {
    const canvas = document.getElementById('seasonalChart');
    if (!canvas) {
        console.error('seasonalChart canvas không tìm thấy');
        return;
    }
    
    const ctx = canvas.getContext('2d');

    let seasonalData = null;
    
    if (earthquakeData.monthly && earthquakeData.monthly.length > 0) {
        const monthlyAverages = new Array(12).fill(0);
        const monthlyCounts = new Array(12).fill(0);
        
        earthquakeData.monthly.forEach(item => {
            const month = item.date.getMonth();
            monthlyAverages[month] += item.count;
            monthlyCounts[month]++;
        });
        
        seasonalData = monthlyAverages.map((sum, index) => 
            monthlyCounts[index] > 0 ? sum / monthlyCounts[index] : 0
        );
        
        console.log('✅ Sử dụng dữ liệu mùa vụ thực từ API');
    } else {
        console.warn('❌ Không có dữ liệu tháng cho biểu đồ mùa vụ');
        showChartError(canvas, 'Không có dữ liệu tháng cho phân tích mùa vụ');
        return;
    }
    
    const months = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T10', 'T11', 'T12'];
    
    if (seasonalChart) {
        seasonalChart.destroy();
    }
    
    seasonalChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: 'Hoạt động động đất theo tháng',
                data: seasonalData,
                borderColor: '#00ff88',
                backgroundColor: 'rgba(0, 255, 136, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#00ff88',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    title: {
                        display: true,
                        text: 'Số lượng động đất',
                        color: '#ffffff'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#a0a0a0'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Tháng',
                        color: '#ffffff'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#a0a0a0'
                    }
                }
            }
        }
    });
}

function calculateMovingAverage(data, windowSize) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        const start = Math.max(0, i - windowSize + 1);
        const window = data.slice(start, i + 1);
        const average = window.reduce((sum, val) => sum + val, 0) / window.length;
        result.push(average);
    }
    return result;
}

function renderCorrelationMatrix(correlationData) {
    const correlationMatrix = document.getElementById('correlationMatrix');
    
    if (!correlationMatrix) {
        console.error('correlationMatrix không tìm thấy');
        return;
    }
    
    const variables = correlationData.variables;
    const correlations = correlationData.matrix;
    
    correlationMatrix.style.gridTemplateColumns = `repeat(${variables.length + 1}, 1fr)`;
    
    correlationMatrix.innerHTML = '';
    
    correlationMatrix.innerHTML = '<div class="correlation-cell header"></div>';
    variables.forEach(variable => {
        correlationMatrix.innerHTML += `<div class="correlation-cell header">${variable}</div>`;
    });
    
    variables.forEach((rowVar, i) => {
        correlationMatrix.innerHTML += `<div class="correlation-cell header">${rowVar}</div>`;
        correlations[i].forEach(correlation => {
            const cell = document.createElement('div');
            cell.className = 'correlation-cell';
            cell.innerHTML = `<div class="correlation-value">${correlation.toFixed(2)}</div>`;
            
            const absCorr = Math.abs(correlation);
            if (correlation > 0) {
                cell.style.background = `rgba(0, 255, 136, ${absCorr * 0.8})`;
            } else {
                cell.style.background = `rgba(255, 68, 68, ${absCorr * 0.8})`;
            }
            
            correlationMatrix.appendChild(cell);
        });
    });
}

function updatePredictionsDisplay(data) {
    console.log('Đang cập nhật hiển thị dự đoán với dữ liệu:', data);
    
    if (data.magnitude_prediction) {
        const magElement = document.getElementById('predictedMagnitude');
        if (magElement) {
            magElement.textContent = data.magnitude_prediction.value.toFixed(1);
        }
        
        const magConfidenceBar = document.querySelector('.prediction-card:nth-child(1) .confidence-fill');
        const magConfidenceText = document.querySelector('.prediction-card:nth-child(1) .confidence-text');
        if (magConfidenceBar && magConfidenceText) {
            magConfidenceBar.style.width = `${data.magnitude_prediction.confidence}%`;
            magConfidenceText.textContent = `Độ tin cậy: ${data.magnitude_prediction.confidence}%`;
        }
        
        const magDetails = document.querySelector('.prediction-card:nth-child(1) .prediction-details');
        if (magDetails) {
            const model = data.magnitude_prediction.model || 'ML Model';
            const note = data.magnitude_prediction.note || 'dựa trên dữ liệu được train';
            // magDetails.textContent = `Mô hình ${model} - ${note}`;
        }
        
        updateRiskLevel(data.magnitude_prediction.value);
    }
    
    if (data.depth_prediction) {
        const depthElement = document.getElementById('predictedDepth');
        if (depthElement) {
            depthElement.textContent = data.depth_prediction.value.toFixed(1);
        }
        
        const depthConfidenceBar = document.querySelector('.prediction-card:nth-child(3) .confidence-fill');
        const depthConfidenceText = document.querySelector('.prediction-card:nth-child(3) .confidence-text');
        if (depthConfidenceBar && depthConfidenceText) {
            depthConfidenceBar.style.width = `${data.depth_prediction.confidence}%`;
            depthConfidenceText.textContent = `Độ tin cậy: ${data.depth_prediction.confidence}%`;
        }
        
        const depthCard = document.querySelector('.prediction-card:nth-child(3)');
        let methodElement = depthCard.querySelector('.calculation-method');
        if (!methodElement) {
            methodElement = document.createElement('div');
            methodElement.className = 'calculation-method';
            methodElement.style.fontSize = '12px';
            methodElement.style.color = '#a0a0a0';
            methodElement.style.marginTop = '10px';
            depthCard.appendChild(methodElement);
        }
        methodElement.textContent = data.depth_prediction.method || '';
    }
    
    if (data.risk_factors) {
        const geologicalEl = document.getElementById('geologicalActivity');
        const tectonicEl = document.getElementById('tectonicPressure');
        
        if (geologicalEl) {
            geologicalEl.textContent = data.risk_factors.geological_activity;
        }
        
        if (tectonicEl) {
            tectonicEl.textContent = data.risk_factors.tectonic_pressure;
        }
    }

    if (data.risk_classification) {
        const riskLevel = document.getElementById('riskLevel');
        if (riskLevel) {
            const riskLevelText = data.risk_classification.level;
            
            riskLevel.className = 'risk-level';
            
            if (riskLevelText.includes('CỰC CAO')) {
                riskLevel.classList.add('extreme');
                riskLevel.querySelector('.risk-text').textContent = 'RỦI RO CỰC CAO';
            } else if (riskLevelText.includes('CAO')) {
                riskLevel.classList.add('high');
                riskLevel.querySelector('.risk-text').textContent = 'RỦI RO CAO';
            } else if (riskLevelText.includes('TRUNG BÌNH')) {
                riskLevel.classList.add('medium');
                riskLevel.querySelector('.risk-text').textContent = 'RỦI RO TRUNG BÌNH';
            } else if (riskLevelText.includes('THẤP')) {
                riskLevel.classList.add('low');
                riskLevel.querySelector('.risk-text').textContent = 'RỦI RO THẤP';
            } else {
                riskLevel.classList.add('very-low');
                riskLevel.querySelector('.risk-text').textContent = 'RỦI RO RẤT THẤP';
            }
        }
    }
    
    if (data.hotspots) {
        const hotspotList = document.querySelector('.hotspot-list');
        if (hotspotList) {
            hotspotList.innerHTML = '';
            data.hotspots.forEach(hotspot => {
                const item = document.createElement('div');
                item.className = 'hotspot-item';
                item.innerHTML = `
                    <span class="hotspot-name">${hotspot.name}</span>
                    <span class="hotspot-prob">${hotspot.probability}%</span>
                `;
                hotspotList.appendChild(item);
            });
        }
    }
    
    addDataSourceIndicator(data.data_sources || {});
}

function updateRiskClassificationFromDB(riskData) {
    const riskLevel = document.getElementById('riskLevel');
    const riskText = riskLevel?.querySelector('.risk-text');
    
    if (!riskLevel || !riskText) return;
    
    const level = riskData.level.toLowerCase();
    
    if (level.includes('critical')) {
        riskLevel.className = 'risk-level critical';
        riskText.textContent = 'CẢNH BÁO KHẨN CẤP';
    } else if (level.includes('high')) {
        riskLevel.className = 'risk-level high';
        riskText.textContent = 'RỦI RO CAO';
    } else if (level.includes('moderate')) {
        riskLevel.className = 'risk-level medium';
        riskText.textContent = 'RỦI RO TRUNG BÌNH';
    } else {
        riskLevel.className = 'risk-level low';
        riskText.textContent = 'RỦI RO THẤP';
    }
    
    const riskCard = document.querySelector('.prediction-card:nth-child(2)');
    let modelInfo = riskCard.querySelector('.model-info');
    if (!modelInfo) {
        modelInfo = document.createElement('div');
        modelInfo.className = 'model-info';
        modelInfo.style.fontSize = '11px';
        modelInfo.style.color = '#707070';
        modelInfo.style.marginTop = '8px';
        riskCard.querySelector('.risk-classification').appendChild(modelInfo);
    }
    
    const model = riskData.model || 'Rule-based';
    const confidence = riskData.confidence || 0;
    modelInfo.textContent = `(${confidence}% tin cậy)`;
}

function updateRiskFactorsFromAnalysis(factors) {
    const geologicalActivity = document.querySelector('.factor:nth-child(1) .factor-value');
    const tectonicPressure = document.querySelector('.factor:nth-child(2) .factor-value');
    
    if (geologicalActivity && factors.geological_activity) {
        geologicalActivity.textContent = factors.geological_activity;
        
        const match = factors.geological_activity.match(/\(([-+]?\d+)%\)/);
        const trendPercent = match ? parseInt(match[1]) : 0;
        
        if (trendPercent > 20) {
            geologicalActivity.style.color = '#ff4444'; 
        } else if (trendPercent > 5) {
            geologicalActivity.style.color = '#ff8800'; 
        } else if (trendPercent < -20) {
            geologicalActivity.style.color = '#00ff88'; 
        } else if (trendPercent < -5) {
            geologicalActivity.style.color = '#88ff88'; 
        } else {
            geologicalActivity.style.color = '#ffaa00'; 
        }
    }
    
    if (tectonicPressure && factors.tectonic_pressure) {
        tectonicPressure.textContent = factors.tectonic_pressure;
        
        if (factors.tectonic_pressure === 'Cao') {
            tectonicPressure.style.color = '#ff4444';
        } else if (factors.tectonic_pressure === 'Trung bình') {
            tectonicPressure.style.color = '#ffaa00';
        } else {
            tectonicPressure.style.color = '#00ff88';
        }
    }
    
    if (factors.recent_activity) {
        const riskDetails = document.querySelector('.risk-details');
        let activityInfo = riskDetails.querySelector('.recent-activity');
        if (!activityInfo) {
            activityInfo = document.createElement('div');
            activityInfo.className = 'recent-activity';
            activityInfo.style.fontSize = '12px';
            activityInfo.style.color = '#a0a0a0';
            activityInfo.style.marginTop = '10px';
            activityInfo.style.textAlign = 'center';
            riskDetails.appendChild(activityInfo);
        }
        // activityInfo.textContent = `Hoạt động gần đây: ${factors.recent_activity}`;
    }
}

function updateHotspotsFromClusters(hotspots) {
    const hotspotList = document.querySelector('.hotspot-list');
    if (!hotspotList) return;
    
    hotspotList.innerHTML = '';
    
    hotspots.forEach(hotspot => {
        const hotspotItem = document.createElement('div');
        hotspotItem.className = 'hotspot-item';
        
        const riskColor = hotspot.risk_level === 'High' ? '#ff4444' : 
                         hotspot.risk_level === 'Medium' ? '#ffaa00' : '#00ff88';
        
        hotspotItem.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 8px; height: 8px; background: ${riskColor}; border-radius: 50%;"></div>
                <span class="hotspot-name">${hotspot.name}</span>
            </div>
            <span class="hotspot-prob">${hotspot.probability}%</span>
        `;
        
        if (hotspot.location) {
            const locationInfo = document.createElement('div');
            locationInfo.style.fontSize = '10px';
            locationInfo.style.color = '#707070';
            locationInfo.style.gridColumn = '1 / -1';
            locationInfo.textContent = hotspot.location;
            hotspotItem.appendChild(locationInfo);
        }
        
        hotspotList.appendChild(hotspotItem);
    });
}

function addDataSourceIndicator(dataSources) {
    const predictionSection = document.querySelector('.prediction-section .dashboard-container');
    let indicator = predictionSection.querySelector('.data-source-indicator');
    
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.className = 'data-source-indicator';
        indicator.style.cssText = `
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            font-size: 12px;
            color: #a0a0a0;
        `;
        predictionSection.insertBefore(indicator, predictionSection.querySelector('.prediction-grid'));
    }
    
    const hasML = dataSources.has_ml_predictions;
    const hasAnalysis = dataSources.has_analysis_stats;
    // const hasCluster = dataSources.has_cluster_info;
    
    const status = hasML ? '🤖 ML Model' : '📊 Statistical';
    const sources = [
        hasML ? '✅ Trained ML Models' : '❌ No ML Models',
        hasAnalysis ? '✅ Analysis Stats' : '❌ No Analysis Data',
        // hasCluster ? '✅ Cluster Info' : '❌ No Clustering'
    ].join(' | ');
    
    const lastUpdate = dataSources.last_analysis ? 
        `Cập nhật cuối: ${new Date(dataSources.last_analysis).toLocaleString('vi-VN')}` : 
        'Chưa có dữ liệu phân tích';
    
    indicator.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong>${status}</strong> - Nguồn dữ liệu: ${sources}
            </div>
            <div>${lastUpdate}</div>
        </div>
    `;
}

function updateRiskLevel(predictedMagnitude) {
    const riskLevel = document.getElementById('riskLevel');
    if (riskLevel) {
        const riskText = riskLevel.querySelector('.risk-text');
        
        if (predictedMagnitude > 6) {
            riskLevel.className = 'risk-level high';
            if (riskText) riskText.textContent = 'RỦI RO CAO';
        } else if (predictedMagnitude > 4) {
            riskLevel.className = 'risk-level medium';
            if (riskText) riskText.textContent = 'RỦI RO TRUNG BÌNH';
        } else {
            riskLevel.className = 'risk-level low';
            if (riskText) riskText.textContent = 'RỦI RO THẤP';
        }
    }
}

function animateValue(id, start, end, duration, decimals = 0, suffix = '') {
    const element = document.getElementById(id);
    if (!element) return;
    
    const range = end - start;
    const increment = range / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= end) {
            current = end;
            clearInterval(timer);
        }
        element.textContent = current.toFixed(decimals) + suffix;
    }, 16);
}

function setupEventListeners() {
    const timeBtns = document.querySelectorAll('.time-btn');
    timeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            timeBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentPeriod = this.dataset.period;
            
            console.log('=== PERIOD CHANGED ===');
            console.log('Selected period:', currentPeriod);
            
            updateTimeSeriesCharts();
        });
    });
    
    const chartOptions = document.querySelectorAll('.chart-options .chart-option');
    chartOptions.forEach(option => {
        option.addEventListener('click', function() {
            const parent = this.parentElement;
            parent.querySelectorAll('.chart-option').forEach(opt => opt.classList.remove('active'));
            this.classList.add('active');
            currentResample = this.dataset.resample;
            
            updateTrendChart();
        });
    });
    
    setupPresetHandlers();

    const resetBtn = document.getElementById('resetFilter');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetDateFilter);
    }
}

function updateTimeSeriesCharts() {
    const keyMapping = { day: 'daily', week: 'weekly', month: 'monthly' };
    const lineData = earthquakeData[keyMapping[currentPeriod]] || [];
    
    console.log(`Updating charts - Period: ${currentPeriod}, Data length: ${lineData.length}`);

    if (lineData.length === 0) {
        console.warn(`❌ No ${currentPeriod} data available`);

        const canvases = ['lineChart', 'scatterChart', 'histogramChart'];
        canvases.forEach(canvasId => {
            const canvas = document.getElementById(canvasId);
            if (canvas) {
                showChartError(canvas, `No ${currentPeriod}ly data available`);
            }
        });
        return;
    }

    if (lineChart) {
        lineChart.data.labels = lineData.map(d => d.date.toLocaleDateString('vi-VN'));
        lineChart.data.datasets[0].data = lineData.map(d => d.count);
        lineChart.update();
        console.log(`✅ Biểu đồ đường đã được cập nhật với ${lineData.length} điểm dữ liệu thực`);
    }
 
    if (scatterChart) {
        scatterChart.data.datasets[0].data = lineData.map(d => ({
            x: d.magnitude,
            y: d.depth
        }));
        scatterChart.update();
        console.log(`✅ Biểu đồ scatter đã được cập nhật với ${lineData.length} điểm dữ liệu thực`);
    }
    
    if (histogramChart) {
        const bins = [0, 2, 3, 4, 5, 6, 7, 8];
        const binCounts = new Array(bins.length - 1).fill(0);
        
        lineData.forEach(d => {
            for (let i = 0; i < bins.length - 1; i++) {
                if (d.magnitude >= bins[i] && d.magnitude < bins[i + 1]) {
                    binCounts[i]++;
                    break;
                }
            }
        });
        
        histogramChart.data.datasets[0].data = binCounts;
        histogramChart.update();
        console.log(`✅ Biểu đồ histogram đã được cập nhật với phân phối dữ liệu thực:`, binCounts);
    }
}

function updateTrendChart() {
     const data = earthquakeData[currentResample === 'week' ? 'weekly' : 'monthly'] || [];
    
    if (data.length === 0) {
        console.warn('❌ Không có dữ liệu để cập nhật biểu đồ xu hướng');
        const canvas = document.getElementById('trendChart');
        if (canvas) {
            showChartError(canvas, `No ${currentResample}ly data available`);
        }
        return;
    }
    
    if (trendChart) {
        const movingAvg = calculateMovingAverage(data.map(d => d.magnitude), 3);
        
        trendChart.data.labels = data.map(d => d.date.toLocaleDateString('vi-VN'));
        trendChart.data.datasets[0].data = data.map(d => d.magnitude);
        trendChart.data.datasets[1].data = movingAvg;
        trendChart.update();
        
        console.log(`✅ Biểu đồ xu hướng đã được cập nhật với ${data.length} điểm dữ liệu thực`);
    }
}

function loadFallbackData() {
    console.log('Loading fallback data...');
    generateFallbackTimeSeriesData();
    initializeCharts();
    
    const fallbackCorrelation = {
        variables: ['Cường độ', 'Độ sâu', 'Vĩ độ', 'Kinh độ'],
        matrix: [
            [1.00, -0.23, 0.15, -0.08],
            [-0.23, 1.00, 0.12, 0.09],
            [0.15, 0.12, 1.00, 0.03],
            [-0.08, 0.09, 0.03, 1.00]
        ]
    };
    renderCorrelationMatrix(fallbackCorrelation);
    
    updatePredictionsDisplay({
        predictions: [
            { type: 'magnitude', value: 4.2, confidence: 85 },
            { type: 'depth', value: 45.8, confidence: 78 }
        ]
    });
}

function drawMiniChart(canvasId, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    const points = [];
    for (let i = 0; i < 10; i++) {
        points.push(Math.random() * canvas.height);
    }

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;

    points.forEach((point, index) => {
        const x = (canvas.width / (points.length - 1)) * index;
        const y = point;

        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });

    ctx.stroke();

    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
    gradient.addColorStop(0, color + '40');
    gradient.addColorStop(1, color + '00');

    ctx.lineTo(canvas.width, canvas.height);
    ctx.lineTo(0, canvas.height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();
}

setTimeout(() => {
    drawMiniChart('miniChart1', '#00ffcc');
    drawMiniChart('miniChart2', '#ff0080');
    drawMiniChart('miniChart3', '#00ccff');
    drawMiniChart('miniChart4', '#ffcc00');
    drawMiniChart('miniChart5', '#ff6b6b');
    drawMiniChart('miniChart6', '#4ecdc4');
}, 100);

const observerOptions = {
    threshold: 0.5,
    rootMargin: '0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const bars = entry.target.querySelectorAll('.bar');
            bars.forEach((bar, index) => {
                setTimeout(() => {
                    bar.style.animation = 'slideUp 0.5s ease-out forwards';
                }, index * 100);
            });
        }
    });
}, observerOptions);

document.querySelectorAll('.bar-chart').forEach(chart => {
    observer.observe(chart);
});

async function loadAnalysisData(startDate = null, endDate = null) {
    try {
        let url = `${API_BASE_URL}/api/analysis`;
        if (startDate && endDate) {
            url += `?start_date=${startDate}&end_date=${endDate}`;
        }
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const analysisData = await response.json();

        updateRiskFactorsFromAnalysis({
            geological_activity: analysisData.geological_activity,
            tectonic_pressure: analysisData.tectonic_pressure,
            activity_trend: analysisData.activity_trend === 'increasing' ? 20 : 
                          analysisData.activity_trend === 'decreasing' ? -20 : 0,
            recent_activity: analysisData.recent_activity
        });
        
        console.log('✅ Analysis data loaded:', analysisData);
        return analysisData;
        
    } catch (error) {
        console.error('❌ Analysis API Error:', error);
        return null;
    }
}

async function applyDateFilter() {
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    
    if (!startDate || !endDate) {
        alert('Vui lòng chọn cả ngày bắt đầu và kết thúc');
        return;
    }
    
    if (new Date(startDate) > new Date(endDate)) {
        alert('Ngày bắt đầu phải nhỏ hơn ngày kết thúc');
        return;
    }
    
    customDateRange = {
        startDate: startDate,
        endDate: endDate,
        isActive: true
    };

    showLoadingOnCharts();
    
    try {
        await loadTimeSeriesWithDateRange(startDate, endDate);

        await loadAnalysisData(startDate, endDate);
        
        initializeCharts();
        
        updateDataInfo(`${startDate} đến ${endDate}`);
        
        console.log(`✅ Applied date filter: ${startDate} to ${endDate}`);
        
    } catch (error) {
        console.error('❌ Error applying date filter:', error);
        alert('Lỗi khi lọc dữ liệu. Vui lòng thử lại.');
    }
}

async function loadTimeSeriesWithDateRange(startDate, endDate) {
    try {
        const periods = ['day', 'week', 'month'];
        
        for (const period of periods) {
            try {
                const response = await fetch(
                    `${API_BASE_URL}/api/time-series?period=${period}&custom_start=${startDate}&custom_end=${endDate}`
                );
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                const keyName = period === 'day' ? 'daily' : 
                              period === 'week' ? 'weekly' : 'monthly';
                
                earthquakeData[keyName] = data.map(item => ({
                    date: new Date(item.date),
                    count: item.count || 0,
                    magnitude: item.avg_magnitude || 0,
                    max_magnitude: item.max_magnitude || 0,
                    depth: item.avg_depth || 0
                }));
                
                console.log(`✅ Dữ liệu tùy chỉnh ${period} đã được tải:`, data.length, 'items');
                
            } catch (error) {
                console.error(`❌ Lỗi khi tải dữ liệu tùy chỉnh ${period}:`, error);
                earthquakeData[keyName] = [];
            }
        }
        
    } catch (error) {
        console.error('❌ Lỗi API phạm vi ngày tùy chỉnh:', error);
        throw error;
    }
}

function setupPresetHandlers() {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const days = parseInt(this.dataset.preset);
            const endDate = new Date();
            const startDate = new Date();
            startDate.setDate(endDate.getDate() - days);
            
            document.getElementById('startDate').value = startDate.toISOString().split('T')[0];
            document.getElementById('endDate').value = endDate.toISOString().split('T')[0];
            
            applyDateFilter();
        });
    });
}

function showLoadingOnCharts() {
    const canvases = ['lineChart', 'scatterChart', 'histogramChart', 'trendChart', 'seasonalChart'];
    
    canvases.forEach(canvasId => {
        const canvas = document.getElementById(canvasId);
        if (canvas) {
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#1a1a2e';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            ctx.fillStyle = '#ff8800';
            ctx.font = '16px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('⏳ Đang tải dữ liệu...', canvas.width / 2, canvas.height / 2);
        }
    });
}

function updateDataInfo(dateRange) {
    const infoElements = document.querySelectorAll('.data-info');
    infoElements.forEach(element => {
        element.textContent = `Hiển thị: ${dateRange}`;
    });
}

function resetDateFilter() {
    customDateRange.isActive = false;
 
    document.getElementById('startDate').value = '2025-01-01';
    document.getElementById('endDate').value = '2025-12-01';
    
    loadTimeSeriesData().then(() => {
        initializeCharts();
        updateDataInfo('Toàn bộ dữ liệu');
    });
}

async function triggerClustering() {
    try {
        console.log('🔄 Đang kích hoạt clustering...');
        const response = await fetch(`${API_BASE_URL}/api/clustering`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const result = await response.json();
        console.log('✅ Clustering đã hoàn thành:', result);

        await loadPredictions();
        
        return result;
        
    } catch (error) {
        console.error('❌ Lỗi Clustering:', error);
        return null;
    }
}

async function triggerPrediction() {
    try {
        console.log('🔄 Đang kích hoạt dự đoán...');
        const response = await fetch(`${API_BASE_URL}/api/prediction/run`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const result = await response.json();
        console.log('✅ Dự đoán đã hoàn thành:', result);
        
        await loadPredictions();
        
        return result;
        
    } catch (error) {
        console.error('❌ Lỗi dự đoán:', error);
        return null;
    }
}

async function checkSystemStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/prediction/status`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const status = await response.json();
        console.log('📊 System Status:', status);
        
        return status;
        
    } catch (error) {
        console.error('❌ Status Check Error:', error);
        return null;
    }
}

function addSystemControlButtons() {
    const controlsContainer = document.createElement('div');
    controlsContainer.className = 'system-controls';
    controlsContainer.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        display: flex;
        gap: 10px;
        z-index: 1000;
    `;
    
    const clusterBtn = document.createElement('button');
    clusterBtn.textContent = '🔄 Clustering';
    clusterBtn.onclick = triggerClustering;
    
    const predictionBtn = document.createElement('button');
    predictionBtn.textContent = '🤖 Prediction';
    predictionBtn.onclick = triggerPrediction;
    
    const statusBtn = document.createElement('button');
    statusBtn.textContent = '📊 Status';
    statusBtn.onclick = async () => {
        const status = await checkSystemStatus();
        if (status) {
            alert(`System Status:\n${JSON.stringify(status, null, 2)}`);
        }
    };
    
    controlsContainer.appendChild(clusterBtn);
    controlsContainer.appendChild(predictionBtn);
    controlsContainer.appendChild(statusBtn);
    
    document.body.appendChild(controlsContainer);
}

const metricsObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const metrics = entry.target.querySelectorAll('.metric-item');
            metrics.forEach((metric, index) => {
                setTimeout(() => {
                    metric.style.transform = 'translateY(0)';
                    metric.style.opacity = '1';
                }, index * 100);
            });
        }
    });
}, {
    threshold: 0.3
});

document.querySelectorAll('.metrics-grid').forEach(grid => {
    metricsObserver.observe(grid);
});


document.querySelectorAll('.metric-item').forEach(item => {
    item.style.transform = 'translateY(20px)';
    item.style.opacity = '0';
    item.style.transition = 'all 0.5s ease';
});