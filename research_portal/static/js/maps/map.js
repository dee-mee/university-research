// Initialize variables
let map;
let markers = [];
let heatmapLayer = null;
let currentMarkers = [];
let selectedMetric = 'temperature';
let realTimeUpdatesEnabled = false;
let updateInterval = null;
let trendChart = null;

// Initialize the map when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the map
    map = L.map('map').setView([40.7128, -74.0060], 4); // Default center on NYC
    
    // Add OpenStreetMap as base layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Set up event listeners
    setupEventListeners();
    
    // Load initial data
    fetchMarkers();
    
    // Initialize trend chart
    initTrendChart();
    
    // Initialize legend
    updateLegend();
});

// Set up event listeners for all controls
function setupEventListeners() {
    // Metric selector
    const metricSelect = document.getElementById('metricSelect');
    if (metricSelect) {
        metricSelect.addEventListener('change', function() {
            selectedMetric = this.value;
            updateVisualization();
            // Also update the trend chart when metric changes
            fetchTrendData();
        });
    }
    
    // Real-time updates toggle
    const realTimeUpdates = document.getElementById('realTimeUpdates');
    if (realTimeUpdates) {
        realTimeUpdates.addEventListener('change', function() {
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
    }
    
    // Heatmap toggle
    const toggleHeatmap = document.getElementById('toggleHeatmap');
    if (toggleHeatmap) {
        toggleHeatmap.addEventListener('click', function() {
            document.getElementById('toggleMarkers').classList.remove('active');
            this.classList.add('active');
            showHeatmap();
        });
    }
    
    // Markers toggle
    const toggleMarkers = document.getElementById('toggleMarkers');
    if (toggleMarkers) {
        toggleMarkers.addEventListener('click', function() {
            document.getElementById('toggleHeatmap').classList.remove('active');
            this.classList.add('active');
            showMarkers();
        });
    }
    
    // Trend metric selector
    const trendMetricSelect = document.getElementById('trendMetricSelect');
    if (trendMetricSelect) {
        trendMetricSelect.addEventListener('change', function() {
            fetchTrendData();
        });
    }
}

// Fetch markers data from API
function fetchMarkers() {
    // Show loading indicator if needed
    console.log("Fetching markers data...");
    
    fetch('/api/markers/')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            console.log("Markers data received:", data);
            markers = data.results || data;
            updateVisualization();
            updateLatestReadingsTable();
        })
        .catch(error => {
            console.error('Error fetching markers:', error);
            // Display error message to user
            alert('Failed to load map data. Please try again later.');
        });
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
    
    // Check if markers array exists and has items
    if (!markers || markers.length === 0) {
        console.warn("No marker data available to display");
        return;
    }
    
    // Add markers to the map
    markers.forEach(marker => {
        if (!marker.latitude || !marker.longitude) {
            console.warn("Marker missing coordinates:", marker);
            return;
        }
        
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
            
            // Format popup content
            const popupContent = `
                <div class="marker-popup">
                    <h5>${marker.name || 'Unnamed Location'}</h5>
                    <p><strong>${getMetricDisplay(selectedMetric)}:</strong> ${value}</p>
                    <button class="btn btn-sm btn-primary popup-details-btn" 
                            onclick="openMarkerModal('${marker.id}')">View Details</button>
                </div>
            `;
            
            // Add popup
            mapMarker.bindPopup(popupContent);
            
            // Add click event (alternative approach if popup button doesn't work)
            mapMarker.on('click', function() {
                // Close any open popups first
                mapMarker.closePopup();
                // Open modal after a short delay to avoid conflicts
                setTimeout(() => {
                    openMarkerModal(marker.id);
                }, 100);
            });
        }
    });
    
    // Remove heatmap layer if it exists
    if (heatmapLayer && map.hasLayer(heatmapLayer)) {
        map.removeLayer(heatmapLayer);
    }
}

// Display heatmap on the map
function showHeatmap() {
    // Clear previous markers
    clearMap();
    
    // Check if markers array exists and has items
    if (!markers || markers.length === 0) {
        console.warn("No marker data available for heatmap");
        return;
    }
    
    // Prepare heatmap data
    const heatData = [];
    
    markers.forEach(marker => {
        if (!marker.latitude || !marker.longitude) {
            console.warn("Marker missing coordinates:", marker);
            return;
        }
        
        const value = getMetricValue(marker, selectedMetric);
        if (value !== null) {
            // Add to heatmap data with intensity based on value
            const intensity = normalizeValueForHeatmap(value, selectedMetric);
            heatData.push([marker.latitude, marker.longitude, intensity]);
        }
    });
    
    // Check if we have data to display
    if (heatData.length === 0) {
        console.warn("No valid heatmap data to display");
        return;
    }
    
    // Remove existing heatmap layer
    if (heatmapLayer && map.hasLayer(heatmapLayer)) {
        map.removeLayer(heatmapLayer);
    }
    
    // Create and add heatmap layer
    try {
        heatmapLayer = L.heatLayer(heatData, {
            radius: 25,
            blur: 15,
            maxZoom: 10,
            gradient: getGradientForMetric(selectedMetric)
        }).addTo(map);
    } catch (error) {
        console.error("Error creating heatmap layer:", error);
        alert("Failed to create heatmap. Please try marker view instead.");
        // Fall back to marker view
        document.getElementById('toggleMarkers').click();
    }
}

// Clear all markers from the map
function clearMap() {
    currentMarkers.forEach(marker => {
        if (map.hasLayer(marker)) {
            map.removeLayer(marker);
        }
    });
    currentMarkers = [];
}

// Expose the openMarkerModal function to the global scope for popup button
window.openMarkerModal = function(markerId) {
    // Check if Bootstrap is available
    if (typeof bootstrap === 'undefined') {
        console.error("Bootstrap JS is not loaded - cannot open modal");
        alert("Cannot open details modal. Please check the console for errors.");
        return;
    }
    
    const modalElement = document.getElementById('markerModal');
    if (!modalElement) {
        console.error("Modal element not found in the DOM");
        return;
    }
    
    const modal = new bootstrap.Modal(modalElement);
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
    if (downloadCSV) downloadCSV.href = `/api/markers/${markerId}/download_data/?format=csv`;
    if (downloadJSON) downloadJSON.href = `/api/markers/${markerId}/download_data/?format=json`;
    
    // Update view details link
    if (viewDetailBtn) viewDetailBtn.href = `/markers/${markerId}/`;
    
    // Show the modal first, then fetch data
    modal.show();
    
    // Fetch marker details
    fetch(`/api/markers/${markerId}/`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(marker => {
            // Update modal title
            document.getElementById('markerModalLabel').textContent = marker.name || 'Marker Details';
            
            // Create HTML for environmental data
            let envDataHtml = '';
            if (marker.latest_data) {
                const data = marker.latest_data;
                
                // Create a table of all available metrics
                envDataHtml = `
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>Metric</th>
                                    <th>Value</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                
                // Add rows for each metric
                for (const [key, value] of Object.entries(data)) {
                    if (key !== 'updated_at') {
                        envDataHtml += `
                            <tr>
                                <td><strong>${getMetricDisplay(key)}</strong></td>
                                <td>${value}</td>
                            </tr>
                        `;
                    }
                }
                
                // Add updated timestamp
                envDataHtml += `
                            <tr>
                                <td><strong>Updated At</strong></td>
                                <td>${new Date(data.updated_at || marker.updated_at).toLocaleString()}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                `;
                
                // Add location info
                envDataHtml += `
                    <div class="mt-3">
                        <p><strong>Location:</strong> ${marker.latitude}, ${marker.longitude}</p>
                    </div>
                `;
            } else {
                envDataHtml = '<p>No data available for this marker.</p>';
            }
            
            // Update modal body with environmental data
            modalBody.innerHTML = envDataHtml;
        })
        .catch(error => {
            console.error('Error fetching marker details:', error);
            modalBody.innerHTML = '<div class="alert alert-danger">Failed to load marker details. Please try again later.</div>';
        });
};

// Update the latest readings table
function updateLatestReadingsTable() {
    const tableBody = document.getElementById('latestReadingsTable').querySelector('tbody');
    if (!tableBody) {
        console.error("Table body element not found");
        return;
    }
    
    tableBody.innerHTML = '';
    
    // Check if markers array exists and has items
    if (!markers || markers.length === 0) {
        const noDataRow = document.createElement('tr');
        noDataRow.innerHTML = '<td colspan="5" class="text-center">No data available</td>';
        tableBody.appendChild(noDataRow);
        return;
    }

    markers.forEach(marker => {
        const row = document.createElement('tr');
        
        // Format the date safely
        let updatedDate = 'N/A';
        try {
            updatedDate = new Date(marker.updated_at).toLocaleString();
        } catch (e) {
            console.warn("Invalid date format:", marker.updated_at);
        }
        
        row.innerHTML = `
            <td>${marker.name || 'Unnamed'}</td>
            <td>${getMetricValue(marker, 'temperature') ?? 'N/A'}</td>
            <td>${getMetricValue(marker, 'humidity') ?? 'N/A'}</td>
            <td>${getMetricValue(marker, 'air_quality_index') ?? 'N/A'}</td>
            <td>${updatedDate}</td>
        `;
        tableBody.appendChild(row);
    });
}

// Get the value of the selected metric from the marker data
function getMetricValue(marker, metric) {
    if (!marker || !marker.latest_data) return null;
    return marker.latest_data[metric] !== undefined ? marker.latest_data[metric] : null;
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
    return metricDisplayNames[metric] || metric.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// Get color for the marker based on the value and metric
function getColorForValue(value, metric) {
    // Define color ranges for different metrics
    const colorRanges = {
        temperature: [
            { max: 0, color: '#00f' },    // Blue for very cold
            { max: 15, color: '#0ff' },   // Cyan for cool
            { max: 25, color: '#0f0' },   // Green for moderate
            { max: 35, color: '#ff0' },   // Yellow for warm
            { max: Infinity, color: '#f00' } // Red for hot
        ],
        humidity: [
            { max: 20, color: '#f00' },   // Red for very dry
            { max: 40, color: '#ff0' },   // Yellow for dry
            { max: 60, color: '#0f0' },   // Green for moderate
            { max: 80, color: '#0ff' },   // Cyan for humid
            { max: Infinity, color: '#00f' } // Blue for very humid
        ],
        air_quality_index: [
            { max: 50, color: '#0f0' },   // Green for good
            { max: 100, color: '#ff0' },  // Yellow for moderate
            { max: 150, color: '#f90' },  // Orange for unhealthy for sensitive groups
            { max: 200, color: '#f00' },  // Red for unhealthy
            { max: Infinity, color: '#900' } // Dark red for very unhealthy/hazardous
        ],
        // Add default ranges for other metrics
        default: [
            { max: 20, color: '#0f0' },   // Green for low
            { max: 50, color: '#ff0' },   // Yellow for medium
            { max: Infinity, color: '#f00' } // Red for high
        ]
    };

    // Get the appropriate color range for the metric
    const ranges = colorRanges[metric] || colorRanges.default;
    
    // Find the color based on the value
    for (const range of ranges) {
        if (value <= range.max) {
            return range.color;
        }
    }
    
    // Default color if no range matches (shouldn't happen with Infinity)
    return '#f00';
}

// Normalize value for heatmap intensity
function normalizeValueForHeatmap(value, metric) {
    // Normalize based on metric-specific ranges
    const metricRanges = {
        temperature: [0, 50],     // 0-50°C
        humidity: [0, 100],       // 0-100%
        air_quality_index: [0, 500], // 0-500 AQI
        precipitation: [0, 100],   // 0-100mm
        wind_speed: [0, 100],      // 0-100 km/h
        barometric_pressure: [950, 1050], // 950-1050 hPa
        uv_index: [0, 11],         // 0-11+ UV index
        visibility: [0, 20],       // 0-20 km
        cloud_cover: [0, 100],     // 0-100%
        soil_moisture: [0, 100],   // 0-100%
        water_level: [0, 10],      // 0-10m
        vegetation_index: [0, 1]   // 0-1 NDVI
    };

    const [min, max] = metricRanges[metric] || [0, 100];
    
    // Ensure value is within the specified range
    const clampedValue = Math.max(min, Math.min(value, max));
    
    // Return normalized value (0-1)
    return (clampedValue - min) / (max - min);
}

// Get gradient for heatmap based on the metric
function getGradientForMetric(metric) {
    const gradients = {
        temperature: {0.2: 'blue', 0.4: 'cyan', 0.6: 'lime', 0.8: 'yellow', 1.0: 'red'},
        humidity: {0.2: 'red', 0.4: 'yellow', 0.6: 'lime', 0.8: 'cyan', 1.0: 'blue'},
        air_quality_index: {0.2: 'lime', 0.4: 'yellow', 0.6: 'orange', 0.8: 'red', 1.0: 'purple'},
        precipitation: {0.2: 'white', 0.4: 'lightblue', 0.6: 'blue', 0.8: 'darkblue', 1.0: 'purple'},
        wind_speed: {0.2: 'lightgreen', 0.4: 'green', 0.6: 'yellow', 0.8: 'orange', 1.0: 'red'},
        // Default gradient for other metrics
        default: {0.2: 'green', 0.4: 'yellow', 0.6: 'orange', 0.8: 'red', 1.0: 'darkred'}
    };
    return gradients[metric] || gradients.default;
}

// Initialize trend chart
function initTrendChart() {
    const ctx = document.getElementById('trendChart');
    if (!ctx) {
        console.error("Trend chart canvas element not found");
        return;
    }
    
    // Check if Chart.js is available
    if (typeof Chart === 'undefined') {
        console.error("Chart.js library is not loaded");
        return;
    }
    
    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [], // Dates will be populated dynamically
            datasets: [{
                label: getMetricDisplay('temperature'),
                data: [], // Data will be populated dynamically
                borderColor: 'rgba(75, 192, 192, 1)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderWidth: 2,
                tension: 0.1,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    mode: 'index',
                    intersect: false
                },
                legend: {
                    position: 'top',
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day',
                        displayFormats: {
                            day: 'MMM d'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: 'Value'
                    }
                }
            }
        }
    });

    // Fetch trend data and update chart
    fetchTrendData();
}

// Fetch trend data from API and update chart
function fetchTrendData() {
    // Get the selected metric for the trend chart
    const trendMetricSelect = document.getElementById('trendMetricSelect');
    const trendMetric = trendMetricSelect ? trendMetricSelect.value : selectedMetric;
    
    fetch(`/api/trend_data/?metric=${trendMetric}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            updateTrendChart(data, trendMetric);
        })
        .catch(error => {
            console.error('Error fetching trend data:', error);
            // Display message in chart area
            if (trendChart) {
                trendChart.data.labels = [];
                trendChart.data.datasets[0].data = [];
                trendChart.update();
            }
        });
}

// Update the trend chart with new data
function updateTrendChart(data, metric) {
    if (!trendChart) {
        return;
    }

    // Update chart labels and data
    trendChart.data.labels = data.map(entry => entry.date);
    trendChart.data.datasets[0].data = data.map(entry => entry.value);
    trendChart.data.datasets[0].label = getMetricDisplay(metric);

    // Update chart
    trendChart.update();
}

// // Fetch trend data from API and update chart
// function fetchTrendData(chart) {
//     fetch(`/api/trend_data/?metric=${selectedMetric}`)
//         .then(response => response.json())
//         .then(data => {
//             chart.data.labels = data.dates;
//             chart.data.datasets[0].data = data.values;
//             chart.update();
//         })
//         .catch(error => console.error('Error fetching trend data:', error));
// }

// // Update legend based on selected metric
// function updateLegend() {
//     const legendContent = document.getElementById('legendContent');
//     legendContent.innerHTML = '';

//     const gradient = getGradientForMetric(selectedMetric);
//     for (const [key, color] of Object.entries(gradient)) {
//         const legendItem = document.createElement('div');
//         legendItem.innerHTML = `<span style="background-color: ${color}; width: 20px; height: 20px; display: inline-block;"></span> ${key * 100}%`;
//         legendContent.appendChild(legendItem);
//     }
// }

// Initialize the map
document.addEventListener('DOMContentLoaded', function() {
    initMap();
});
