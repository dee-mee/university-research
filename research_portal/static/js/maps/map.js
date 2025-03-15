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
            center: [0.0236, 37.9062], // Kenya's coordinates
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
        fetch(`${this.apiBaseUrl}/weather-stations/`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("Raw API response:", data);
                
                // Convert data to string and back to make sure we're seeing the exact structure
                const dataStr = JSON.stringify(data);
                console.log("API response as string:", dataStr);
                
                // Very simple approach - just use the data directly
                this.stations = data.features || [];
                
                if (this.stations.length > 0) {
                    console.log("First station:", this.stations[0]);
                    this.displayStations();
                } else {
                    throw new Error("No stations found in the response");
                }
            })
            .catch(error => {
                console.error("Error loading stations:", error);
                this.showError(`Failed to load weather stations. Error: ${error.message}`);
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
            // Create marker
            const marker = this.createStationMarker(station);
            
            // Add marker to appropriate layer group
            if (station.properties.is_active) {
                this.stationLayers.active.addLayer(marker);
            } else {
                marker.setOpacity(0.5); // Make inactive stations semi-transparent
                this.stationLayers.inactive.addLayer(marker);
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
        // Extract station properties
        const props = station.properties;
        const coords = station.geometry.coordinates;
        
        // Create marker
        const marker = L.marker([coords[1], coords[0]], {
            title: props.name,
            alt: props.name,
            riseOnHover: true
        });
        
        // Create popup content
        const popupContent = `
            <div class="info-container">
                <h4>${props.name}</h4>
                <p>${props.description || 'No description available.'}</p>
                <p><strong>Status:</strong> ${props.is_active ? 'Active' : 'Inactive'}</p>
                <p><strong>Altitude:</strong> ${props.altitude ? props.altitude + ' m' : 'N/A'}</p>
                <p><strong>Installed:</strong> ${props.date_installed || 'N/A'}</p>
                <button class="btn btn-sm btn-primary station-data-btn" data-station-id="${props.id}">View Data</button>
            </div>
        `;
        
        // Bind popup to marker
        marker.bindPopup(popupContent);
        
        // Add click event to load station data
        marker.on('click', () => {
            this.loadStationData(props.id);
        });
        
        return marker;
    }
    
    /**
     * Load data for a specific station
     */
    loadStationData(stationId) {
        fetch(`${this.apiBaseUrl}/weather-stations/${stationId}/data/?days=7`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Update the popup with the latest data
                const popup = L.popup()
                    .setLatLng(this.map.getCenter())
                    .setContent(this.createDataPopupContent(data))
                    .openOn(this.map);
            })
            .catch(error => {
                console.error("Error loading station data:", error);
            });
    }
    
    /**
     * Create popup content for station data
     */
    createDataPopupContent(data) {
        if (!data.results || data.results.length === 0) {
            return `<div class="info-container"><p>No recent data available for this station.</p></div>`;
        }
        
        const latest = data.results[0];
        
        return `
            <div class="info-container">
                <h4>${latest.station_name} - Latest Data</h4>
                <p><strong>Time:</strong> ${new Date(latest.timestamp).toLocaleString()}</p>
                <p><strong>Temperature:</strong> ${latest.temperature !== null ? latest.temperature + ' °C' : 'N/A'}</p>
                <p><strong>Humidity:</strong> ${latest.humidity !== null ? latest.humidity + '%' : 'N/A'}</p>
                <p><strong>Precipitation:</strong> ${latest.precipitation !== null ? latest.precipitation + ' mm' : 'N/A'}</p>
                <p><strong>Wind:</strong> ${latest.wind_speed !== null ? latest.wind_speed + ' m/s' : 'N/A'} 
                   ${latest.wind_direction !== null ? 'at ' + latest.wind_direction + '°' : ''}</p>
                <p><strong>Air Quality:</strong> ${latest.air_quality_index !== null ? latest.air_quality_index : 'N/A'}</p>
                <p><strong>Data Quality:</strong> ${latest.data_quality}</p>
                <button class="btn btn-sm btn-secondary" onclick="window.location.href='${this.apiBaseUrl}/weather-stations/${latest.station}/statistics/'">View Statistics</button>
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
        fetch(`${this.apiBaseUrl}/climate-data/recent/?hours=24`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                this.createHeatmap(data.results);
            })
            .catch(error => {
                console.error("Error loading heatmap data:", error);
                this.showError("Failed to load heatmap data.");
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
            const location = item.station_location;
            if (location && location.coordinates) {
                // Get the value for the current data view
                let intensity = 0;
                switch (this.dataView) {
                    case 'temperature':
                        intensity = item.temperature !== null ? Math.abs(item.temperature) : 0;
                        break;
                    case 'precipitation':
                        intensity = item.precipitation !== null ? item.precipitation * 5 : 0;
                        break;
                    case 'wind':
                        intensity = item.wind_speed !== null ? item.wind_speed * 3 : 0;
                        break;
                    case 'humidity':
                        intensity = item.humidity !== null ? item.humidity / 5 : 0;
                        break;
                    default:
                        intensity = 0;
                }
                
                heatPoints.push([
                    location.coordinates[1], // latitude
                    location.coordinates[0], // longitude
                    intensity // intensity value
                ]);
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
            this.showError("No data available for heatmap.");
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
           alertDiv.remove();
       }, 5000);
   }
   
   /**
    * Populate the station dropdown with available stations
    */
   populateStationDropdown() {
       const stationSelect = document.getElementById('stationSelect');
       
       // Clear existing options except the first one
       while (stationSelect.options.length > 1) {
           stationSelect.remove(1);
       }
       
       // Add stations to dropdown
       this.stations.forEach(station => {
           const option = document.createElement('option');
           option.value = station.properties.id;
           option.textContent = station.properties.name;
           // Add an indicator for inactive stations
           if (!station.properties.is_active) {
               option.textContent += ' (Inactive)';
           }
           stationSelect.appendChild(option);
       });
       
       // Add event listener for station selection
       stationSelect.addEventListener('change', (e) => {
           this.zoomToStation(e.target.value);
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
       const station = this.stations.find(s => s.properties.id == stationId);
       
       if (station) {
           const coords = station.geometry.coordinates;
           // Zoom to the station
           this.map.setView([coords[1], coords[0]], 14);
           
           // Find and open the station marker popup
           this.stationLayers.active.eachLayer(layer => {
               if (layer.options.title === station.properties.name) {
                   layer.openPopup();
               }
           });
           
           this.stationLayers.inactive.eachLayer(layer => {
               if (layer.options.title === station.properties.name) {
                   layer.openPopup();
               }
           });
       }
   }
}