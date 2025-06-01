/**
 * Weather Station Network Map Functionality
 * 
 * This script handles the weather station map display, including:
 * - Fetching station data from the API
 * - Creating and managing map markers
 * - Handling station filtering and selection
 * - Creating station info cards and popups
 */

// Map configuration
const mapConfig = {
    center: [40.7128, -74.0060], // Default center (will be adjusted based on stations)
    zoom: 10,
    minZoom: 3,
    maxZoom: 18,
    tileLayers: {
        standard: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        satellite: 'https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        terrain: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png'
    }
};

// Station data and marker collections
let allStations = [];
let stationMarkers = {};
let markersGroup = null;
let map = null;

// Initialize the map when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    fetchStationData();
    setupEventListeners();
});

/**
 * Initialize the Leaflet map with tile layers and controls
 */
function initializeMap() {
    // Create map instance
    map = L.map('map', {
        center: mapConfig.center,
        zoom: mapConfig.zoom,
        minZoom: mapConfig.minZoom,
        maxZoom: mapConfig.maxZoom,
        zoomControl: false
    });
    
    // Add zoom control to top-right
    L.control.zoom({
        position: 'topright'
    }).addTo(map);
    
    // Add tile layer
    L.tileLayer(mapConfig.tileLayers.standard, {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    // Add layer control for different map styles
    const baseLayers = {
        "Standard": L.tileLayer(mapConfig.tileLayers.standard),
        "Satellite": L.tileLayer(mapConfig.tileLayers.satellite, {
            subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
            attribution: '&copy; Google Maps'
        }),
        "Terrain": L.tileLayer(mapConfig.tileLayers.terrain)
    };
    
    L.control.layers(baseLayers, null, {
        position: 'topright',
        collapsed: false
    }).addTo(map);
    
    // Create a layer group for markers
    markersGroup = L.layerGroup().addTo(map);
}

/**
 * Fetch station data from the API
 */
function fetchStationData() {
    showLoadingIndicator();
    
    fetch('/api/stations/')  // Updated from '/maps/api/stations/' to match the actual API route
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            allStations = data;
            createStationMarkers();
            populateStationDropdown();
            updateFilterCounts();
            zoomToAllStations();
            hideLoadingIndicator();
        })
        .catch(error => {
            console.error('Error fetching station data:', error);
            displayErrorMessage('Failed to load station data. Please try again later.');
            hideLoadingIndicator();
        });
}

/**
 * Create markers for all stations and add them to the map
 */
function createStationMarkers() {
    // Clear existing markers
    markersGroup.clearLayers();
    stationMarkers = {};
    
    // Create marker for each station
    allStations.forEach(station => {
        const marker = createStationMarker(station);
        
        if (marker) {
            marker.addTo(markersGroup);
            stationMarkers[station.id] = marker;
        }
    });
}

/**
 * Create a marker for a specific station
 */
function createStationMarker(station) {
    if (!station.latitude || !station.longitude) {
        console.warn(`Station ${station.id} (${station.name}) has invalid coordinates`);
        return null;
    }
    
    const isActive = station.status === 'active';
    const batteryLevel = station.battery_level || 100;
    
    // Create custom icon
    const customIcon = L.divIcon({
        className: 'custom-marker-icon',
        html: createMarkerIconHtml(station, isActive, batteryLevel),
        iconSize: [32, 32],
        iconAnchor: [16, 32]
    });
    
    // Create marker with popup
    const marker = L.marker([station.latitude, station.longitude], {
        icon: customIcon,
        title: station.name,
        alt: `${station.name} (${station.id})`,
        riseOnHover: true,
        riseOffset: 250
    });
    
    // Add popup with station info
    marker.bindPopup(() => createStationPopupContent(station));
    
    // Add click handler
    marker.on('click', () => {
        // Create or update station card
        createStationInfoCard(station);
        
        // Center map on station (with offset if station card is visible)
        const offset = document.querySelector('#station-info-cards').offsetHeight / 2;
        map.panTo([station.latitude, station.longitude], {
            animate: true,
            duration: 0.5,
            paddingBottomRight: [0, offset]
        });
    });
    
    return marker;
}

/**
 * Create HTML for the marker icon
 */
function createMarkerIconHtml(station, isActive, batteryLevel) {
    let iconClass = isActive ? 'fa-solid fa-location-dot active' : 'fa-solid fa-location-dot inactive';
    
    // Determine battery indicator class
    let batteryClass = 'battery-good';
    if (batteryLevel < 20) {
        batteryClass = 'battery-critical';
    } else if (batteryLevel < 40) {
        batteryClass = 'battery-low';
    }
    
    return `
        <div class="marker-content ${isActive ? 'active' : 'inactive'}">
            <i class="${iconClass}"></i>
            <div class="battery-indicator ${batteryClass}"></div>
            ${station.show_label ? `<div class="marker-label">${station.name}</div>` : ''}
        </div>
    `;
}

/**
 * Create content for station popup
 */
function createStationPopupContent(station) {
    // Format last updated time
    const lastUpdated = station.last_data_received ? 
        new Date(station.last_data_received).toLocaleString() : 
        'No data received';
    
    // Determine status class
    let statusClass = 'status-inactive';
    if (station.status === 'active') {
        statusClass = 'status-active';
    } else if (station.status === 'maintenance') {
        statusClass = 'status-maintenance';
    } else if (station.status === 'lost') {
        statusClass = 'status-lost';
    }
    
    // Extract numeric station ID if it has a prefix
    const stationIdForUrl = station.id.startsWith('ws_') ? station.id.substring(3) : station.id;
    
    // Create popup content
    const content = document.createElement('div');
    content.className = 'info-container';
    content.innerHTML = `
        <h4>${station.name}</h4>
        <p><strong>ID:</strong> ${station.id}</p>
        <p><strong>Status:</strong> <span class="${statusClass}">${station.status || 'Unknown'}</span></p>
        <p><strong>Type:</strong> ${station.device_type || 'Standard'}</p>
        <p><strong>Location:</strong> ${station.location_name || 'Unknown'}</p>
        <p><strong>Coordinates:</strong> ${station.latitude.toFixed(6)}, ${station.longitude.toFixed(6)}</p>
        <p><strong>Last Updated:</strong> ${lastUpdated}</p>
        ${station.battery_level ? `<p><strong>Battery:</strong> ${station.battery_level}%</p>` : ''}
        ${station.signal_strength ? `<p><strong>Signal:</strong> ${station.signal_strength}%</p>` : ''}
        
        ${station.has_alerts ? `
        <div class="alert alert-warning">
            <small><i class="fas fa-exclamation-triangle"></i> This station has active alerts</small>
        </div>
        ` : ''}
        
        ${!station.is_online ? `
        <div class="alert alert-danger">
            <small><i class="fas fa-times-circle"></i> This station is currently offline</small>
        </div>
        ` : ''}
        
        <div class="text-center">
            <a href="/maps/stations/${stationIdForUrl}/" class="btn btn-sm btn-success">
                <i class="fas fa-chart-line me-1"></i> View Statistics
            </a>
        </div>
    `;
    
    return content;
}

/**
 * Create or update station info card
 */
function createStationInfoCard(station) {
    const container = document.getElementById('station-cards-container');
    
    // Check if card already exists
    let card = document.getElementById(`station-card-${station.id}`);
    
    if (!card) {
        // Create new card
        card = document.createElement('div');
        card.id = `station-card-${station.id}`;
        card.className = 'col-md-4 mb-3';
        container.appendChild(card);
    }
    
    // Update card content
    const statusClass = station.status === 'active' ? 'text-success' : 
                        station.status === 'maintenance' ? 'text-warning' : 'text-danger';
    
    // Extract numeric station ID if it has a prefix
    const stationIdForUrl = station.id.startsWith('ws_') ? station.id.substring(3) : station.id;
    
    card.innerHTML = `
        <div class="card station-card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5 class="mb-0">${station.name}</h5>
                <button type="button" class="btn-close" aria-label="Close" 
                    onclick="document.getElementById('station-card-${station.id}').remove()"></button>
            </div>
            <div class="card-body">
                <p class="coordinates">
                    <i class="fas fa-map-marker-alt me-1"></i> 
                    ${station.latitude.toFixed(6)}, ${station.longitude.toFixed(6)}
                </p>
                <p class="status ${statusClass}">
                    <i class="fas fa-circle me-1"></i> ${station.status || 'Unknown'}
                </p>
                <div class="d-grid gap-2">
                    <a href="/maps/stations/${stationIdForUrl}/" class="btn btn-success station-stats-btn">
                        <i class="fas fa-chart-line me-1"></i> View Statistics
                    </a>
                </div>
            </div>
        </div>
    `;
    
    // Make container visible
    document.getElementById('station-info-cards').style.display = 'block';
    document.getElementById('station-info-cards').scrollIntoView({
        behavior: 'smooth',
        block: 'start'
    });
}

/**
 * Populate station dropdown with options
 */
function populateStationDropdown() {
    const select = document.getElementById('stationSelect');
    
    if (!select) return;
    
    // Sort stations alphabetically by name
    const sortedStations = [...allStations].sort((a, b) => a.name.localeCompare(b.name));
    
    // Add option for each station
    sortedStations.forEach(station => {
        const option = document.createElement('option');
        option.value = station.id;
        option.textContent = station.name;
        select.appendChild(option);
    });
}

/**
 * Set up event listeners for UI elements
 */
function setupEventListeners() {
    // Station selection dropdown
    const stationSelect = document.getElementById('stationSelect');
    if (stationSelect) {
        stationSelect.addEventListener('change', function() {
            const stationId = this.value;
            
            if (stationId) {
                // Find selected station
                const station = allStations.find(s => s.id == stationId);
                
                if (station && stationMarkers[station.id]) {
                    // Zoom to station and open popup
                    map.setView([station.latitude, station.longitude], 14);
                    stationMarkers[station.id].openPopup();
                }
            } else {
                // If "All Stations" selected, zoom to fit all stations
                zoomToAllStations();
            }
        });
    }
    
    // Filter checkboxes
    const filterCheckboxes = document.querySelectorAll('.filter-checkbox input');
    filterCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', applyFilters);
    });
    
    // Reset filters button
    const resetBtn = document.getElementById('reset-filters');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetFilters);
    }
}

/**
 * Apply filters based on checkbox selections
 */
function applyFilters() {
    const filters = {
        sources: {
            weatherStations: document.getElementById('filter-weather-stations')?.checked ?? true,
            fieldDevices: document.getElementById('filter-field-devices')?.checked ?? true,
            manualEntries: document.getElementById('filter-manual-entries')?.checked ?? true
        },
        status: {
            active: document.getElementById('filter-status-active')?.checked ?? true,
            maintenance: document.getElementById('filter-status-maintenance')?.checked ?? false,
            inactive: document.getElementById('filter-status-inactive')?.checked ?? false,
            lost: document.getElementById('filter-status-lost')?.checked ?? false
        },
        battery: {
            good: document.getElementById('filter-battery-good')?.checked ?? true,
            low: document.getElementById('filter-battery-low')?.checked ?? false,
            critical: document.getElementById('filter-battery-critical')?.checked ?? false
        }
    };
    
    // Apply filters to each station marker
    allStations.forEach(station => {
        const marker = stationMarkers[station.id];
        if (!marker) return;
        
        // Check if station matches filters
        const sourceMatch = (station.device_type === 'weather_station' && filters.sources.weatherStations) ||
                           (station.device_type === 'field_device' && filters.sources.fieldDevices) ||
                           (station.device_type === 'manual_entry' && filters.sources.manualEntries);
        
        const statusMatch = (station.status === 'active' && filters.status.active) ||
                           (station.status === 'maintenance' && filters.status.maintenance) ||
                           (station.status === 'inactive' && filters.status.inactive) ||
                           (station.status === 'lost' && filters.status.lost);
        
        let batteryLevel = station.battery_level || 100;
        const batteryMatch = (batteryLevel >= 40 && filters.battery.good) ||
                            (batteryLevel >= 20 && batteryLevel < 40 && filters.battery.low) ||
                            (batteryLevel < 20 && filters.battery.critical);
        
        // Show or hide marker based on filter match
        if (sourceMatch && statusMatch && batteryMatch) {
            marker.addTo(markersGroup);
        } else {
            markersGroup.removeLayer(marker);
        }
    });
}

/**
 * Reset all filters to their default state
 */
function resetFilters() {
    // Reset source filters
    document.getElementById('filter-weather-stations').checked = true;
    document.getElementById('filter-field-devices').checked = true;
    document.getElementById('filter-manual-entries').checked = true;
    
    // Reset status filters
    document.getElementById('filter-status-active').checked = true;
    document.getElementById('filter-status-maintenance').checked = false;
    document.getElementById('filter-status-inactive').checked = false;
    document.getElementById('filter-status-lost').checked = false;
    
    // Reset battery filters
    document.getElementById('filter-battery-good').checked = true;
    document.getElementById('filter-battery-low').checked = false;
    document.getElementById('filter-battery-critical').checked = false;
    
    // Apply reset filters
    applyFilters();
}

/**
 * Update filter count badges
 */
function updateFilterCounts() {
    // Source type counts
    const weatherStationCount = allStations.filter(s => s.device_type === 'weather_station').length;
    const fieldDeviceCount = allStations.filter(s => s.device_type === 'field_device').length;
    const manualEntryCount = allStations.filter(s => s.device_type === 'manual_entry').length;
    
    document.getElementById('weather-station-count').textContent = weatherStationCount;
    document.getElementById('field-device-count').textContent = fieldDeviceCount;
    document.getElementById('manual-entry-count').textContent = manualEntryCount;
    
    // Status counts
    const activeCount = allStations.filter(s => s.status === 'active').length;
    const maintenanceCount = allStations.filter(s => s.status === 'maintenance').length;
    const inactiveCount = allStations.filter(s => s.status === 'inactive').length;
    const lostCount = allStations.filter(s => s.status === 'lost').length;
    
    document.getElementById('status-active-count').textContent = activeCount;
    document.getElementById('status-maintenance-count').textContent = maintenanceCount;
    document.getElementById('status-inactive-count').textContent = inactiveCount;
    document.getElementById('status-lost-count').textContent = lostCount;
    
    // Battery level counts
    const goodBatteryCount = allStations.filter(s => (s.battery_level || 100) >= 40).length;
    const lowBatteryCount = allStations.filter(s => (s.battery_level || 100) >= 20 && (s.battery_level || 100) < 40).length;
    const criticalBatteryCount = allStations.filter(s => (s.battery_level || 100) < 20).length;
    
    document.getElementById('battery-good-count').textContent = goodBatteryCount;
    document.getElementById('battery-low-count').textContent = lowBatteryCount;
    document.getElementById('battery-critical-count').textContent = criticalBatteryCount;
}

/**
 * Zoom map to show all stations
 */
function zoomToAllStations() {
    if (allStations.length === 0) return;
    
    // Create bounds object
    const bounds = L.latLngBounds();
    
    // Add each station to bounds
    allStations.forEach(station => {
        if (station.latitude && station.longitude) {
            bounds.extend([station.latitude, station.longitude]);
        }
    });
    
    // Zoom to fit all stations
    if (bounds.isValid()) {
        map.fitBounds(bounds, {
            padding: [50, 50],
            maxZoom: 14
        });
    }
}

/**
 * Show loading indicator
 */
function showLoadingIndicator() {
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'map-loading';
    loadingDiv.style.position = 'absolute';
    loadingDiv.style.top = '50%';
    loadingDiv.style.left = '50%';
    loadingDiv.style.transform = 'translate(-50%, -50%)';
    loadingDiv.style.zIndex = '1000';
    loadingDiv.style.background = 'rgba(255,255,255,0.8)';
    loadingDiv.style.padding = '20px';
    loadingDiv.style.borderRadius = '10px';
    loadingDiv.style.boxShadow = '0 0 10px rgba(0,0,0,0.2)';
    
    loadingDiv.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2 mb-0">Loading station data...</p>
        </div>
    `;
    
    document.getElementById('map').appendChild(loadingDiv);
}

/**
 * Hide loading indicator
 */
function hideLoadingIndicator() {
    const loadingDiv = document.getElementById('map-loading');
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

/**
 * Display error message on the map
 */
function displayErrorMessage(message) {
    const errorDiv = document.createElement('div');
    errorDiv.id = 'map-error';
    errorDiv.style.position = 'absolute';
    errorDiv.style.top = '50%';
    errorDiv.style.left = '50%';
    errorDiv.style.transform = 'translate(-50%, -50%)';
    errorDiv.style.zIndex = '1000';
    errorDiv.style.background = 'rgba(255,255,255,0.9)';
    errorDiv.style.padding = '20px';
    errorDiv.style.borderRadius = '10px';
    errorDiv.style.boxShadow = '0 0 10px rgba(0,0,0,0.2)';
    errorDiv.style.textAlign = 'center';
    
    errorDiv.innerHTML = `
        <div class="text-center">
            <div class="text-danger mb-3">
                <i class="fas fa-exclamation-circle" style="font-size: 2rem;"></i>
            </div>
            <p class="mb-3">${message}</p>
            <button class="btn btn-primary btn-sm" onclick="fetchStationData()">
                <i class="fas fa-sync-alt me-1"></i> Retry
            </button>
        </div>
    `;
    
    document.getElementById('map').appendChild(errorDiv);
}