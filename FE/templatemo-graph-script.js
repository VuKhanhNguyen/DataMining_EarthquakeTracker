/* JavaScript Document

TemplateMo 602 Graph Page - Earthquake Tracker Dashboard

https://templatemo.com/tm-602-graph-page

*/

// API Configuration
const API_BASE_URL = 'http://127.0.0.1:8000';

// Global variables for charts
let lineChart, scatterChart, histogramChart, trendChart, seasonalChart;
let currentPeriod = 'day';
let currentResample = 'week';

// Data storage
let earthquakeData = {
    daily: [],
    weekly: [],
    monthly: []
};

// Debug function to manually test API
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

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
    loadInitialData();
    setupEventListeners();
});

// Load initial data from API
async function loadInitialData() {
    try {
        // Load stats
        await loadStats();
        
        // Load time series data for different periods
        await loadTimeSeriesData();
        
        // Initialize charts after data is loaded
        initializeCharts();
        
        // Load correlation matrix
        await loadCorrelationMatrix();
        
        // Load predictions
        await loadPredictions();
        
    } catch (error) {
        console.error('Error loading initial data:', error);
        // Fallback to sample data if API fails
        loadFallbackData();
    }
}

// Load statistics from API
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        if (!response.ok) throw new Error('Failed to fetch stats');
        
        const stats = await response.json();
        
        // Animate counters with real data
        animateValue('totalEarthquakes', 0, stats.total_earthquakes, 2000);
        animateValue('avgMagnitude', 0, stats.avg_magnitude, 2000, 1);
        animateValue('avgDepth', 0, stats.avg_depth, 2000, 1, ' km');
        animateValue('riskZones', 0, stats.risk_zones, 2000);
        
    } catch (error) {
        console.error('Error loading stats:', error);
        // Fallback stats
        animateValue('totalEarthquakes', 0, 1234, 2000);
        animateValue('avgMagnitude', 0, 4.2, 2000, 1);
        animateValue('avgDepth', 0, 45.8, 2000, 1, ' km');
        animateValue('riskZones', 0, 5, 2000);
    }
}

// Load time series data
async function loadTimeSeriesData() {
    try {
        // Load data for different periods
        const periods = ['day', 'week', 'month'];
        const daysBacks = { day: 30, week: 84, month: 365 };
        
        for (const period of periods) {
            const response = await fetch(
                `${API_BASE_URL}/api/time-series?period=${period}&days_back=${daysBacks[period]}`
            );
            
            if (response.ok) {
                const data = await response.json();
                const keyName = period === 'day' ? 'daily' : 
                              period === 'week' ? 'weekly' : 'monthly';
                
                console.log(`Loading ${period} data:`, data.length, 'items');
                console.log('Raw API response sample:', data.slice(0, 2));
                
                earthquakeData[keyName] = data.map(item => ({
                    date: new Date(item.date),
                    count: item.count || 0,
                    magnitude: item.avg_magnitude || 0,
                    max_magnitude: item.max_magnitude || 0,
                    depth: item.avg_depth || 0,
                    latitude: 0,
                    longitude: 0
                }));
                
                console.log(`Processed ${keyName}:`, earthquakeData[keyName].length, 'items');
            } else {
                console.error(`Failed to load ${period} data:`, response.status);
            }
        }
        
        // Debug final data
        console.log('=== FINAL EARTHQUAKE DATA ===');
        Object.keys(earthquakeData).forEach(key => {
            console.log(`${key}:`, {
                length: earthquakeData[key].length,
                sample: earthquakeData[key].slice(0, 2).map(d => ({
                    date: d.date.toLocaleDateString(),
                    count: d.count,
                    magnitude: d.magnitude,
                    depth: d.depth
                }))
            });
        });
        
        // Check if any period has insufficient data (less than minimum required)
        const minRequiredData = { daily: 7, weekly: 4, monthly: 3 }; // Minimum points to show meaningful charts
        const hasData = {
            daily: earthquakeData.daily && earthquakeData.daily.length >= minRequiredData.daily,
            weekly: earthquakeData.weekly && earthquakeData.weekly.length >= minRequiredData.weekly,
            monthly: earthquakeData.monthly && earthquakeData.monthly.length >= minRequiredData.monthly
        };
        
        console.log('Data availability (sufficient data):', hasData);
        console.log('Actual data lengths:', {
            daily: earthquakeData.daily ? earthquakeData.daily.length : 0,
            weekly: earthquakeData.weekly ? earthquakeData.weekly.length : 0,
            monthly: earthquakeData.monthly ? earthquakeData.monthly.length : 0
        });
        
        // Always generate fallback for insufficient data
        if (!hasData.daily) {
            console.log('Generating fallback daily data (insufficient data)...');
            earthquakeData.daily = generateSampleData(30, 'day');
        }
        if (!hasData.weekly) {
            console.log('Generating fallback weekly data (insufficient data)...');
            earthquakeData.weekly = generateSampleData(12, 'week');
        }
        if (!hasData.monthly) {
            console.log('Generating fallback monthly data (insufficient data)...');
            earthquakeData.monthly = generateSampleData(12, 'month');
        }
        
    } catch (error) {
        console.error('Error loading time series data:', error);
        generateFallbackTimeSeriesData();
    }
}

// Generate fallback data if API fails
function generateFallbackTimeSeriesData() {
    console.log('Generating comprehensive fallback time series data...');
    
    // Generate more diverse data
    earthquakeData = {
        daily: generateSampleData(30, 'day'),
        weekly: generateSampleData(12, 'week'), 
        monthly: generateSampleData(12, 'month')
    };
    
    // Add some variation to make data more realistic
    ['daily', 'weekly', 'monthly'].forEach(period => {
        earthquakeData[period].forEach((item, index) => {
            // Add some realistic patterns
            if (period === 'weekly') {
                // Add weekly patterns - more activity mid-week
                const dayOfWeek = index % 7;
                item.count = Math.floor(item.count * (0.7 + 0.3 * Math.sin(dayOfWeek * Math.PI / 3.5)));
            } else if (period === 'monthly') {
                // Add monthly patterns - varying activity
                item.count = Math.floor(item.count * (0.8 + 0.4 * Math.sin(index * Math.PI / 6)));
            }
            
            // Ensure magnitude distribution is realistic
            if (item.magnitude < 2) item.magnitude = 2 + Math.random();
            if (item.magnitude > 7) item.magnitude = 6 + Math.random();
        });
    });
    
    // Debug fallback data
    console.log('Comprehensive fallback data generated:', {
        daily: earthquakeData.daily.length,
        weekly: earthquakeData.weekly.length,
        monthly: earthquakeData.monthly.length
    });
    
    // Show sample data for each period
    Object.keys(earthquakeData).forEach(key => {
        console.log(`${key} sample:`, earthquakeData[key].slice(0, 3).map(d => ({
            date: d.date.toLocaleDateString(),
            count: d.count,
            magnitude: d.magnitude.toFixed(1)
        })));
    });
}

// Load correlation matrix
async function loadCorrelationMatrix() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/correlation`);
        if (!response.ok) throw new Error('Failed to fetch correlation');
        
        const correlationData = await response.json();
        renderCorrelationMatrix(correlationData);
        
    } catch (error) {
        console.error('Error loading correlation matrix:', error);
        // Fallback correlation matrix
        const fallbackData = {
            variables: ['Cường độ', 'Độ sâu', 'Vĩ độ', 'Kinh độ'],
            matrix: [
                [1.00, -0.15, 0.05, -0.03],
                [-0.15, 1.00, 0.08, 0.02],
                [0.05, 0.08, 1.00, 0.12],
                [-0.03, 0.02, 0.12, 1.00]
            ]
        };
        renderCorrelationMatrix(fallbackData);
    }
}

// Load predictions
async function loadPredictions() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/predictions`);
        if (!response.ok) throw new Error('Failed to fetch predictions');
        
        const data = await response.json();
        updatePredictionsDisplay(data);
        
    } catch (error) {
        console.error('Error loading predictions:', error);
        // Fallback predictions
        updatePredictionsDisplay({
            predictions: [
                { type: 'magnitude', value: 4.2, confidence: 85 },
                { type: 'depth', value: 45.8, confidence: 78 }
            ]
        });
    }
}

// Navigation functionality
function initializeNavigation() {
    const hamburger = document.getElementById('hamburger');
    const navLinksMobile = document.getElementById('navLinksMobile');
    const mobileLinks = navLinksMobile.querySelectorAll('a');

    hamburger.addEventListener('click', function () {
        hamburger.classList.toggle('active');
        navLinksMobile.classList.toggle('active');
    });

    // Close mobile menu when a link is clicked
    mobileLinks.forEach(link => {
        link.addEventListener('click', function () {
            hamburger.classList.remove('active');
            navLinksMobile.classList.remove('active');
        });
    });

    // Close mobile menu when scrolling
    window.addEventListener('scroll', function () {
        hamburger.classList.remove('active');
        navLinksMobile.classList.remove('active');
    });

    // Navbar scroll effect
    window.addEventListener('scroll', function () {
        const navbar = document.getElementById('navbar');
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // Active navigation highlighting
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

    // Smooth scrolling
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

// Generate sample earthquake data (fallback)
function generateSampleData(count, period) {
    const data = [];
    const now = new Date();
    
    console.log(`Generating ${count} sample data points for period: ${period}`);
    
    for (let i = count - 1; i >= 0; i--) {
        const date = new Date(now);
        
        if (period === 'day') {
            date.setDate(date.getDate() - i);
        } else if (period === 'week') {
            date.setDate(date.getDate() - (i * 7));
        } else if (period === 'month') {
            date.setMonth(date.getMonth() - i);
        }
        
        // Generate realistic earthquake data with variation based on period
        const baseMagnitude = 3 + Math.random() * 4; // 3-7 magnitude range
        const magnitude = Math.round(baseMagnitude * 10) / 10; // Round to 1 decimal
        const depth = 10 + Math.random() * 150; // 10-160 km depth
        
        // Vary count based on period type
        let count;
        if (period === 'day') {
            count = Math.floor(Math.random() * 20) + 5; // 5-25 per day
        } else if (period === 'week') {
            count = Math.floor(Math.random() * 100) + 20; // 20-120 per week
        } else {
            count = Math.floor(Math.random() * 400) + 50; // 50-450 per month
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

// Initialize all charts
function initializeCharts() {
    // Wait a bit to ensure DOM elements are ready
    setTimeout(() => {
        initializeLineChart();
        initializeScatterChart();
        initializeHistogramChart();
        initializeTrendChart();
        initializeSeasonalChart();
    }, 100);
}

// Line Chart - Time series of earthquake frequency
function initializeLineChart() {
    const canvas = document.getElementById('lineChart');
    if (!canvas) {
        console.error('lineChart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    const keyMapping = { day: 'daily', week: 'weekly', month: 'monthly' };
    const data = earthquakeData[keyMapping[currentPeriod]] || [];
    
    console.log(`Line Chart - Period: ${currentPeriod}, Key: ${keyMapping[currentPeriod]}, Data length: ${data.length}`);
    
    const minRequiredData = { day: 7, week: 4, month: 3 };
    if (data.length < minRequiredData[currentPeriod]) {
        console.warn(`Insufficient data for line chart (${data.length} items, need ${minRequiredData[currentPeriod]}), using fallback`);
        const fallbackCounts = { day: 30, week: 12, month: 12 };
        data = generateSampleData(fallbackCounts[currentPeriod], currentPeriod);
        earthquakeData[keyMapping[currentPeriod]] = data;
        console.log(`Generated ${data.length} fallback data points for line chart`);
    }
    
    if (lineChart) {
        lineChart.destroy();
    }
    
    lineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date.toLocaleDateString()),
            datasets: [{
                label: 'Số lượng động đất',
                data: data.map(d => d.count),
                borderColor: '#ff4444',
                backgroundColor: 'rgba(255, 68, 68, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#ff4444',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 5
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
                    beginAtZero: true,
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

// Scatter Chart - Magnitude vs Depth
function initializeScatterChart() {
    const canvas = document.getElementById('scatterChart');
    if (!canvas) {
        console.error('scatterChart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    const keyMapping = { day: 'daily', week: 'weekly', month: 'monthly' };
    const data = earthquakeData[keyMapping[currentPeriod]] || [];
    
    console.log(`Scatter Chart - Period: ${currentPeriod}, Data length: ${data.length}`);
    
    const minRequiredData = { day: 7, week: 4, month: 3 };
    if (data.length < minRequiredData[currentPeriod]) {
        console.warn(`Insufficient data for scatter chart (${data.length} items, need ${minRequiredData[currentPeriod]}), using fallback`);
        const fallbackCounts = { day: 30, week: 12, month: 12 };
        data = generateSampleData(fallbackCounts[currentPeriod], currentPeriod);
        earthquakeData[keyMapping[currentPeriod]] = data;
        console.log(`Generated ${data.length} fallback data points for scatter chart`);
    }
    
    if (scatterChart) {
        scatterChart.destroy();
    }
    
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
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    title: {
                        display: true,
                        text: 'Độ sâu (km)',
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
                        text: 'Cường độ (Richter)',
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

// Histogram Chart - Magnitude distribution
function initializeHistogramChart() {
    const canvas = document.getElementById('histogramChart');
    if (!canvas) {
        console.error('histogramChart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    const keyMapping = { day: 'daily', week: 'weekly', month: 'monthly' };
    const data = earthquakeData[keyMapping[currentPeriod]] || [];
    
    console.log(`Histogram Chart - Period: ${currentPeriod}, Data length: ${data.length}`);
    
    const minRequiredData = { day: 7, week: 4, month: 3 };
    if (data.length < minRequiredData[currentPeriod]) {
        console.warn(`Insufficient data for histogram chart (${data.length} items, need ${minRequiredData[currentPeriod]}), using fallback`);
        const fallbackCounts = { day: 30, week: 12, month: 12 };
        data = generateSampleData(fallbackCounts[currentPeriod], currentPeriod);
        earthquakeData[keyMapping[currentPeriod]] = data;
        console.log(`Generated ${data.length} fallback data points for histogram chart`);
    }
    
    // Create magnitude bins
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
    
    if (histogramChart) {
        histogramChart.destroy();
    }
    
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
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Tần suất',
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
                        text: 'Cường độ (Richter)',
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

// Trend Chart - Resampled data
function initializeTrendChart() {
    const canvas = document.getElementById('trendChart');
    if (!canvas) {
        console.error('trendChart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    const data = earthquakeData[currentResample === 'week' ? 'weekly' : 'monthly'] || [];
    
    // Calculate moving average for trend
    const movingAvg = calculateMovingAverage(data.map(d => d.magnitude), 3);
    
    if (trendChart) {
        trendChart.destroy();
    }
    
    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date.toLocaleDateString()),
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
                    label: 'Xu hướng (MA)',
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

// Seasonal Chart - Monthly patterns
function initializeSeasonalChart() {
    const canvas = document.getElementById('seasonalChart');
    if (!canvas) {
        console.error('seasonalChart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    
    // Use monthly data if available, otherwise generate seasonal pattern
    let seasonalData;
    if (earthquakeData.monthly && earthquakeData.monthly.length > 0) {
        // Group by month and calculate averages
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
    } else {
        // Generate seasonal pattern (fallback)
        const months = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T10', 'T11', 'T12'];
        seasonalData = months.map((month, index) => {
            const baseLine = 15;
            const seasonal = Math.sin((index / 12) * 2 * Math.PI) * 5;
            const noise = (Math.random() - 0.5) * 3;
            return Math.max(0, baseLine + seasonal + noise);
        });
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

// Calculate moving average
function calculateMovingAverage(data, windowSize) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < windowSize - 1) {
            result.push(null);
        } else {
            const window = data.slice(i - windowSize + 1, i + 1);
            const average = window.reduce((sum, val) => sum + val, 0) / windowSize;
            result.push(average);
        }
    }
    return result;
}

// Render correlation matrix
function renderCorrelationMatrix(correlationData) {
    const correlationMatrix = document.getElementById('correlationMatrix');
    
    if (!correlationMatrix) {
        console.error('correlationMatrix element not found');
        return;
    }
    
    const variables = correlationData.variables;
    const correlations = correlationData.matrix;
    
    correlationMatrix.style.gridTemplateColumns = `repeat(${variables.length + 1}, 1fr)`;
    
    // Clear existing content
    correlationMatrix.innerHTML = '';
    
    // Add headers
    correlationMatrix.innerHTML = '<div class="correlation-cell header"></div>';
    variables.forEach(variable => {
        correlationMatrix.innerHTML += `<div class="correlation-cell header">${variable}</div>`;
    });
    
    // Add correlation values
    variables.forEach((rowVar, i) => {
        correlationMatrix.innerHTML += `<div class="correlation-cell header">${rowVar}</div>`;
        correlations[i].forEach(correlation => {
            const cell = document.createElement('div');
            cell.className = 'correlation-cell';
            cell.innerHTML = `<div class="correlation-value">${correlation.toFixed(2)}</div>`;
            
            // Color based on correlation strength
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

// Update predictions display
function updatePredictionsDisplay(data) {
    if (!data.predictions || data.predictions.length === 0) return;
    
    // Find magnitude prediction
    const magPrediction = data.predictions.find(p => p.type === 'magnitude');
    if (magPrediction) {
        const magnitudeElement = document.getElementById('predictedMagnitude');
        if (magnitudeElement) {
            magnitudeElement.textContent = magPrediction.value.toFixed(1);
        }
        
        // Update risk level based on magnitude
        updateRiskLevel(magPrediction.value);
    }
    
    // Find depth prediction
    const depthPrediction = data.predictions.find(p => p.type === 'depth');
    if (depthPrediction) {
        const depthElement = document.getElementById('predictedDepth');
        if (depthElement) {
            depthElement.textContent = depthPrediction.value.toFixed(1);
        }
    }
}

// Update risk level display
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

// Animate counter values
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

// Setup event listeners
function setupEventListeners() {
    // Time period selector
    const timeBtns = document.querySelectorAll('.time-btn');
    timeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            timeBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentPeriod = this.dataset.period;
            console.log('=== PERIOD CHANGED ===');
            console.log('Selected period:', currentPeriod);
            console.log('Available data before update:', Object.keys(earthquakeData).map(key => `${key}: ${earthquakeData[key] ? earthquakeData[key].length : 0}`));
            
            // Force ensure we have enough data for this period
            const keyMapping = { day: 'daily', week: 'weekly', month: 'monthly' };
            const minRequiredData = { day: 7, week: 4, month: 3 };
            const currentKey = keyMapping[currentPeriod];
            const currentData = earthquakeData[currentKey];
            
            if (!currentData || currentData.length < minRequiredData[currentPeriod]) {
                console.log(`Insufficient data for ${currentPeriod}, generating fallback immediately`);
                const fallbackCounts = { day: 30, week: 12, month: 12 };
                earthquakeData[currentKey] = generateSampleData(fallbackCounts[currentPeriod], currentPeriod);
            }
            
            updateTimeSeriesCharts();
        });
    });
    
    // Chart options for trend analysis
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
}

// Update time series charts when period changes
function updateTimeSeriesCharts() {
    // Sửa mapping key
    const keyMapping = { day: 'daily', week: 'weekly', month: 'monthly' };
    let lineData = earthquakeData[keyMapping[currentPeriod]];
    
    console.log(`Updating charts - Period: ${currentPeriod}, Key: ${keyMapping[currentPeriod]}`);
    console.log('Line data length:', lineData ? lineData.length : 'undefined');
    console.log('Sample line data:', lineData ? lineData.slice(0, 3) : 'No data');
    
    // If insufficient data, generate fallback for this specific period
    const minRequiredData = { day: 7, week: 4, month: 3 };
    if (!lineData || lineData.length < minRequiredData[currentPeriod]) {
        console.warn(`Insufficient data for period ${currentPeriod} (${lineData ? lineData.length : 0} items, need ${minRequiredData[currentPeriod]}), generating fallback...`);
        const fallbackCounts = { day: 30, week: 12, month: 12 };
        earthquakeData[keyMapping[currentPeriod]] = generateSampleData(fallbackCounts[currentPeriod], currentPeriod);
        lineData = earthquakeData[keyMapping[currentPeriod]];
        console.log(`Generated fallback data: ${lineData.length} items`);
    }
    
    // Update Line Chart
    if (lineChart && lineData && lineData.length > 0) {
        lineChart.data.labels = lineData.map(d => d.date.toLocaleDateString());
        lineChart.data.datasets[0].data = lineData.map(d => d.count);
        lineChart.update();
        console.log(`Line chart updated with ${lineData.length} data points`);
    }
    
    // Update Scatter Chart  
    if (scatterChart && lineData && lineData.length > 0) {
        scatterChart.data.datasets[0].data = lineData.map(d => ({
            x: d.magnitude,
            y: d.depth
        }));
        scatterChart.update();
        console.log(`Scatter chart updated with ${lineData.length} data points`);
    }
    
    // Update Histogram
    if (histogramChart && lineData && lineData.length > 0) {
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
        console.log(`Histogram updated with bins:`, binCounts);
    }
}

// Update trend chart when resample period changes
function updateTrendChart() {
    const data = earthquakeData[currentResample === 'week' ? 'weekly' : 'monthly'];
    
    if (trendChart && data) {
        const movingAvg = calculateMovingAverage(data.map(d => d.magnitude), 3);
        
        trendChart.data.labels = data.map(d => d.date.toLocaleDateString());
        trendChart.data.datasets[0].data = data.map(d => d.magnitude);
        trendChart.data.datasets[1].data = movingAvg;
        trendChart.update();
    }
}

// Load fallback data if API is not available
function loadFallbackData() {
    console.log('Loading fallback data...');
    generateFallbackTimeSeriesData();
    initializeCharts();
    
    // Fallback correlation matrix
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
    
    // Fallback predictions
    updatePredictionsDisplay({
        predictions: [
            { type: 'magnitude', value: 4.2, confidence: 85 },
            { type: 'depth', value: 45.8, confidence: 78 }
        ]
    });
}

// Mini charts animation (keeping original functionality)
function drawMiniChart(canvasId, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    // Generate random data points
    const points = [];
    for (let i = 0; i < 10; i++) {
        points.push(Math.random() * canvas.height);
    }

    // Draw line
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

    // Draw gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
    gradient.addColorStop(0, color + '40');
    gradient.addColorStop(1, color + '00');

    ctx.lineTo(canvas.width, canvas.height);
    ctx.lineTo(0, canvas.height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();
}

// Initialize mini charts
setTimeout(() => {
    drawMiniChart('miniChart1', '#00ffcc');
    drawMiniChart('miniChart2', '#ff0080');
    drawMiniChart('miniChart3', '#00ccff');
    drawMiniChart('miniChart4', '#ffcc00');
    drawMiniChart('miniChart5', '#ff6b6b');
    drawMiniChart('miniChart6', '#4ecdc4');
}, 100);

// Animate stats on scroll
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

// Add slide up animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideUp {
        from {
            transform: scaleY(0);
            transform-origin: bottom;
        }
        to {
            transform: scaleY(1);
            transform-origin: bottom;
        }
    }
`;
document.head.appendChild(style);

// Metrics animation on scroll
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

// Initialize metrics animation state
document.querySelectorAll('.metric-item').forEach(item => {
    item.style.transform = 'translateY(20px)';
    item.style.opacity = '0';
    item.style.transition = 'all 0.5s ease';
});