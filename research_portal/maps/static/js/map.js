// Initialize map and layers
let map;
let weatherStationLayer;
let fieldDeviceLayer;
let manualEntryLayer;

// Layer groups for filtering
const weatherStations = L.layerGroup();
const fieldDevices = L.layerGroup();
const manualEntries = L.layerGroup();

// Counters for each data source and status
let weatherStationCount = 0;
let fieldDeviceCount = 0;
let manualEntryCount = 0;

let statusActiveCount = 0;
let statusMaintenanceCount = 0;
let statusInactiveCount = 0;
let statusLostCount = 0;

let batteryGoodCount = 0;
let batteryLowCount = 0;
let batteryCriticalCount = 0;

// Custom icons
const weatherStationIcon = L.divIcon({
    className: 'custom-div-icon',
    html: '<div class="marker-pin weather-station"><i class="fas fa-cloud"></i></div>',
    iconSize: [30, 42],
    iconAnchor: [15, 42]
});

const fieldDeviceIcon = L.divIcon({
    className: 'custom-div-icon',
    html: '<div class="marker-pin field-device"><i class="fas fa-microchip"></i></div>',
    iconSize: [30, 42],
    iconAnchor: [15, 42]
});

const manualEntryIcon = L.divIcon({
    className: 'custom-div-icon',
    html: '<div class="marker-pin manual-entry"><i class="fas fa-user"></i></div>',
    iconSize: [30, 42],
    iconAnchor: [15, 42]
});

// Status-based field device icons
function getFieldDeviceIcon(status, batteryLevel) {
    let statusClass = 'status-active';
    let iconContent = '<i class="fas fa-microchip"></i>';
    
    // Determine status class
    if (status === 'maintenance') {
        statusClass = 'status-maintenance';
        iconContent = '<i class="fas fa-tools"></i>';
    } else if (status === 'inactive') {
        statusClass = 'status-inactive';
    } else if (status === 'lost') {
        statusClass = 'status-lost';
        iconContent = '<i class="fas fa-question"></i>';
    }
    
    // Add battery indicator if available
    let batteryIndicator = '';
    if (batteryLevel !== null && batteryLevel !== undefined) {
        let batteryClass = 'battery-good';
        if (batteryLevel < 20) {
            batteryClass = 'battery-critical';
        } else if (batteryLevel < 40) {
            batteryClass = 'battery-low';
        }
        batteryIndicator = `<div class="battery-indicator ${batteryClass}"></div>`;
    }
    
    return L.divIcon({
        className: 'custom-div-icon',
        html: `<div class="marker-pin field-device ${statusClass}">${iconContent}${batteryIndicator}</div>`,
        iconSize: [30, 42],
        iconAnchor: [15, 42]
    });
}

// Initialize the map
function initMap() {
    // Create the map
    map = L.map('map').setView([0, 0], 2);
    
    // Add base tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    // Add layer groups to map
    weatherStations.addTo(map);
    fieldDevices.addTo(map);
    manualEntries.addTo(map);
    
    // Load data
    loadMapData();
    
    // Initialize filter controls
    initFilterControls();
}

// Load map data from API
function loadMapData() {
    // Show loading indicator
    document.getElementById('map-loading').style.display = 'block';
    
    // Reset counters
    weatherStationCount = 0;
    fieldDeviceCount = 0;
    manualEntryCount = 0;
    
    statusActiveCount = 0;
    statusMaintenanceCount = 0;
    statusInactiveCount = 0;
    statusLostCount = 0;
    
    batteryGoodCount = 0;
    batteryLowCount = 0;
    batteryCriticalCount = 0;
    
    // Clear existing layers
    weatherStations.clearLayers();
    fieldDevices.clearLayers();
    manualEntries.clearLayers();
    
    // Fetch station data from the database through API
    fetch('/api/stations/')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Process the data
            console.log('Received map data:', data);
            
            // Process all stations
            data.forEach(station => {
                if (station.device_type === 'weather_station') {
                    processWeatherStation(station);
                } else if (station.device_type === 'field_device') {
                    processFieldDevice(station);
                } else if (station.device_type === 'manual_entry') {
                    processManualEntry(station);
                }
            });
            
            // Update filter counts
            updateFilterCounts();
            
            // Hide loading indicator
            document.getElementById('map-loading').style.display = 'none';
            
            // Make sure all layers are added to the map
            weatherStations.addTo(map);
            fieldDevices.addTo(map);
            manualEntries.addTo(map);
            
            // Update station dropdown
            updateStationDropdown(data);
        })
        .catch(error => {
            console.error('Error fetching map data:', error);
            document.getElementById('map-error').textContent = 'Failed to load map data. Please try again later.';
            document.getElementById('map-error').style.display = 'block';
            document.getElementById('map-loading').style.display = 'none';
        });
}

// Process weather stations data
function processWeatherStations(data) {
    L.geoJSON(data, {
        pointToLayer: function(feature, latlng) {
            return L.marker(latlng, { icon: weatherStationIcon });
        },
        onEachFeature: function(feature, layer) {
            const props = feature.properties;
            
            // Create popup content
            let popupContent = `
                <div class="map-popup">
                    <h5>${props.name}</h5>
                    <p><strong>Station ID:</strong> ${props.station_id}</p>
                    <p><strong>Status:</strong> ${props.is_active ? 'Active' : 'Inactive'}</p>
                    <p><strong>Last Data:</strong> ${props.last_data_feed || 'N/A'}</p>
                    <div class="popup-actions">
                        <a href="/maps/stations/${props.id}/statistics/" class="btn btn-sm btn-primary">View Statistics</a>
                    </div>
                </div>
            `;
            
            layer.bindPopup(popupContent);
        }
    }).addTo(weatherStations);
}

// Process field devices data
function processFieldDevices(data) {
    L.geoJSON(data, {
        pointToLayer: function(feature, latlng) {
            const props = feature.properties;
            
            // Update status counters
            switch(props.status) {
                case 'active':
                    statusActiveCount++;
                    break;
                case 'maintenance':
                    statusMaintenanceCount++;
                    break;
                case 'inactive':
                    statusInactiveCount++;
                    break;
                case 'lost':
                    statusLostCount++;
                    break;
            }
            
            // Update battery counters
            if (props.battery_level !== null && props.battery_level !== undefined) {
                if (props.battery_level < 20) {
                    batteryCriticalCount++;
                } else if (props.battery_level < 40) {
                    batteryLowCount++;
                } else {
                    batteryGoodCount++;
                }
            }
            
            return L.marker(latlng, { 
                icon: getFieldDeviceIcon(props.status, props.battery_level)
            });
        },
        onEachFeature: function(feature, layer) {
            const props = feature.properties;
            
            // Format battery level
            let batteryDisplay = 'N/A';
            if (props.battery_level !== null && props.battery_level !== undefined) {
                let batteryClass = 'text-success';
                if (props.battery_level < 20) {
                    batteryClass = 'text-danger';
                } else if (props.battery_level < 40) {
                    batteryClass = 'text-warning';
                }
                batteryDisplay = `<span class="${batteryClass}">${props.battery_level}%</span>`;
            }
            
            // Format signal strength
            let signalDisplay = 'N/A';
            if (props.signal_strength !== null && props.signal_strength !== undefined) {
                let signalClass = 'text-success';
                if (props.signal_strength < -90) {
                    signalClass = 'text-danger';
                } else if (props.signal_strength < -70) {
                    signalClass = 'text-warning';
                }
                signalDisplay = `<span class="${signalClass}">${props.signal_strength} dBm</span>`;
            }
            
            // Format last calibration date
            let calibrationDisplay = props.last_calibration || 'Never';
            let nextCalibrationDisplay = props.next_calibration || 'Not scheduled';
            
            // Format firmware version
            let firmwareDisplay = props.firmware_version || 'Unknown';
            
            // Format transmission interval
            let transmissionDisplay = props.transmission_interval ? `${props.transmission_interval} min` : 'Unknown';
            
            // Format latest sensor readings
            let latestReadings = '';
            if (props.latest_data) {
                latestReadings = `
                    <div class="latest-readings">
                        <h6>Latest Readings</h6>
                        <div class="readings-grid">
                            ${props.latest_data.temperature ? `<div><i class="fas fa-thermometer-half"></i> ${props.latest_data.temperature}°C</div>` : ''}
                            ${props.latest_data.humidity ? `<div><i class="fas fa-tint"></i> ${props.latest_data.humidity}%</div>` : ''}
                            ${props.latest_data.precipitation ? `<div><i class="fas fa-cloud-rain"></i> ${props.latest_data.precipitation} mm</div>` : ''}
                            ${props.latest_data.wind_speed ? `<div><i class="fas fa-wind"></i> ${props.latest_data.wind_speed} km/h</div>` : ''}
                        </div>
                    </div>
                `;
            }
            
            // Create status badge
            let statusBadgeClass = 'bg-success';
            if (props.status === 'maintenance') {
                statusBadgeClass = 'bg-warning';
            } else if (props.status === 'inactive') {
                statusBadgeClass = 'bg-secondary';
            } else if (props.status === 'lost') {
                statusBadgeClass = 'bg-danger';
            }
            
            // Create popup content with enhanced information
            let popupContent = `
                <div class="map-popup field-device-popup">
                    <div class="popup-header">
                        <h5>${props.name}</h5>
                        <span class="badge ${statusBadgeClass}">${props.status}</span>
                    </div>
                    
                    <div class="device-info">
                        <p><strong>Device ID:</strong> ${props.device_id}</p>
                        <p><strong>Type:</strong> ${props.device_type || 'N/A'}</p>
                        <p><strong>Manufacturer:</strong> ${props.manufacturer || 'N/A'}</p>
                        <p><strong>Model:</strong> ${props.model_number || 'N/A'}</p>
                        <p><strong>Firmware:</strong> ${firmwareDisplay}</p>
                    </div>
                    
                    <div class="device-status">
                        <div class="status-item">
                            <i class="fas fa-battery-half"></i>
                            <span>Battery: ${batteryDisplay}</span>
                        </div>
                        <div class="status-item">
                            <i class="fas fa-signal"></i>
                            <span>Signal: ${signalDisplay}</span>
                        </div>
                        <div class="status-item">
                            <i class="fas fa-clock"></i>
                            <span>Transmission: ${transmissionDisplay}</span>
                        </div>
                    </div>
                    
                    ${latestReadings}
                    
                    <div class="device-maintenance">
                        <p><strong>Last Communication:</strong> ${props.last_communication || 'N/A'}</p>
                        <p><strong>Last Calibration:</strong> ${calibrationDisplay}</p>
                        <p><strong>Next Calibration:</strong> ${nextCalibrationDisplay}</p>
                    </div>
                    
                    <div class="popup-actions">
                        <a href="/maps/field-devices/${props.id}/" class="btn btn-sm btn-primary">View Details</a>
                        <a href="/maps/field-devices/${props.id}/calibrate/" class="btn btn-sm btn-warning">Calibrate</a>
                        <a href="/maps/field-devices/${props.id}/data/" class="btn btn-sm btn-info">View Data</a>
                    </div>
                </div>
            `;
            
            layer.bindPopup(popupContent);
        }
    }).addTo(fieldDevices);
}

// Process manual entries data
function processManualEntries(data) {
    L.geoJSON(data, {
        pointToLayer: function(feature, latlng) {
            return L.marker(latlng, { icon: manualEntryIcon });
        },
        onEachFeature: function(feature, layer) {
            const props = feature.properties;
            
            // Create popup content
            let popupContent = `
                <div class="map-popup">
                    <h5>${props.title || 'Manual Entry'}</h5>
                    <p><strong>Date:</strong> ${props.date || 'N/A'}</p>
                    <p><strong>Recorded by:</strong> ${props.recorded_by || 'N/A'}</p>
                    <p>${props.description || ''}</p>
                    <div class="popup-actions">
                        <a href="/maps/manual-entries/${props.id}/" class="btn btn-sm btn-primary">View Details</a>
                    </div>
                </div>
            `;
            
            layer.bindPopup(popupContent);
        }
    }).addTo(manualEntries);
}

// Initialize filter controls
function initFilterControls() {
    // Weather station filter
    document.getElementById('filter-weather-stations').addEventListener('change', function() {
        if (this.checked) {
            map.addLayer(weatherStations);
        } else {
            map.removeLayer(weatherStations);
        }
    });
    
    // Field device filter
    document.getElementById('filter-field-devices').addEventListener('change', function() {
        if (this.checked) {
            map.addLayer(fieldDevices);
        } else {
            map.removeLayer(fieldDevices);
        }
    });
    
    // Manual entry filter
    document.getElementById('filter-manual-entries').addEventListener('change', function() {
        if (this.checked) {
            map.addLayer(manualEntries);
        } else {
            map.removeLayer(manualEntries);
        }
    });
    
    // Status filters
    document.getElementById('filter-status-active').addEventListener('change', function() {
        filterFieldDevices();
    });
    document.getElementById('filter-status-maintenance').addEventListener('change', function() {
        filterFieldDevices();
    });
    document.getElementById('filter-status-inactive').addEventListener('change', function() {
        filterFieldDevices();
    });
    document.getElementById('filter-status-lost').addEventListener('change', function() {
        filterFieldDevices();
    });
    
    // Battery filters
    document.getElementById('filter-battery-good').addEventListener('change', function() {
        filterFieldDevices();
    });
    document.getElementById('filter-battery-low').addEventListener('change', function() {
        filterFieldDevices();
    });
    document.getElementById('filter-battery-critical').addEventListener('change', function() {
        filterFieldDevices();
    });
    
    // Reset filters button
    document.getElementById('reset-filters').addEventListener('click', function() {
        // Reset checkboxes
        document.getElementById('filter-weather-stations').checked = true;
        document.getElementById('filter-field-devices').checked = true;
        document.getElementById('filter-manual-entries').checked = true;
        document.getElementById('filter-status-active').checked = true;
        document.getElementById('filter-status-maintenance').checked = true;
        document.getElementById('filter-status-inactive').checked = true;
        document.getElementById('filter-status-lost').checked = true;
        document.getElementById('filter-battery-good').checked = true;
        document.getElementById('filter-battery-low').checked = true;
        document.getElementById('filter-battery-critical').checked = true;
        
        // Reset layers
        map.addLayer(weatherStations);
        map.addLayer(fieldDevices);
        map.addLayer(manualEntries);
        
        // Reset field device filters
        fieldDevices.eachLayer(function(layer) {
            layer.setStyle({ opacity: 1 });
        });
    });
}

// Filter field devices based on selected criteria
function filterFieldDevices() {
    fieldDevices.eachLayer(function(layer) {
        const props = layer.feature.properties;
        
        // Check status filters
        const statusFilters = [
            ['active', 'filter-status-active'],
            ['maintenance', 'filter-status-maintenance'],
            ['inactive', 'filter-status-inactive'],
            ['lost', 'filter-status-lost']
        ];
        
        let statusMatch = false;
        for (const [status, filterId] of statusFilters) {
            if (props.status === status && document.getElementById(filterId).checked) {
                statusMatch = true;
                break;
            }
        }
        
        // Check battery filters
        let batteryMatch = true;
        const batteryLevel = props.battery_level;
        if (batteryLevel !== null && batteryLevel !== undefined) {
            if (batteryLevel < 20 && !document.getElementById('filter-battery-critical').checked) {
                batteryMatch = false;
            } else if (batteryLevel < 40 && !document.getElementById('filter-battery-low').checked) {
                batteryMatch = false;
            } else if (!document.getElementById('filter-battery-good').checked) {
                batteryMatch = false;
            }
        }
        
        // Set layer opacity based on filters
        if (statusMatch && batteryMatch) {
            layer.setStyle({ opacity: 1 });
        } else {
            layer.setStyle({ opacity: 0.3 });
        }
    });
}

// Update filter count badges
function updateFilterCounts() {
    document.getElementById('weather-station-count').textContent = weatherStationCount;
    document.getElementById('field-device-count').textContent = fieldDeviceCount;
    document.getElementById('manual-entry-count').textContent = manualEntryCount;
    
    document.getElementById('status-active-count').textContent = statusActiveCount;
    document.getElementById('status-maintenance-count').textContent = statusMaintenanceCount;
    document.getElementById('status-inactive-count').textContent = statusInactiveCount;
    document.getElementById('status-lost-count').textContent = statusLostCount;
    
    document.getElementById('battery-good-count').textContent = batteryGoodCount;
    document.getElementById('battery-low-count').textContent = batteryLowCount;
    document.getElementById('battery-critical-count').textContent = batteryCriticalCount;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initMap();
});
