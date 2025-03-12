// map_app/static/map_app/js/map.js

// Initialize the map
let map = L.map('map').setView([40.7128, -74.0060], 4); // Default center on NYC
let markers = [];
let heatmapLayer = null;
let currentMarkers = [];
let selectedMetric = 'temperature';
let realTimeUpdatesEnabled = false;
let updateInterval = null;

// Add OpenStreetMap as base layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Initialize the map
function initMap() {
    // Load markers from API
    fetchMarkers();
    
    // Set up event listeners
    document.getElementById('metricSelect').addEventListener('change', function() {
        selectedMetric = this.value;
        updateVisualization();
    });
    
    document.getElementById('realTimeUpdates').addEventListener('change', function() {
        realTimeUpdatesEnabled = this.checked;
        
        if (realTimeUpdatesEnabled) {
            // Enable real-time updates every 60 seconds
            updateInterval = setInterval(function() {
                fetchMarkers();
            }, 60000);
        } else {
            // Disable real-time updates
            if (updateInterval) {
                clearInterval(updateInterval);
                updateInterval = null;
            }
        }
    });
    
    document.getElementById('toggleHeatmap').addEventListener('click', function() {
        document.getElementById('toggleMarkers').classList.remove('active');
        this.classList.add('active');
        showHeatmap();
    });
    
    document.getElementById('toggleMarkers').addEventListener('click', function() {
        document.getElementById('toggleHeatmap').classList.remove('active');
        this.classList.add('active');
        showMarkers();
    });
    
    // Initialize trend chart
    initTrendChart();
}

// Fetch markers data from API
function fetchMarkers() {
    fetch('/api/markers/')
        .then(response => response.json())
        .then(data => {
            markers = data.results || data;
            updateVisualization();
            updateLatestReadingsTable();
        })
        .catch(error => console.error('Error fetching markers:', error));
}

// Update visualization based on current mode (markers or heatmap)
function updateVisualization() {
    if (document.getElementById('toggleHeatmap').classList.contains('active')) {
        showHeatmap();
    } else {
        showMarkers();
    }
    updateLegend();
}

// Display markers on the map
function showMarkers() {
    // Clear previous markers and heatmap
    clearMap();
    
    // Add markers to the map
    markers.forEach(marker => {
        const value = getMetricValue(marker, selectedMetric);
        if (value !== null) {
            const markerColor = getColorForValue(value, selectedMetric);
            
            const mapMarker = L.circleMarker([marker.latitude, marker.longitude], {
                radius: 8,
                fillColor: markerColor,
                color: '#000',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(map);
            
            // Add the marker to the current markers array
            currentMarkers.push(mapMarker);
            
            // Add popup and click event
            mapMarker.bindPopup(`<strong>${marker.name}</strong><br>${getMetricDisplay(selectedMetric)}: ${value}`);
            mapMarker.on('click', function() {
                openMarkerModal(marker.id);
            });
        }
    });
    
    // Remove heatmap layer if it exists
    if (map.hasLayer(heatmapLayer)) {
        map.removeLayer(heatmapLayer);
    }
}

// Display heatmap on the map
function showHeatmap() {
    // Clear previous markers
    clearMap();
    
    // Prepare heatmap data
    const heatData = [];
    
    markers.forEach(marker => {
        const value = getMetricValue(marker, selectedMetric);
        if (value !== null) {
            // Add to heatmap data with intensity based on value
            // Note: adjusted intensity for better visualization
            const intensity = normalizeValueForHeatmap(value, selectedMetric);
            heatData.push([marker.latitude, marker.longitude, intensity]);
        }
    });
    
    // Create and add heatmap layer
    if (heatmapLayer) {
        map.removeLayer(heatmapLayer);
    }
    
    heatmapLayer = L.heatLayer(heatData, {
        radius: 25,
        blur: 15,
        maxZoom: 10,
        gradient: getGradientForMetric(selectedMetric)
    }).addTo(map);
}

// Clear all markers from the map
function clearMap() {
    currentMarkers.forEach(marker => {
        map.removeLayer(marker);
    });
    currentMarkers = [];
}

// Open modal with marker details
function openMarkerModal(markerId) {
    const modal = new bootstrap.Modal(document.getElementById('markerModal'));
    const modalBody = document.getElementById('markerModalBody');
    const viewDetailBtn = document.getElementById('viewDetailBtn');
    const downloadCSV = document.getElementById('downloadCSV');
    const downloadJSON = document.getElementById('downloadJSON');
    
    // Reset modal body and show loading spinner
    modalBody.innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    
    // Update download links
    downloadCSV.href = `/api/markers/${markerId}/download_data/?format=csv`;
    downloadJSON.href = `/api/markers/${markerId}/download_data/?format=json`;
    
    // Update view details link
    viewDetailBtn.href = `/markers/${markerId}/`;
    
    // Fetch marker details
    fetch(`/api/markers/${markerId}/`)
        .then(response => response.json())
        .then(marker => {
            // Update modal title
            document.getElementById('markerModalLabel').textContent = marker.name;
            
            // Create HTML for environmental data
            let envDataHtml = '';
            if (marker.latest_data) {
                const data = marker.latest_data;
                
                envDataHtml = `
                    <div class="row">
                        <div class="col-md-6">
                            <ul class="list-group">
                                <li class="list-group-item"><strong>Temperature:</strong> ${data.temperature}</li>
                                <li class="list-group-item"><strong>Humidity:</strong> ${data.humidity}</li>
                                <li class="list-group-item"><strong>Air Quality Index:</strong> ${data.air_quality_index}</li>
                                <li class="list-group-item"><strong>Updated At:</strong> ${new Date(data.updated_at).toLocaleString()}</li>
                            </ul>
                        </div>
                    </div>
                `;
            } else {
                envDataHtml = '<p>No data available for this marker.</p>';
            }
            
            // Update modal body with environmental data
            modalBody.innerHTML = envDataHtml;
            
            // Show the modal
            modal.show();
        })
        .catch(error => console.error('Error fetching marker details:', error));
}

// Update the latest readings table
function updateLatestReadingsTable() {
    const tableBody = document.getElementById('latestReadingsTable').querySelector('tbody');
    tableBody.innerHTML = '';

    markers.forEach(marker => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${marker.name}</td>
            <td>${getMetricValue(marker, 'temperature')}</td>
            <td>${getMetricValue(marker, 'humidity')}</td>
            <td>${getMetricValue(marker, 'air_quality_index')}</td>
            <td>${new Date(marker.updated_at).toLocaleString()}</td>
        `;
        tableBody.appendChild(row);
    });
}

// Get the value of the selected metric from the marker data
function getMetricValue(marker, metric) {
    return marker.latest_data ? marker.latest_data[metric] : null;
}

// Get the display name for the selected metric
function getMetricDisplay(metric) {
    const metricDisplayNames = {
        temperature: 'Temperature',
        humidity: 'Humidity',
        precipitation: 'Precipitation',
        air_quality_index: 'Air Quality Index',
        wind_speed: 'Wind Speed',
        barometric_pressure: 'Barometric Pressure',
        uv_index: 'UV Index',
        visibility: 'Visibility',
        cloud_cover: 'Cloud Cover',
        soil_moisture: 'Soil Moisture',
        water_level: 'Water Level',
        vegetation_index: 'Vegetation Index'
    };
    return metricDisplayNames[metric] || metric;
}

// Get color for the marker based on the value and metric
function getColorForValue(value, metric) {
    // Define color ranges for different metrics
    const colorRanges = {
        temperature: ['#00f', '#0ff', '#0f0', '#ff0', '#f00'],
        humidity: ['#f00', '#ff0', '#0f0', '#0ff', '#00f'],
        air_quality_index: ['#0f0', '#ff0', '#f90', '#f00', '#900']
        // Add more metrics and their color ranges as needed
    };

    const ranges = colorRanges[metric] || ['#0f0', '#ff0', '#f00'];
    const index = Math.min(Math.floor(value / (100 / ranges.length)), ranges.length - 1);
    return ranges[index];
}

// Normalize value for heatmap intensity
function normalizeValueForHeatmap(value, metric) {
    // Normalize based on metric-specific ranges
    const metricRanges = {
        temperature: [0, 50],
        humidity: [0, 100],
        air_quality_index: [0, 500]
        // Add more metrics and their ranges as needed
    };

    const [min, max] = metricRanges[metric] || [0, 100];
    return (value - min) / (max - min);
}

// Get gradient for heatmap based on the metric
function getGradientForMetric(metric) {
    const gradients = {
        temperature: {0.4: 'blue', 0.6: 'cyan', 0.7: 'lime', 0.8: 'yellow', 1.0: 'red'},
        humidity: {0.4: 'red', 0.6: 'yellow', 0.7: 'lime', 0.8: 'cyan', 1.0: 'blue'},
        air_quality_index: {0.4: 'lime', 0.6: 'yellow', 0.7: 'orange', 0.8: 'red', 1.0: 'purple'}
        // Add more gradients as needed
    };
    return gradients[metric] || {0.4: 'lime', 0.6: 'yellow', 0.7: 'orange', 0.8: 'red', 1.0: 'purple'};
}

// Initialize trend chart
function initTrendChart() {
    const ctx = document.getElementById('trendChart').getContext('2d');
    const trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [], // Dates will be populated dynamically
            datasets: [{
                label: 'Temperature',
                data: [], // Data will be populated dynamically
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1,
                fill: false
            }]
        },
        options: {
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day'
                    }
                },
                y: {
                    beginAtZero: true
                }
            }
        }
    });

    // Fetch trend data and update chart
    fetchTrendData(trendChart);
}

// Fetch trend data from API and update chart
function fetchTrendData(chart) {
    fetch(`/api/trend_data/?metric=${selectedMetric}`)
        .then(response => response.json())
        .then(data => {
            chart.data.labels = data.dates;
            chart.data.datasets[0].data = data.values;
            chart.update();
        })
        .catch(error => console.error('Error fetching trend data:', error));
}

// Update legend based on selected metric
function updateLegend() {
    const legendContent = document.getElementById('legendContent');
    legendContent.innerHTML = '';

    const gradient = getGradientForMetric(selectedMetric);
    for (const [key, color] of Object.entries(gradient)) {
        const legendItem = document.createElement('div');
        legendItem.innerHTML = `<span style="background-color: ${color}; width: 20px; height: 20px; display: inline-block;"></span> ${key * 100}%`;
        legendContent.appendChild(legendItem);
    }
}

// Initialize the map
document.addEventListener('DOMContentLoaded', function() {
    initMap();
});
