/**
 * Weather Station Hotspot Feature
 * Enhances the map with interactive hotspots for visualizing temperature and rainfall data
 */
class WeatherHotspot {
    constructor(mapInstance, apiBaseUrl) {
        this.map = mapInstance;
        this.apiBaseUrl = apiBaseUrl;
        this.stations = [];
        this.stationData = {};
        this.currentParameter = 'temperature'; // Default parameter
        this.timeRange = '7'; // Default time range in days
        
        // Color scales for different parameters
        this.colorScales = {
            temperature: [
                { value: -10, color: '#0022FF' }, // Very cold (blue)
                { value: 0, color: '#0099FF' },   // Cold (light blue)
                { value: 10, color: '#00FFFF' },  // Cool (cyan)
                { value: 20, color: '#FFFF00' },  // Warm (yellow)
                { value: 30, color: '#FF9900' },  // Hot (orange)
                { value: 40, color: '#FF0000' }   // Very hot (red)
            ],
            precipitation: [
                { value: 0, color: '#FFFFFF' },   // No rain (white)
                { value: 5, color: '#CCFFCC' },   // Light rain (light green)
                { value: 20, color: '#66CC66' },  // Moderate rain (medium green)
                { value: 50, color: '#009900' },  // Heavy rain (dark green)
                { value: 100, color: '#006600' }, // Very heavy rain (very dark green)
                { value: 200, color: '#003300' }  // Extreme rain (almost black green)
            ]
        };
        
        // Initialize the controls
        this.initControls();
    }
    
    /**
     * Initialize parameter selection controls
     */
    initControls() {
        // Create parameter control container if it doesn't exist
        if (!document.getElementById('parameter-controls')) {
            const controlsDiv = document.createElement('div');
            controlsDiv.id = 'parameter-controls';
            controlsDiv.className = 'parameter-controls';
            controlsDiv.innerHTML = `
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Data Parameters</h5>
                    </div>
                    <div class="card-body">
                        <div class="form-group mb-3">
                            <label for="parameter-select" class="form-label">Parameter:</label>
                            <select id="parameter-select" class="form-select">
                                <option value="temperature">Temperature (°C)</option>
                                <option value="precipitation">Rainfall (mm)</option>
                            </select>
                        </div>
                        <div class="form-group mb-3">
                            <label for="time-range-select" class="form-label">Time Range:</label>
                            <select id="time-range-select" class="form-select">
                                <option value="1">Last 24 Hours</option>
                                <option value="7" selected>Last 7 Days</option>
                                <option value="30">Last 30 Days</option>
                                <option value="90">Last 3 Months</option>
                            </select>
                        </div>
                        <button id="update-hotspots" class="btn btn-primary w-100">
                            <i class="fas fa-sync-alt me-2"></i>Update Map
                        </button>
                    </div>
                </div>
                <div class="card mt-3">
                    <div class="card-header">
                        <h5 class="mb-0">Legend</h5>
                    </div>
                    <div class="card-body p-2">
                        <div id="parameter-legend" class="d-flex flex-column"></div>
                    </div>
                </div>
            `;
            
            // Add to the map
            document.querySelector('.map-wrapper').appendChild(controlsDiv);
            
            // Add event listeners
            document.getElementById('parameter-select').addEventListener('change', (e) => {
                this.currentParameter = e.target.value;
                this.updateLegend();
            });
            
            document.getElementById('time-range-select').addEventListener('change', (e) => {
                this.timeRange = e.target.value;
            });
            
            document.getElementById('update-hotspots').addEventListener('click', () => {
                this.loadStationData();
            });
            
            // Initialize the legend
            this.updateLegend();
        }
    }
    
    /**
     * Update the legend based on the current parameter
     */
    updateLegend() {
        const legendDiv = document.getElementById('parameter-legend');
        legendDiv.innerHTML = '';
        
        const scale = this.colorScales[this.currentParameter];
        const unit = this.currentParameter === 'temperature' ? '°C' : 'mm';
        
        // Create legend items
        for (let i = scale.length - 1; i >= 0; i--) {
            const item = document.createElement('div');
            item.className = 'legend-item d-flex align-items-center mb-1';
            
            // Determine label text
            let labelText;
            if (i === scale.length - 1) {
                labelText = `> ${scale[i].value} ${unit}`;
            } else {
                labelText = `${scale[i].value} - ${scale[i+1].value} ${unit}`;
            }
            
            item.innerHTML = `
                <div class="legend-color me-2" style="background-color: ${scale[i].color}"></div>
                <div class="legend-label">${labelText}</div>
            `;
            
            legendDiv.appendChild(item);
        }
    }
    
    /**
     * Set the stations data
     */
    setStations(stations) {
        this.stations = stations;
    }
    
    /**
     * Load climate data for all stations
     */
    loadStationData() {
        // Show loading indicator
        this.showLoading(true);
        
        // Fetch data from API
        const url = `${this.apiBaseUrl}/api/climate-data/recent/?days=${this.timeRange}`;
        console.log("Fetching hotspot data from:", url);
        
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    // Try fallback path
                    const fallbackUrl = `${this.apiBaseUrl}/api/map-data/`;
                    console.log("Trying fallback URL:", fallbackUrl);
                    return fetch(fallbackUrl);
                }
                return response;
            })
            .then(response => response.json())
            .then(data => {
                // Process the data
                this.processStationData(data);
                
                // Update the markers
                this.updateMarkers();
                
                // Hide loading indicator
                this.showLoading(false);
            })
            .catch(error => {
                console.error("Error loading hotspot data:", error);
                this.showLoading(false);
                // Show error message
                if (window.weatherMap) {
                    window.weatherMap.showError(`Failed to load hotspot data: ${error.message}`);
                }
            });
    }
    
    /**
     * Process the station data
     */
    processStationData(data) {
        // Reset station data
        this.stationData = {};
        
        // Handle different response formats
        let climateData = [];
        
        if (Array.isArray(data)) {
            climateData = data;
        } else if (data.results && Array.isArray(data.results)) {
            climateData = data.results;
        } else if (data.recent_data && Array.isArray(data.recent_data)) {
            climateData = data.recent_data;
        } else if (data.stations && data.stations.features) {
            // Extract station info from map_data response
            this.stations = data.stations.features;
            
            if (data.recent_data) {
                climateData = data.recent_data;
            }
        }
        
        // Process climate data
        climateData.forEach(item => {
            const stationId = item.station;
            
            if (!this.stationData[stationId]) {
                this.stationData[stationId] = {
                    readings: [],
                    averages: {}
                };
            }
            
            // Add reading to station data
            this.stationData[stationId].readings.push(item);
        });
        
        // Calculate averages for each station
        for (const stationId in this.stationData) {
            const readings = this.stationData[stationId].readings;
            
            // Calculate average temperature
            const temperatures = readings
                .filter(r => r.temperature !== null && r.temperature !== undefined)
                .map(r => parseFloat(r.temperature));
                
            if (temperatures.length > 0) {
                this.stationData[stationId].averages.temperature = 
                    temperatures.reduce((sum, val) => sum + val, 0) / temperatures.length;
            }
            
            // Calculate total precipitation
            const precipitation = readings
                .filter(r => r.precipitation !== null && r.precipitation !== undefined)
                .map(r => parseFloat(r.precipitation));
                
            if (precipitation.length > 0) {
                this.stationData[stationId].averages.precipitation = 
                    precipitation.reduce((sum, val) => sum + val, 0);
            }
        }
        
        console.log("Processed station data:", this.stationData);
    }
    
    /**
     * Update the map markers based on the current parameter
     */
    updateMarkers() {
        if (!window.weatherMap) return;
        
        // Clear existing layers
        window.weatherMap.stationLayers.active.clearLayers();
        window.weatherMap.stationLayers.inactive.clearLayers();
        
        // Process each station
        this.stations.forEach(station => {
            try {
                // Get station properties
                const props = station.properties || station;
                const stationId = props.id || props.station_id || '';
                
                // Check if we have data for this station
                const hasData = this.stationData[stationId] && 
                                this.stationData[stationId].averages[this.currentParameter] !== undefined;
                
                // Create marker with color based on parameter value
                const marker = this.createHotspotMarker(station, hasData);
                
                // Determine if station is active
                const isActive = props.is_active !== undefined ? 
                    props.is_active : (props.status === 'active');
                
                // Add marker to appropriate layer group
                if (isActive) {
                    window.weatherMap.stationLayers.active.addLayer(marker);
                } else {
                    marker.setOpacity(0.5); // Make inactive stations semi-transparent
                    window.weatherMap.stationLayers.inactive.addLayer(marker);
                }
            } catch (error) {
                console.error("Error displaying station:", station, error);
            }
        });
    }
    
    /**
     * Create a hotspot marker for a station
     */
    createHotspotMarker(station, hasData) {
        // Extract station properties
        let props, coords;
        
        if (station.properties) {
            // GeoJSON structure
            props = station.properties;
            coords = station.geometry.coordinates;
        } else {
            // Direct properties structure
            props = station;
            coords = [station.longitude, station.latitude];
        }
        
        // Get station ID
        const stationId = props.id || props.station_id || '';
        
        // Determine marker color based on parameter value
        let markerColor = '#999999'; // Default gray for no data
        let markerSize = 18;
        
        if (hasData) {
            const value = this.stationData[stationId].averages[this.currentParameter];
            markerColor = this.getColorForValue(value, this.currentParameter);
            
            // Adjust size based on value intensity
            const scale = this.colorScales[this.currentParameter];
            const maxValue = scale[scale.length - 1].value;
            const normalizedValue = Math.min(value, maxValue) / maxValue;
            markerSize = 18 + Math.round(normalizedValue * 12); // Size between 18 and 30
        }
        
        // Create custom icon for the hotspot
        const markerIcon = L.divIcon({
            className: 'custom-marker-icon',
            html: `<div class="marker-content hotspot ${props.is_active || props.status === 'active' ? 'active' : 'inactive'}" 
                      style="background-color: ${markerColor}; width: ${markerSize}px; height: ${markerSize}px;">
                      <div class="marker-label">${props.name || props.station_name || 'Station'}</div>
                   </div>`,
            iconSize: [markerSize, markerSize],
            iconAnchor: [markerSize/2, markerSize/2],
            popupAnchor: [0, -markerSize/2]
        });
        
        // Create marker
        const marker = L.marker([
            Array.isArray(coords) ? coords[1] : props.latitude, 
            Array.isArray(coords) ? coords[0] : props.longitude
        ], {
            title: props.name || props.station_name || 'Unnamed Station',
            alt: props.name || props.station_name || 'Unnamed Station',
            riseOnHover: true,
            icon: markerIcon
        });
        
        // Create popup content with parameter visualization
        const popupContent = this.createHotspotPopup(stationId, props);
        
        // Bind popup to marker
        marker.bindPopup(popupContent, { 
            minWidth: 300,
            maxWidth: 400
        });
        
        return marker;
    }
    
    /**
     * Create popup content with parameter visualization
     */
    createHotspotPopup(stationId, props) {
        const stationName = props.name || props.station_name || 'Unnamed Station';
        
        // Check if we have data for this station
        if (!this.stationData[stationId] || !this.stationData[stationId].readings || this.stationData[stationId].readings.length === 0) {
            return `
                <div class="info-container">
                    <h4>${stationName}</h4>
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        No data available for this station.
                    </div>
                    
                    <div class="button-container mt-3">
                        <a href="${this.apiBaseUrl}/stations/${stationId}/statistics/" 
                           class="btn btn-lg btn-success w-100 mb-2 station-stats-direct-link">
                            <i class="fas fa-chart-bar me-1"></i> View Statistics
                        </a>
                    </div>
                </div>
            `;
        }
        
        // Get station data
        const stationData = this.stationData[stationId];
        const readings = stationData.readings;
        
        // Sort readings by timestamp
        readings.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        
        // Get latest reading
        const latest = readings[0];
        
        // Format timestamp
        const timestamp = new Date(latest.timestamp).toLocaleString();
        
        // Prepare data for chart
        const chartData = {
            labels: [],
            temperature: [],
            precipitation: []
        };
        
        // Get last 7 readings (or all if less than 7)
        const chartReadings = readings.slice(0, 7).reverse();
        
        chartReadings.forEach(reading => {
            // Format date for chart label
            const date = new Date(reading.timestamp);
            chartData.labels.push(date.toLocaleDateString());
            
            // Add temperature and precipitation data
            chartData.temperature.push(reading.temperature !== null && reading.temperature !== undefined ? reading.temperature : null);
            chartData.precipitation.push(reading.precipitation !== null && reading.precipitation !== undefined ? reading.precipitation : null);
        });
        
        // Create popup content
        return `
            <div class="info-container">
                <h4>${stationName} - Parameter Data</h4>
                <p><strong>Latest Reading:</strong> ${timestamp}</p>
                <p><strong>Temperature:</strong> ${latest.temperature !== null && latest.temperature !== undefined ? latest.temperature + ' °C' : 'N/A'}</p>
                <p><strong>Rainfall:</strong> ${latest.precipitation !== null && latest.precipitation !== undefined ? latest.precipitation + ' mm' : 'N/A'}</p>
                
                <div class="chart-container mt-3">
                    <canvas id="station-chart-${stationId}" width="100%" height="200"></canvas>
                </div>
                
                <div class="button-container mt-3">
                    <a href="${this.apiBaseUrl}/stations/${stationId}/statistics/" 
                       class="btn btn-lg btn-success w-100 mb-2 station-stats-direct-link">
                        <i class="fas fa-chart-bar me-1"></i> View Full Statistics
                    </a>
                </div>
            </div>
            
            <script>
                // Create chart when popup is opened
                setTimeout(() => {
                    const ctx = document.getElementById('station-chart-${stationId}');
                    if (ctx) {
                        new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: ${JSON.stringify(chartData.labels)},
                                datasets: [
                                    {
                                        label: 'Temperature (°C)',
                                        data: ${JSON.stringify(chartData.temperature)},
                                        borderColor: 'rgba(255, 99, 132, 1)',
                                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                                        yAxisID: 'y'
                                    },
                                    {
                                        label: 'Rainfall (mm)',
                                        data: ${JSON.stringify(chartData.precipitation)},
                                        borderColor: 'rgba(54, 162, 235, 1)',
                                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                                        yAxisID: 'y1'
                                    }
                                ]
                            },
                            options: {
                                responsive: true,
                                scales: {
                                    y: {
                                        type: 'linear',
                                        display: true,
                                        position: 'left',
                                        title: {
                                            display: true,
                                            text: 'Temperature (°C)'
                                        }
                                    },
                                    y1: {
                                        type: 'linear',
                                        display: true,
                                        position: 'right',
                                        title: {
                                            display: true,
                                            text: 'Rainfall (mm)'
                                        },
                                        grid: {
                                            drawOnChartArea: false
                                        }
                                    }
                                }
                            }
                        });
                    }
                }, 100);
            </script>
        `;
    }
    
    /**
     * Get color for a parameter value
     */
    getColorForValue(value, parameter) {
        const scale = this.colorScales[parameter];
        
        // If value is below the minimum, return the first color
        if (value <= scale[0].value) {
            return scale[0].color;
        }
        
        // If value is above the maximum, return the last color
        if (value >= scale[scale.length - 1].value) {
            return scale[scale.length - 1].color;
        }
        
        // Find the two scale points that the value falls between
        for (let i = 0; i < scale.length - 1; i++) {
            if (value >= scale[i].value && value < scale[i + 1].value) {
                // Calculate the percentage between the two points
                const percent = (value - scale[i].value) / (scale[i + 1].value - scale[i].value);
                
                // Interpolate between the two colors
                return this.interpolateColor(scale[i].color, scale[i + 1].color, percent);
            }
        }
        
        // Fallback
        return scale[0].color;
    }
    
    /**
     * Interpolate between two colors
     */
    interpolateColor(color1, color2, percent) {
        // Convert hex to RGB
        const r1 = parseInt(color1.substring(1, 3), 16);
        const g1 = parseInt(color1.substring(3, 5), 16);
        const b1 = parseInt(color1.substring(5, 7), 16);
        
        const r2 = parseInt(color2.substring(1, 3), 16);
        const g2 = parseInt(color2.substring(3, 5), 16);
        const b2 = parseInt(color2.substring(5, 7), 16);
        
        // Interpolate
        const r = Math.round(r1 + (r2 - r1) * percent);
        const g = Math.round(g1 + (g2 - g1) * percent);
        const b = Math.round(b1 + (b2 - b1) * percent);
        
        // Convert back to hex
        return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    }
    
    /**
     * Show or hide loading indicator
     */
    showLoading(show) {
        // Remove existing loading indicator
        const existingLoader = document.getElementById('hotspot-loader');
        if (existingLoader) {
            existingLoader.remove();
        }
        
        if (show) {
            // Create loading indicator
            const loader = document.createElement('div');
            loader.id = 'hotspot-loader';
            loader.className = 'hotspot-loader';
            loader.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p>Loading hotspot data...</p>
            `;
            
            // Add to the map
            document.querySelector('.map-wrapper').appendChild(loader);
        }
    }
}

// Initialize hotspot feature when the map is ready
document.addEventListener('DOMContentLoaded', function() {
    // Wait for the map to be initialized
    const checkMap = setInterval(() => {
        if (window.weatherMap && window.weatherMap.map) {
            clearInterval(checkMap);
            
            // Create hotspot instance
            window.hotspot = new WeatherHotspot(window.weatherMap.map, '/maps');
            
            // Set stations when they're loaded
            const checkStations = setInterval(() => {
                if (window.weatherMap.stations && window.weatherMap.stations.length > 0) {
                    clearInterval(checkStations);
                    
                    // Set stations
                    window.hotspot.setStations(window.weatherMap.stations);
                    
                    // Load station data
                    window.hotspot.loadStationData();
                }
            }, 500);
        }
    }, 500);
});
