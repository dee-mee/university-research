/**
 * Weather Station Map JavaScript
 * Handles fetching and displaying weather station data on a Leaflet map
 * Works in standalone mode or as an overlay on top of Windy map
 */
class WeatherStationMap {
    constructor(mapElementId, apiBaseUrl, options = {}) {
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
        this.options = Object.assign({
            useWindyOverlay: false,
            windyMapId: 'windy-map',
            mapContainerId: 'map-container',
            initialView: [-0.9, 34.75],
            initialZoom: 6
        }, options);
        
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
            // Handle data button clicks
            if (e.target && (e.target.classList.contains('station-data-btn') || 
                              e.target.closest('.station-data-btn'))) {
                const btn = e.target.classList.contains('station-data-btn') ? 
                            e.target : e.target.closest('.station-data-btn');
                const stationId = btn.getAttribute('data-station-id');
                console.log("Loading data for station:", stationId);
                this.loadStationData(stationId);
            }
            
            // This is no longer needed as we're using direct links now
            // But kept for backward compatibility
            if (e.target && (e.target.classList.contains('station-stats-btn') || 
                              e.target.closest('.station-stats-btn'))) {
                const btn = e.target.classList.contains('station-stats-btn') ? 
                            e.target : e.target.closest('.station-stats-btn');
                const stationId = btn.getAttribute('data-station-id');
                console.log("Navigating to statistics for station:", stationId);
                window.location.href = `${this.apiBaseUrl}/maps/stations/${stationId}/statistics/`;
            }
        });

        // Add listener for the custom centerMap function
        window.centerMap = (lat, lon, locationName) => {
            this.centerOnCoordinates(lat, lon, locationName);
        };

        // Listener for station selector dropdown
        const stationSelect = document.getElementById('stationSelect');
        if (stationSelect) {
            stationSelect.addEventListener('change', (e) => {
                const stationId = e.target.value;
                if (stationId) {
                    this.zoomToStation(stationId);
                } else {
                    // If "All Stations" is selected, zoom to show all stations
                    this.zoomToAllStations();
                }
            });
        }
    }
    
    /**
     * Initialize the Leaflet map
     */
    initMap() {
        // Check if we're in Windy overlay mode
        if (this.options.useWindyOverlay) {
            this.initOverlayMap();
        } else {
            this.initStandaloneMap();
        }
        
        // Add the station layers to the map
        this.stationLayers.active.addTo(this.map);
        this.stationLayers.inactive.addTo(this.map);
        
        // Add info control
        this.addInfoControl();
        
        // Add legend
        this.addLegend();
    }

    /**
     * Initialize map as a standalone Leaflet map
     */
    initStandaloneMap() {
        // Create the map centered on Kenya
        this.map = L.map(this.mapElementId, {
            center: this.options.initialView,
            zoom: this.options.initialZoom,
            minZoom: 2,
            maxZoom: 18
        });
        
        // Add the tile layer (OpenStreetMap)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(this.map);
    }

    /**
     * Initialize map as an overlay on top of Windy iframe
     */
    initOverlayMap() {
        // Get the Windy iframe container
        const windyContainer = document.getElementById(this.options.windyMapId);
        if (!windyContainer) {
            console.error("Windy map container not found:", this.options.windyMapId);
            return;
        }

        // Create a container for the overlay map if it doesn't exist
        let mapContainer = document.getElementById(this.options.mapContainerId);
        if (!mapContainer) {
            mapContainer = document.createElement('div');
            mapContainer.id = this.options.mapContainerId;
            mapContainer.style.position = 'absolute';
            mapContainer.style.top = '0';
            mapContainer.style.left = '0';
            mapContainer.style.width = '100%';
            mapContainer.style.height = '100%';
            mapContainer.style.pointerEvents = 'auto';
            mapContainer.style.zIndex = '1000'; // Keep at 1000, below navbar's 1500
            
            // Insert the overlay container right after the Windy iframe
            windyContainer.parentNode.insertBefore(mapContainer, windyContainer.nextSibling);
        }

        // Create the overlay map with transparent background - NO TILES
        this.map = L.map(this.options.mapContainerId, {
            center: this.options.initialView,
            zoom: this.options.initialZoom,
            zoomControl: true,
            attributionControl: false,
            layers: [], // No base layers
            scrollWheelZoom: true
        });

        // Make the map fully transparent
        // These are the important changes to ensure transparency
        setTimeout(() => {
            const mapPane = document.querySelector(`#${this.options.mapContainerId} .leaflet-map-pane`);
            if (mapPane) mapPane.style.background = 'transparent';
            
            const tilePane = document.querySelector(`#${this.options.mapContainerId} .leaflet-tile-pane`);
            if (tilePane) tilePane.style.opacity = '0';
            
            const overlayPane = document.querySelector(`#${this.options.mapContainerId} .leaflet-overlay-pane`);
            if (overlayPane) overlayPane.style.background = 'transparent';
            
            document.querySelector(`#${this.options.mapContainerId} .leaflet-control-container`).style.zIndex = '2000';
        }, 100);

        // Sync view with Windy iframe (initial position)
        this.syncWithWindyMap();
        
        // Add opacity control for markers
        this.addOpacityControl();
    }

    /**
     * Sync the overlay map with Windy map iframe
     */
    syncWithWindyMap() {
        try {
            // Get the current Windy iframe src
            const windyIframe = document.getElementById(this.options.windyMapId);
            if (!windyIframe) return;

            const src = windyIframe.src;
            
            // Extract coordinates and zoom from the iframe URL
            const latMatch = src.match(/lat=([^&]*)/);
            const lonMatch = src.match(/lon=([^&]*)/);
            const zoomMatch = src.match(/zoom=([^&]*)/);
            
            if (latMatch && lonMatch) {
                const lat = parseFloat(latMatch[1]);
                const lon = parseFloat(lonMatch[1]);
                const zoom = zoomMatch ? parseInt(zoomMatch[1]) : this.options.initialZoom;
                
                // Set the view of our overlay map to match Windy
                if (!isNaN(lat) && !isNaN(lon)) {
                    this.map.setView([lat, lon], zoom);
                }
            }
        } catch (error) {
            console.error('Error syncing with Windy map:', error);
        }
    }

    /**
     * Center the map on specific coordinates and add a marker
     * This function can be called from outside (window.centerMap)
     */
    centerOnCoordinates(lat, lon, locationName) {
        // Update map view
        this.map.setView([lat, lon], 12);
        
        // If we're in overlay mode, also update the Windy iframe
        if (this.options.useWindyOverlay) {
            this.updateWindyIframe(lat, lon, locationName);
        }
        
        // Optional: Add a temporary marker
        const tempMarker = L.marker([lat, lon], {
            title: locationName || 'Selected Location',
            riseOnHover: true
        }).addTo(this.map);
        
        tempMarker.bindPopup(`<b>${locationName || 'Selected Location'}</b><br>Coordinates: ${lat}, ${lon}`).openPopup();
        
        // Remove the marker after some time
        setTimeout(() => {
            this.map.removeLayer(tempMarker);
        }, 5000);
    }

    /**
     * Update the Windy iframe src to center on specific coordinates
     */
    updateWindyIframe(lat, lon, locationName) {
        const iframe = document.getElementById(this.options.windyMapId);
        if (!iframe) return;
        
        const currentSrc = iframe.src;
        const newSrc = currentSrc.replace(/lat=([^&]*)/, `lat=${lat}`)
                               .replace(/lon=([^&]*)/, `lon=${lon}`)
                               .replace(/detailLat=([^&]*)/, `detailLat=${lat}`)
                               .replace(/detailLon=([^&]*)/, `detailLon=${lon}`);
        
        iframe.src = newSrc;
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
        
        // If we're in overlay mode, update station visibility
        if (this.options.useWindyOverlay) {
            this.updateStationVisibility();
        }
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
        console.log("Creating marker for station:", stationId, props.name || props.station_name);
        
        // Create custom icon for better visibility on Windy map
        // Make markers smaller and more transparent by default
        const markerIcon = L.divIcon({
            className: 'custom-marker-icon',
            html: `<div class="marker-content ${props.is_active || props.status === 'active' ? 'active' : 'inactive'}">
                     <i class="fas fa-map-marker-alt"></i>
                     <div class="marker-label">${props.name || props.station_name || 'Station'}</div>
                   </div>`,
            iconSize: [18, 28], // Smaller icon
            iconAnchor: [9, 28],
            popupAnchor: [0, -28]
        });
        
        // Create marker with transparency
        const marker = L.marker([
            Array.isArray(coords) ? coords[1] : props.latitude, 
            Array.isArray(coords) ? coords[0] : props.longitude
        ], {
            title: props.name || props.station_name || 'Unnamed Station',
            alt: props.name || props.station_name || 'Unnamed Station',
            riseOnHover: true,
            icon: markerIcon,
            opacity: 0.7 // Default transparency for all markers
        });
        
        // Create popup content with VERY prominent buttons - FIX URL PATH
        const popupContent = `
            <div class="info-container">
                <h4>${props.name || props.station_name || 'Unnamed Station'}</h4>
                <p>${props.description || 'No description available.'}</p>
                <p><strong>Status:</strong> ${props.is_active || props.status === 'active' ? 'Active' : 'Inactive'}</p>
                <p><strong>Altitude:</strong> ${props.altitude ? props.altitude + ' m' : 'N/A'}</p>
                <p><strong>Installed:</strong> ${props.date_installed || props.installation_date || 'N/A'}</p>
                
                <div class="button-container mt-3">
                    <a href="${this.apiBaseUrl}/stations/${stationId}/statistics/" 
                       class="btn btn-lg btn-success w-100 mb-2 station-stats-direct-link">
                        <i class="fas fa-chart-bar me-1"></i> View Statistics
                    </a>
                    <button class="btn btn-sm btn-primary station-data-btn w-100" data-station-id="${stationId}">
                        <i class="fas fa-chart-line me-1"></i> Show Latest Data
                    </button>
                </div>
            </div>
        `;
        
        // Bind popup to marker
        marker.bindPopup(popupContent, { 
            minWidth: 200,
            maxWidth: 300
        });
        
        // Add click event to open popup without automatically loading data
        marker.on('click', () => {
            console.log("Marker clicked for station:", stationId);
            // Just let the popup open naturally - don't auto-load data
        });
        
        return marker;
    }

    /**
     * Update the visibility of stations based on zoom level
     * For Windy overlay mode - hide station labels at lower zoom levels
     */
    updateStationVisibility() {
        const currentZoom = this.map.getZoom();
        const showLabels = currentZoom >= 9;
        
        // Update labels visibility
        document.querySelectorAll('.marker-label').forEach(label => {
            label.style.display = showLabels ? 'block' : 'none';
        });
        
        // Update marker size based on zoom
        document.querySelectorAll('.marker-content').forEach(marker => {
            marker.style.fontSize = currentZoom <= 6 ? '12px' : (currentZoom <= 8 ? '14px' : '16px');
        });
    }
    
    /**
     * Load data for a specific station
     */
    loadStationData(stationId) {
        if (!stationId) {
            this.showError("Invalid station ID");
            return;
        }
        
        // Get station info for popup location before making API call
        const station = this.findStationById(stationId);
        let popupLatLng;
        let stationName = "Unknown Station";
        
        if (station) {
            if (station.properties) {
                stationName = station.properties.name || station.properties.station_name || "Unknown Station";
                if (station.geometry && station.geometry.coordinates) {
                    popupLatLng = [station.geometry.coordinates[1], station.geometry.coordinates[0]];
                } else {
                    popupLatLng = [station.properties.latitude || 0, station.properties.longitude || 0];
                }
            } else {
                stationName = station.name || station.station_name || "Unknown Station";
                popupLatLng = [station.latitude || 0, station.longitude || 0];
            }
        } else {
            popupLatLng = this.map.getCenter();
        }
        
        // Show loading message in popup
        const loadingPopup = L.popup()
            .setLatLng(popupLatLng)
            .setContent(`
                <div class="info-container">
                    <h4>${stationName} - Loading Data</h4>
                    <div class="text-center my-3">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                    <p class="text-center">Loading latest readings...</p>
                </div>
            `)
            .openOn(this.map);
        
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
                console.log("Station data response:", data);
                
                // Check if data is empty (either empty array or empty object)
                const isEmpty = 
                    (Array.isArray(data) && data.length === 0) || 
                    (data && typeof data === 'object' && Object.keys(data).length === 0) ||
                    (!data);
                    
                if (isEmpty) {
                    // Create content for when there's no data - FIX URL PATH
                    const noDataContent = `
                        <div class="info-container">
                            <h4>${stationName}</h4>
                            <div class="alert alert-warning">
                                <i class="fas fa-exclamation-triangle me-2"></i>
                                No recent data available for this station.
                            </div>
                            
                            <div class="button-container mt-3">
                                <a href="${this.apiBaseUrl}/stations/${stationId}/statistics/" 
                                   class="btn btn-lg btn-success w-100 mb-2 station-stats-direct-link">
                                    <i class="fas fa-chart-bar me-1"></i> View Statistics
                                </a>
                                <a href="${this.apiBaseUrl}/stations/${stationId}/export/" 
                                   class="btn btn-sm btn-secondary w-100">
                                    <i class="fas fa-download me-1"></i> Export Data
                                </a>
                            </div>
                        </div>
                    `;
                    loadingPopup.setContent(noDataContent);
                } else {
                    // We have data, show it normally
                    loadingPopup.setContent(this.createDataPopupContent(data, stationId));
                }
            })
            .catch(error => {
                console.error("Error loading station data:", error);
                
                // Show error in popup but keep it open - FIX URL PATH
                const errorContent = `
                    <div class="info-container">
                        <h4>${stationName}</h4>
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-circle me-2"></i>
                            Error loading data: ${error.message}
                        </div>
                        
                        <div class="button-container mt-3">
                            <a href="${this.apiBaseUrl}/stations/${stationId}/statistics/" 
                               class="btn btn-lg btn-success w-100 mb-2 station-stats-direct-link">
                                <i class="fas fa-chart-bar me-1"></i> View Statistics
                            </a>
                            <button class="btn btn-sm btn-primary w-100" onclick="window.weatherMap.loadStationData('${stationId}')">
                                <i class="fas fa-sync-alt me-1"></i> Try Again
                            </button>
                        </div>
                    </div>
                `;
                loadingPopup.setContent(errorContent);
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
            // This won't be called as we now handle empty data in loadStationData
            return `<div class="info-container"><p>No recent data available for this station.</p></div>`;
        }
        
        const latest = results[0];
        const station = this.findStationById(stationId);
        const stationName = station ? 
            (station.properties ? station.properties.name : station.name) || 'Unknown Station' :
            latest.station_name || 'Unknown Station';
        
        console.log("Creating data popup for station:", stationId, stationName);
        
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
                
                <div class="button-container mt-3">
                    <a href="${this.apiBaseUrl}/stations/${stationId}/statistics/" 
                       class="btn btn-lg btn-success w-100 mb-2 station-stats-direct-link">
                        <i class="fas fa-chart-bar me-1"></i> View Station Statistics
                    </a>
                    <a href="${this.apiBaseUrl}/stations/${stationId}/export/" 
                       class="btn btn-sm btn-secondary w-100">
                        <i class="fas fa-download me-1"></i> Export Data
                    </a>
                </div>
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
            })
            .then(response => response.json())
            .then(data => {
                // Handle different response formats
                let results;
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

    /**
     * Zoom to all stations
     */
    zoomToAllStations() {
        const bounds = L.featureGroup([
            this.stationLayers.active, 
            this.stationLayers.inactive
        ]).getBounds();
        
        if (bounds.isValid()) {
            this.map.fitBounds(bounds);
            
            // If we're in overlay mode, also update the Windy iframe
            if (this.options.useWindyOverlay) {
                const center = bounds.getCenter();
                const zoom = this.map.getBoundsZoom(bounds);
                this.updateWindyIframe(center.lat, center.lng, 'All Stations');
            }
        } else {
            // Default to Kenya view if no stations
            this.map.setView(this.options.initialView, this.options.initialZoom);
            
            // Update Windy iframe if in overlay mode
            if (this.options.useWindyOverlay) {
                this.updateWindyIframe(this.options.initialView[0], this.options.initialView[1], 'Kenya');
            }
        }
    }
    
    /**
     * Add custom styles for markers on Windy map
     */
    addCustomStyles() {
        // Add CSS if not already present
        if (!document.getElementById('weather-station-map-styles')) {
            const styleElement = document.createElement('style');
            styleElement.id = 'weather-station-map-styles';
            styleElement.textContent = `
                .custom-marker-icon {
                    background: transparent !important;
                    border: none !important;
                }
                .marker-content {
                    color: rgba(224, 54, 22, 0.8);
                    font-size: 14px;
                    text-align: center;
                    text-shadow: 0px 0px 3px white, 0px 0px 2px white;
                    transition: all 0.3s ease;
                }
                .marker-content:hover {
                    transform: scale(1.2);
                    color: rgba(224, 54, 22, 1);
                }
                .marker-content.active {
                    color: rgba(224, 54, 22, 0.8);
                }
                .marker-content.inactive {
                    color: rgba(153, 153, 153, 0.6);
                }
                .marker-label {
                    position: absolute;
                    bottom: 100%;
                    left: 50%;
                    transform: translateX(-50%);
                    background: rgba(0, 0, 0, 0.5);
                    color: white;
                    padding: 1px 4px;
                    border-radius: 3px;
                    font-size: 10px;
                    white-space: nowrap;
                    pointer-events: none;
                    transition: all 0.3s ease;
                }
                .info-container {
                    padding: 6px 8px;
                    background: white;
                    background: rgba(255,255,255,0.85);
                    box-shadow: 0 0 15px rgba(0,0,0,0.2);
                    border-radius: 5px;
                    max-width: 300px;
                }
                .info-container h4 {
                    margin: 0 0 5px;
                    color: #555;
                }
                .opacity-control {
                    width: 180px;
                }
                /* Make popups more transparent */
                .leaflet-popup-content-wrapper {
                    background: rgba(255, 255, 255, 0.85);
                }
                .leaflet-popup-tip {
                    background: rgba(255, 255, 255, 0.85);
                }
                /* Enhanced popup styles for better visibility */
                .leaflet-popup {
                    z-index: 1100 !important; /* Make sure popups show above the map but below navbar */
                }
                
                .leaflet-popup-content-wrapper {
                    background: rgba(255, 255, 255, 0.95); /* More opaque background */
                    box-shadow: 0 3px 14px rgba(0,0,0,0.3);
                }
            `;
            document.head.appendChild(styleElement);
        }
    }

    // Add this new method to add opacity controls
    /**
     * Add opacity control for markers
     */
    addOpacityControl() {
        const opacityControl = L.control({ position: 'topright' });
        
        opacityControl.onAdd = () => {
            const div = L.DomUtil.create('div', 'info-container opacity-control');
            div.innerHTML = `
                <h4>Marker Opacity</h4>
                <input type="range" id="marker-opacity" min="10" max="100" value="70" class="form-range">
                <div class="d-flex justify-content-between">
                    <span>Transparent</span>
                    <span>Opaque</span>
                </div>
            `;
            
            // Prevent map interactions when using the slider
            L.DomEvent.disableClickPropagation(div);
            L.DomEvent.disableScrollPropagation(div);
            
            return div;
        };
        
        opacityControl.addTo(this.map);
        
        // Add event listener after the control is added to DOM
        setTimeout(() => {
            const slider = document.getElementById('marker-opacity');
            if (slider) {
                slider.addEventListener('input', (e) => {
                    const opacity = parseInt(e.target.value, 10) / 100;
                    this.updateMarkersOpacity(opacity);
                });
            }
        }, 100);
    }

    /**
     * Update opacity of all markers
     */
    updateMarkersOpacity(opacity) {
        // Update active markers
        this.stationLayers.active.eachLayer(layer => {
            layer.setOpacity(opacity);
            // Also update the inner icon if it has one
            const icon = layer.getElement();
            if (icon) {
                const markerContent = icon.querySelector('.marker-content');
                if (markerContent) {
                    markerContent.style.opacity = opacity;
                }
            }
        });
        
        // Update inactive markers with reduced opacity
        const inactiveOpacity = opacity * 0.5;
        this.stationLayers.inactive.eachLayer(layer => {
            layer.setOpacity(inactiveOpacity);
            // Also update the inner icon
            const icon = layer.getElement();
            if (icon) {
                const markerContent = icon.querySelector('.marker-content');
                if (markerContent) {
                    markerContent.style.opacity = inactiveOpacity;
                }
            }
        });
    }
}

// Initialize map when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if Windy map iframe exists
    const windyMapElement = document.getElementById('windy-map');
    const mapContainerElement = document.getElementById('map-container');
    
    // Configure the map based on the presence of Windy iframe
    let mapOptions = {
        useWindyOverlay: !!windyMapElement,
        windyMapId: 'windy-map',
        mapContainerId: 'map-container',
        initialView: [-0.503, 34.847], // JOOUST coordinates
        initialZoom: 9
    };
    
    // Create the map instance
    const targetElementId = mapOptions.useWindyOverlay ? 'map-container' : 'map';
    window.weatherMap = new WeatherStationMap(targetElementId, '/maps', mapOptions);
    
    // If the map is in overlay mode, add event listeners for the Windy iframe
    if (mapOptions.useWindyOverlay && windyMapElement) {
        // We can't directly listen to iframe content, but we can track when it loads
        windyMapElement.addEventListener('load', function() {
            window.weatherMap.syncWithWindyMap();
        });
        
        // Listen to map zoom events
        window.weatherMap.map.on('zoomend', function() {
            window.weatherMap.updateStationVisibility();
        });
    }
});