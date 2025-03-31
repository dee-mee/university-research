/**
 * Weather Station Map JavaScript
 * Handles fetching and displaying weather station data on a Leaflet map
 * Focused on Kenya with ability to zoom to specific stations
 */
class WeatherStationMap {
    constructor(mapElementId, apiBaseUrl) {
        this.mapElementId = mapElementId;
        this.apiBaseUrl = apiBaseUrl;
        this.map = null;
        this.stationLayers = {
            active: L.layerGroup(),
            inactive: L.layerGroup()
        };
        this.heatmapLayer = null;
        this.dataView = 'temperature';
        this.stations = [];
        
        // Initialize the map
        this.initMap();
        
        // Load the stations
        this.loadStations();
        
        // Bind event listeners
        this.bindEvents();
    }
    
    /**
     * Bind event listeners for map interactions
     */
    bindEvents() {
        document.addEventListener('click', (e) => {
            if (e.target && e.target.classList.contains('station-data-btn')) {
                const stationId = e.target.getAttribute('data-station-id');
                console.log("Loading data for station:", stationId);
                this.loadStationData(stationId);
            }
        });
    }
    
    /**
     * Initialize the Leaflet map
     */
    initMap() {
        // Create the map centered on Kenya
        this.map = L.map(this.mapElementId, {
            center: [-0.9, 34.75], // Nyanza region's coordinates
            zoom: 6,                   // Zoom level for Kenya
            minZoom: 2,
            maxZoom: 18
        });
        
        // Add the tile layer (OpenStreetMap)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(this.map);
        
        // Add the station layers to the map
        this.stationLayers.active.addTo(this.map);
        this.stationLayers.inactive.addTo(this.map);
        
        // Add info control
        this.addInfoControl();
        
        // Add legend
        this.addLegend();
    }
    
    /**
     * Load weather stations from the API
     */
    loadStations() {
        // Use correct path including API prefix
        const url = `${this.apiBaseUrl}/api/weather-stations/`;
        console.log("Fetching stations from:", url);
        
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("Raw API response:", data);
                
                // Handle different response structures
                if (Array.isArray(data)) {
                    // Direct array of stations
                    this.stations = data.map(station => {
                        // Convert to GeoJSON format if not already
                        if (!station.geometry) {
                            return {
                                type: "Feature",
                                geometry: {
                                    type: "Point",
                                    coordinates: [station.longitude, station.latitude]
                                },
                                properties: { ...station }
                            };
                        }
                        return station;
                    });
                } else if (data.features && Array.isArray(data.features)) {
                    // GeoJSON format
                    this.stations = data.features;
                } else if (data.results && Array.isArray(data.results)) {
                    // DRF paginated format
                    this.stations = data.results.map(station => {
                        // Convert to GeoJSON format if not already
                        if (!station.geometry) {
                            return {
                                type: "Feature",
                                geometry: {
                                    type: "Point",
                                    coordinates: [station.longitude, station.latitude]
                                },
                                properties: { ...station }
                            };
                        }
                        return station;
                    });
                } else {
                    throw new Error("Unexpected data format from API");
                }
                
                if (this.stations.length > 0) {
                    console.log("First station:", this.stations[0]);
                    this.displayStations();
                } else {
                    throw new Error("No stations found in the response");
                }
            })
            .catch(error => {
                console.error("Error loading stations:", error);
                // Try the debug endpoint as fallback with corrected paths
                const debugUrl = `${this.apiBaseUrl}/api/debug/stations/`;
                console.log("Trying debug endpoint:", debugUrl);
                
                fetch(debugUrl)
                    .then(response => {
                        if (!response.ok) {
                            const mapDataUrl = `${this.apiBaseUrl}/api/map-data/`;
                            console.log("Trying map-data endpoint:", mapDataUrl);
                            return fetch(mapDataUrl);
                        }
                        return response;
                    })
                    .then(response => response.json())
                    .then(data => {
                        console.log("Debug endpoint data:", data);
                        if (data && (data.features || data.results || Array.isArray(data))) {
                            if (data.features) {
                                this.stations = data.features;
                            } else if (data.stations && data.stations.features) {
                                // Handle map_data response format
                                this.stations = data.stations.features;
                            } else if (data.stations && data.stations.features) {
                                // Handle map_data response format
                                this.stations = data.stations.features;
                            } else if (data.results) {
                                this.stations = data.results;
                            } else {
                                this.stations = data;
                            }
                            this.displayStations();
                        } else {
                            this.showError(`Failed to load weather stations: ${error.message}`);
                        }
                    })
                    .catch(debugError => {
                        this.showError(`Failed to load weather stations. Error: ${error.message}`);
                    });
            });
    }
    
    /**
     * Display weather stations on the map
     */
    displayStations() {
        // Clear existing layers
        this.stationLayers.active.clearLayers();
        this.stationLayers.inactive.clearLayers();
        
        // Check if stations were loaded
        if (!this.stations || this.stations.length === 0) {
            this.showError("No weather stations found.");
            return;
        }
        
        // Process each station
        this.stations.forEach(station => {
            try {
                // Create marker
                const marker = this.createStationMarker(station);
                
                // Determine if station is active based on available properties
                const isActive = station.properties ? 
                    station.properties.is_active !== undefined ? 
                        station.properties.is_active : 
                        (station.properties.status === 'active') : 
                    (station.is_active !== undefined ? 
                        station.is_active : 
                        (station.status === 'active'));
                
                // Add marker to appropriate layer group
                if (isActive) {
                    this.stationLayers.active.addLayer(marker);
                } else {
                    marker.setOpacity(0.5); // Make inactive stations semi-transparent
                    this.stationLayers.inactive.addLayer(marker);
                }
            } catch (error) {
                console.error("Error displaying station:", station, error);
            }
        });
        
        // Populate station dropdown
        this.populateStationDropdown();
        
        // Set map view to Kenya by default
        this.map.setView([0.0236, 37.9062], 6);
    }
    
    /**
     * Create a marker for a weather station
     */
    createStationMarker(station) {
        // Extract station properties, handling different data structures
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
        
        // Get station ID (could be in different formats)
        const stationId = props.id || props.station_id || '';
        
        // Create marker
        const marker = L.marker([
            Array.isArray(coords) ? coords[1] : props.latitude, 
            Array.isArray(coords) ? coords[0] : props.longitude
        ], {
            title: props.name || props.station_name || 'Unnamed Station',
            alt: props.name || props.station_name || 'Unnamed Station',
            riseOnHover: true
        });
        
        // Create popup content
        const popupContent = `
            <div class="info-container">
                <h4>${props.name || props.station_name || 'Unnamed Station'}</h4>
                <p>${props.description || 'No description available.'}</p>
                <p><strong>Status:</strong> ${props.is_active || props.status === 'active' ? 'Active' : 'Inactive'}</p>
                <p><strong>Altitude:</strong> ${props.altitude ? props.altitude + ' m' : 'N/A'}</p>
                <p><strong>Installed:</strong> ${props.date_installed || props.installation_date || 'N/A'}</p>
                <button class="btn btn-sm btn-primary station-data-btn" data-station-id="${stationId}">View Data</button>
            </div>
        `;
        
        // Bind popup to marker
        marker.bindPopup(popupContent);
        
        // Add click event to load station data
        marker.on('click', () => {
            this.loadStationData(stationId);
        });
        
        return marker;
    }
    
    /**
     * Load data for a specific station
     */
    loadStationData(stationId) {
        if (!stationId) {
            this.showError("Invalid station ID");
            return;
        }
        
        // Try to access station data using the correct API endpoint path
        const url = `${this.apiBaseUrl}/api/stations/${stationId}/data/`;
        console.log("Fetching station data from:", url);
        
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    // First fallback - try using DRF viewset endpoint directly
                    const fallbackUrl = `${this.apiBaseUrl}/api/climate-data/?station=${stationId}&days=7`;
                    console.log("Trying fallback URL:", fallbackUrl);
                    return fetch(fallbackUrl);
                }
                return response;
            })
            .then(response => {
                if (!response.ok) {
                    // Second fallback - try accessing the station directly via map-data
                    const mapDataUrl = `${this.apiBaseUrl}/api/map-data/?station=${stationId}`;
                    console.log("Trying map-data endpoint:", mapDataUrl);
                    return fetch(mapDataUrl);
                }
                return response;
            })
            .then(response => response.json())
            .then(data => {
                // Get station info for popup location
                const station = this.findStationById(stationId);
                let popupLatLng;
                
                if (station) {
                    if (station.geometry && station.geometry.coordinates) {
                        popupLatLng = [station.geometry.coordinates[1], station.geometry.coordinates[0]];
                    } else {
                        popupLatLng = [station.latitude || 0, station.longitude || 0];
                    }
                } else {
                    popupLatLng = this.map.getCenter();
                }
                
                // Update the popup with the latest data
                const popup = L.popup()
                    .setLatLng(popupLatLng)
                    .setContent(this.createDataPopupContent(data, stationId))
                    .openOn(this.map);
            })
            .catch(error => {
                console.error("Error loading station data:", error);
                this.showError(`Failed to load data for station: ${error.message}`);
            });
    }
    
    /**
     * Find station by ID in our local data
     */
    findStationById(stationId) {
        for (const station of this.stations) {
            if (station.properties) {
                if (station.properties.id == stationId || station.properties.station_id == stationId) {
                    return station;
                }
            } else if (station.id == stationId || station.station_id == stationId) {
                return station;
            }
        }
        return null;
    }
    
    /**
     * Create popup content for station data
     */
    createDataPopupContent(data, stationId) {
        // Handle different API response formats
        let results;
        if (data.results && data.results.length > 0) {
            results = data.results;
        } else if (Array.isArray(data) && data.length > 0) {
            results = data;
        } else {
            return `<div class="info-container"><p>No recent data available for this station.</p></div>`;
        }
        
        const latest = results[0];
        const station = this.findStationById(stationId);
        const stationName = station ? 
            (station.properties ? station.properties.name : station.name) || 'Unknown Station' :
            latest.station_name || 'Unknown Station';
        
        return `
            <div class="info-container">
                <h4>${stationName} - Latest Data</h4>
                <p><strong>Time:</strong> ${new Date(latest.timestamp || latest.date_time || latest.recorded_time).toLocaleString()}</p>
                <p><strong>Temperature:</strong> ${latest.temperature !== null && latest.temperature !== undefined ? latest.temperature + ' °C' : 'N/A'}</p>
                <p><strong>Humidity:</strong> ${latest.humidity !== null && latest.humidity !== undefined ? latest.humidity + '%' : 'N/A'}</p>
                <p><strong>Precipitation:</strong> ${latest.precipitation !== null && latest.precipitation !== undefined ? latest.precipitation + ' mm' : 'N/A'}</p>
                <p><strong>Wind:</strong> ${latest.wind_speed !== null && latest.wind_speed !== undefined ? latest.wind_speed + ' m/s' : 'N/A'} 
                   ${latest.wind_direction !== null && latest.wind_direction !== undefined ? 'at ' + latest.wind_direction + '°' : ''}</p>
                <p><strong>Air Quality:</strong> ${latest.air_quality_index !== null && latest.air_quality_index !== undefined ? latest.air_quality_index : 'N/A'}</p>
                <p><strong>Data Quality:</strong> ${latest.data_quality || 'Good'}</p>
                <button class="btn btn-sm btn-secondary" onclick="window.location.href='/maps/stations/${stationId}/statistics/'">View Statistics</button>
                <button class="btn btn-sm btn-secondary" onclick="window.location.href='/maps/stations/${stationId}/statistics/'">View Statistics</button>
            </div>
        `;
    }
    
    /**
     * Add info control to the map
     */
    addInfoControl() {
        const info = L.control();
        
        info.onAdd = () => {
            this.infoDiv = L.DomUtil.create('div', 'info-container');
            this.updateInfo();
            return this.infoDiv;
        };
        
        info.addTo(this.map);
    }
    
    /**
     * Update info control content
     */
    updateInfo() {
        if (!this.infoDiv) return;
        
        const activeCount = this.stationLayers.active.getLayers().length;
        const inactiveCount = this.stationLayers.inactive.getLayers().length;
        
        this.infoDiv.innerHTML = `
            <h4>Weather Station Network</h4>
            <p><strong>Active Stations:</strong> ${activeCount}</p>
            <p><strong>Inactive Stations:</strong> ${inactiveCount}</p>
            <p><strong>Total Stations:</strong> ${activeCount + inactiveCount}</p>
            <p><strong>Data View:</strong> ${this.dataView}</p>
        `;
    }
    
   /**
     * Add legend to the map
     */
    addLegend() {
        const legend = L.control({position: 'bottomright'});
        
        legend.onAdd = () => {
            const div = L.DomUtil.create('div', 'info-container legend');
            div.innerHTML = `
                <h4>Legend</h4>
                <div><i style="background: #4285F4"></i> Active Station</div>
                <div><i style="background: #4285F4; opacity: 0.5"></i> Inactive Station</div>
            `;
            return div;
        };
        
        legend.addTo(this.map);
    }
    
    /**
     * Toggle active stations visibility
     */
    toggleActiveStations(visible) {
        if (visible) {
            if (!this.map.hasLayer(this.stationLayers.active)) {
                this.map.addLayer(this.stationLayers.active);
            }
        } else {
            if (this.map.hasLayer(this.stationLayers.active)) {
                this.map.removeLayer(this.stationLayers.active);
            }
        }
        this.updateInfo();
    }
    
    /**
     * Toggle inactive stations visibility
     */
    toggleInactiveStations(visible) {
        if (visible) {
            if (!this.map.hasLayer(this.stationLayers.inactive)) {
                this.map.addLayer(this.stationLayers.inactive);
            }
        } else {
            if (this.map.hasLayer(this.stationLayers.inactive)) {
                this.map.removeLayer(this.stationLayers.inactive);
            }
        }
        this.updateInfo();
    }
    
    /**
     * Toggle heatmap visibility
     */
    toggleHeatmap(visible) {
        if (visible) {
            this.loadHeatmapData();
        } else if (this.heatmapLayer) {
            this.map.removeLayer(this.heatmapLayer);
            this.heatmapLayer = null;
        }
    }
    
    /**
     * Load data for heatmap
     */
    loadHeatmapData() {
        // Use correct API endpoint path for climate data
        const url = `${this.apiBaseUrl}/api/climate-data/recent/?hours=24`;
        console.log("Fetching heatmap data from:", url);
        
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    // Try fallback path
                    const fallbackUrl = `${this.apiBaseUrl}/api/climate-data/?hours=24`;
                    console.log("Trying fallback URL:", fallbackUrl);
                    return fetch(fallbackUrl);
                }
                return response;
            })
            .then(response => {
                if (!response.ok) {
                    // Try the map-data endpoint as another fallback
                    const mapDataUrl = `${this.apiBaseUrl}/api/map-data/`;
                    console.log("Trying map-data endpoint:", mapDataUrl);
                    return fetch(mapDataUrl);
                }
                return response;
                return response;
            })
            .then(response => response.json())
            .then(response => response.json())
            .then(data => {
                // Handle different response formats
                let results;
                // Check for map-data response format
                if (data.recent_data && Array.isArray(data.recent_data)) {
                    results = data.recent_data;
                } else if (data.results && Array.isArray(data.results)) {
                // Check for map-data response format
                if (data.recent_data && Array.isArray(data.recent_data)) {
                    results = data.recent_data;
                } else if (data.results && Array.isArray(data.results)) {
                    results = data.results;
                } else if (Array.isArray(data)) {
                    results = data;
                } else {
                    results = []; // Empty array if no valid data
                }
                
                this.createHeatmap(results);
            })
            .catch(error => {
                console.error("Error loading heatmap data:", error);
                this.showError(`Failed to load heatmap data: ${error.message}`);
                this.showError(`Failed to load heatmap data: ${error.message}`);
            });
    }
    
    /**
     * Create heatmap from data
     */
    createHeatmap(data) {
        // Remove existing heatmap if any
        if (this.heatmapLayer) {
            this.map.removeLayer(this.heatmapLayer);
        }
        
        // Prepare points for heatmap
        const heatPoints = [];
        
        data.forEach(item => {
            // Try to extract location from various possible formats
            let lat = null, lng = null;
            
            if (item.station_location) {
                if (typeof item.station_location === 'object' && item.station_location.coordinates) {
                    // GeoJSON Point format
                    lng = item.station_location.coordinates[0];
                    lat = item.station_location.coordinates[1];
                } else if (typeof item.station_location === 'string') {
                    // Parse string format "POINT(lng lat)" or similar
                    try {
                        const match = item.station_location.match(/POINT\s*\(\s*([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)\s*\)/i);
                        if (match) {
                            lng = parseFloat(match[1]);
                            lat = parseFloat(match[2]);
                        }
                    } catch (e) {
                        console.error("Error parsing station_location string:", e);
                    }
                }
            } else if (item.latitude !== undefined && item.longitude !== undefined) {
                // Direct lat/lng properties
                lat = parseFloat(item.latitude);
                lng = parseFloat(item.longitude);
            } else if (item.station) {
                // Try to find station in our loaded stations
                const station = this.findStationById(item.station);
                if (station) {
                    if (station.geometry && station.geometry.coordinates) {
                        lng = station.geometry.coordinates[0];
                        lat = station.geometry.coordinates[1];
                    } else {
                        lat = station.latitude;
                        lng = station.longitude;
                    }
                }
            }
            
            // Only add valid points with location
            if (lat !== null && lng !== null && !isNaN(lat) && !isNaN(lng)) {
                // Get the value for the current data view
                let intensity = 0;
                switch (this.dataView) {
                    case 'temperature':
                        intensity = item.temperature !== null && item.temperature !== undefined ? 
                            Math.abs(parseFloat(item.temperature)) : 0;
                        break;
                    case 'precipitation':
                        intensity = item.precipitation !== null && item.precipitation !== undefined ? 
                            parseFloat(item.precipitation) * 5 : 0;
                        break;
                    case 'wind':
                        intensity = item.wind_speed !== null && item.wind_speed !== undefined ? 
                            parseFloat(item.wind_speed) * 3 : 0;
                        break;
                    case 'humidity':
                        intensity = item.humidity !== null && item.humidity !== undefined ? 
                            parseFloat(item.humidity) / 5 : 0;
                        break;
                    default:
                        intensity = 0;
                }
                
                // Only add points with valid intensity
                if (!isNaN(intensity)) {
                    heatPoints.push([
                        lat, // latitude
                        lng, // longitude
                        intensity // intensity value
                    ]);
                }
            }
        });
        
        // Create heatmap layer if we have points
        if (heatPoints.length > 0) {
            // Check if heatmap plugin is available
            if (typeof L.heatLayer === 'function') {
                this.heatmapLayer = L.heatLayer(heatPoints, {
                    radius: 25,
                    blur: 15,
                    maxZoom: 10,
                    gradient: {0.4: 'blue', 0.6: 'cyan', 0.7: 'lime', 0.8: 'yellow', 1: 'red'}
                }).addTo(this.map);
            } else {
                console.error("Leaflet.heat plugin is not loaded. Cannot create heatmap.");
                this.showError("Heatmap plugin not available. Please include Leaflet.heat in your project.");
            }
        } else {
            this.showError("No valid data available for heatmap.");
        }
    }
    
    /**
     * Change data view for visualization
     */
    changeDataView(dataView) {
        this.dataView = dataView;
        this.updateInfo();
        
        // If heatmap is visible, refresh it with new data type
        if (this.heatmapLayer && this.map.hasLayer(this.heatmapLayer)) {
            this.loadHeatmapData();
        }
    }
    
    /**
     * Refresh data from the API
     */
    refreshData() {
        // Reload stations
        this.loadStations();
        
        // Reload heatmap if visible
        if (this.heatmapLayer && this.map.hasLayer(this.heatmapLayer)) {
            this.loadHeatmapData();
        }
        
        this.updateInfo();
    }
    
    /**
     * Show error message
     */
    showError(message) {
        console.error(message);
        
        // Create error alert
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger';
        alertDiv.role = 'alert';
        alertDiv.style.position = 'fixed';
        alertDiv.style.top = '10px';
        alertDiv.style.left = '50%';
        alertDiv.style.transform = 'translateX(-50%)';
        alertDiv.style.zIndex = '1000';
        alertDiv.textContent = message;
        
        // Add close button
        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'btn-close';
        closeButton.setAttribute('aria-label', 'Close');
        closeButton.addEventListener('click', () => {
            alertDiv.remove();
        });
        
        alertDiv.appendChild(closeButton);
        document.body.appendChild(alertDiv);
        
        // Remove alert after 5 seconds
        setTimeout(() => {
            if (document.body.contains(alertDiv)) {
                alertDiv.remove();
            }
        }, 5000);
    }
    
    /**
     * Populate the station dropdown with available stations
     */
    populateStationDropdown() {
        const stationSelect = document.getElementById('stationSelect');
        if (!stationSelect) return;
        
        // Clear existing options except the first one
        while (stationSelect.options.length > 1) {
            stationSelect.remove(1);
        }
        
        // Add stations to dropdown
        this.stations.forEach(station => {
            const option = document.createElement('option');
            // Handle different data structures
            if (station.properties) {
                option.value = station.properties.id || station.properties.station_id || '';
                option.textContent = station.properties.name || station.properties.station_name || 'Unnamed Station';
                // Add an indicator for inactive stations
                if (!station.properties.is_active && station.properties.is_active !== undefined) {
                    option.textContent += ' (Inactive)';
                } else if (station.properties.status === 'inactive') {
                    option.textContent += ' (Inactive)';
                }
            } else {
                option.value = station.id || station.station_id || '';
                option.textContent = station.name || station.station_name || 'Unnamed Station';
                // Add an indicator for inactive stations
                if (!station.is_active && station.is_active !== undefined) {
                    option.textContent += ' (Inactive)';
                } else if (station.status === 'inactive') {
                    option.textContent += ' (Inactive)';
                }
            }
            stationSelect.appendChild(option);
        });
    }

    /**
     * Zoom to a specific station when selected from dropdown
     */
    zoomToStation(stationId) {
        if (!stationId) {
            // If "All Stations" is selected, zoom to include all stations
            const bounds = L.featureGroup([
                this.stationLayers.active, 
                this.stationLayers.inactive
            ]).getBounds();
            
            if (bounds.isValid()) {
                this.map.fitBounds(bounds);
            } else {
                // Default to Kenya view if no stations
                this.map.setView([0.0236, 37.9062], 6);
            }
            return;
        }
        
        // Find the selected station
        const station = this.findStationById(stationId);
        
        if (station) {
            let lat, lng;
            
            if (station.geometry && station.geometry.coordinates) {
                lng = station.geometry.coordinates[0];
                lat = station.geometry.coordinates[1];
            } else {
                lat = station.latitude;
                lng = station.longitude;
            }
            
            // Zoom to the station
            this.map.setView([lat, lng], 14);
            
            // Find and open the station marker popup
            const searchByTitle = station.properties ? 
                station.properties.name || station.properties.station_name : 
                station.name || station.station_name;
                
            this.stationLayers.active.eachLayer(layer => {
                if (layer.options.title === searchByTitle) {
                    layer.openPopup();
                }
            });
            
            this.stationLayers.inactive.eachLayer(layer => {
                if (layer.options.title === searchByTitle) {
                    layer.openPopup();
                }
            });
        }
    }
}