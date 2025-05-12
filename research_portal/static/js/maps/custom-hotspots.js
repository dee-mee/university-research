/**
 * Custom Hotspots for specific locations
 * Adds predefined hotspots for JOOUST, Mianthe, Siaya, and Bondo
 */
class CustomHotspots {
    constructor(map, hotspotInstance) {
        this.map = map;
        this.hotspot = hotspotInstance;
        this.customStations = [
            {
                id: 'jooust-station',
                name: 'JOOUST Weather Station',
                latitude: -0.093889,
                longitude: 34.258611,
                description: 'Jaramogi Oginga Odinga University of Science and Technology Weather Station',
                is_active: true,
                altitude: 1200,
                date_installed: '2023-01-15',
                climate_data: {
                    temperature: 26.5,
                    precipitation: 12.3,
                    humidity: 68,
                    wind_speed: 3.2,
                    timestamp: new Date().toISOString()
                }
            },
            {
                id: 'kisumu-station',
                name: 'Kisumu Weather Station',
                latitude: -0.0917,
                longitude: 34.7680,
                description: 'Kisumu City Weather Monitoring Station',
                is_active: true,
                altitude: 1150,
                date_installed: '2023-02-20',
                climate_data: {
                    temperature: 28.2,
                    precipitation: 5.7,
                    humidity: 62,
                    wind_speed: 4.1,
                    timestamp: new Date().toISOString()
                }
            },
            {
                id: 'siaya-station',
                name: 'Siaya Weather Station',
                latitude: -0.0617,
                longitude: 34.2422,
                description: 'Siaya County Weather Monitoring Station',
                is_active: true,
                altitude: 1180,
                date_installed: '2023-03-10',
                climate_data: {
                    temperature: 27.8,
                    precipitation: 18.5,
                    humidity: 75,
                    wind_speed: 2.8,
                    timestamp: new Date().toISOString()
                }
            },
            {
                id: 'bondo-station',
                name: 'Bondo Weather Station',
                latitude: -0.1003,
                longitude: 34.2755,
                description: 'Bondo Regional Climate Research Station',
                is_active: true,
                altitude: 1220,
                date_installed: '2023-01-05',
                climate_data: {
                    temperature: 25.9,
                    precipitation: 22.1,
                    humidity: 72,
                    wind_speed: 3.5,
                    timestamp: new Date().toISOString()
                }
            }
        ];
    }

    /**
     * Add custom hotspots to the map
     */
    addHotspots() {
        // Convert custom stations to GeoJSON format
        const stationsGeoJSON = this.customStations.map(station => {
            return {
                type: 'Feature',
                geometry: {
                    type: 'Point',
                    coordinates: [station.longitude, station.latitude]
                },
                properties: {
                    id: station.id,
                    name: station.name,
                    description: station.description,
                    is_active: station.is_active,
                    altitude: station.altitude,
                    date_installed: station.date_installed,
                    climate_data: station.climate_data
                }
            };
        });

        // Add custom stations to the existing stations
        if (window.weatherMap && window.weatherMap.stations) {
            // Filter out any existing stations with the same IDs
            const existingIds = window.weatherMap.stations
                .filter(s => s.properties && s.properties.id)
                .map(s => s.properties.id);
            
            const newStations = stationsGeoJSON.filter(s => !existingIds.includes(s.properties.id));
            
            // Add new stations to the existing ones
            window.weatherMap.stations = window.weatherMap.stations.concat(newStations);
            
            // Update station data for hotspot visualization
            this.customStations.forEach(station => {
                if (window.hotspot && window.hotspot.stationData) {
                    window.hotspot.stationData[station.id] = {
                        readings: [station.climate_data],
                        averages: {
                            temperature: station.climate_data.temperature,
                            precipitation: station.climate_data.precipitation
                        }
                    };
                }
            });
            
            // Redisplay stations
            window.weatherMap.displayStations();
            
            // If hotspot is available, update markers
            if (window.hotspot) {
                window.hotspot.updateMarkers();
            }
            
            // Center map to show all stations
            this.centerMapOnStations();
        }
    }
    
    /**
     * Center the map to show all custom stations
     */
    centerMapOnStations() {
        if (!this.map || this.customStations.length === 0) return;
        
        // Create bounds from custom stations
        const bounds = L.latLngBounds(
            this.customStations.map(station => [station.latitude, station.longitude])
        );
        
        // Fit map to bounds with some padding
        this.map.fitBounds(bounds, {
            padding: [50, 50],
            maxZoom: 10
        });
    }
    
    /**
     * Generate time series data for custom stations
     */
    generateTimeSeriesData() {
        // For each custom station, generate 7 days of data
        this.customStations.forEach(station => {
            const readings = [];
            const now = new Date();
            
            // Generate data for the past 7 days
            for (let i = 6; i >= 0; i--) {
                const date = new Date(now);
                date.setDate(date.getDate() - i);
                
                // Base values
                const baseTemp = station.climate_data.temperature;
                const basePrecip = station.climate_data.precipitation;
                
                // Add some random variation
                const tempVariation = (Math.random() * 4) - 2; // -2 to +2
                const precipVariation = (Math.random() * 5) - 1; // -1 to +4
                
                readings.push({
                    timestamp: date.toISOString(),
                    temperature: baseTemp + tempVariation,
                    precipitation: Math.max(0, basePrecip + precipVariation),
                    humidity: station.climate_data.humidity + ((Math.random() * 10) - 5),
                    wind_speed: station.climate_data.wind_speed + ((Math.random() * 2) - 1)
                });
            }
            
            // Add the readings to the station data
            if (window.hotspot && window.hotspot.stationData && window.hotspot.stationData[station.id]) {
                window.hotspot.stationData[station.id].readings = readings;
            }
        });
    }
}

// Create a global instance for direct access
window.customHotspots = null;

// Initialize custom hotspots when the page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Custom hotspots script loaded');
    
    // Add hotspots directly without waiting for other components
    addCustomHotspotsDirectly();
    
    // Also try the dependency-based approach as a fallback
    const checkDependencies = setInterval(() => {
        if (window.weatherMap && window.weatherMap.map) {
            console.log('Weather map detected, adding custom hotspots');
            clearInterval(checkDependencies);
            
            // Create custom hotspots
            window.customHotspots = new CustomHotspots(window.weatherMap.map, window.hotspot);
            
            // Add custom hotspots
            window.customHotspots.addHotspots();
            
            // Generate time series data
            window.customHotspots.generateTimeSeriesData();
        }
    }, 500);
});

// Function to add hotspots directly to the map
function addCustomHotspotsDirectly() {
    // Wait a bit for the map to initialize
    setTimeout(() => {
        console.log('Adding custom hotspots directly');
        
        // Define the locations with real coordinates
        const locations = [
            { name: 'JOOUST', lat: -0.093889, lng: 34.258611, temp: 26.5, rain: 12.3 },
            { name: 'Kisumu', lat: -0.0917, lng: 34.7680, temp: 28.2, rain: 5.7 },
            { name: 'Siaya', lat: -0.0617, lng: 34.2422, temp: 27.8, rain: 18.5 },
            { name: 'Bondo', lat: -0.1003, lng: 34.2755, temp: 25.9, rain: 22.1 }
        ];
        
        // Check if map is available
        if (window.weatherMap && window.weatherMap.map) {
            const map = window.weatherMap.map;
            
            // Add markers for each location
            locations.forEach(loc => {
                // Create a colored marker based on temperature
                const color = getTemperatureColor(loc.temp);
                const size = 30; // Fixed size for visibility
                
                const marker = L.marker([loc.lat, loc.lng], {
                    icon: L.divIcon({
                        className: 'custom-hotspot-marker',
                        html: `<div class="hotspot-dot" style="background-color: ${color}; width: ${size}px; height: ${size}px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.5);">
                                <span class="hotspot-label" style="position: absolute; top: -20px; left: 50%; transform: translateX(-50%); white-space: nowrap; background: rgba(0,0,0,0.7); color: white; padding: 2px 5px; border-radius: 3px; font-size: 12px;">${loc.name}</span>
                              </div>`,
                        iconSize: [size, size],
                        iconAnchor: [size/2, size/2]
                    })
                }).addTo(map);
                
                // Add popup with data and view data button
                marker.bindPopup(`
                    <div class="info-container">
                        <h4>${loc.name} Weather Station</h4>
                        <p><strong>Temperature:</strong> ${loc.temp} °C</p>
                        <p><strong>Rainfall:</strong> ${loc.rain} mm</p>
                        <p><strong>Last Updated:</strong> ${new Date().toLocaleString()}</p>
                        <div class="mt-3">
                            <a href="/maps/station-data/?id=${loc.name.toLowerCase()}-station" class="btn btn-primary btn-sm">
                                <i class="fas fa-chart-line"></i> View Data
                            </a>
                        </div>
                    </div>
                `);
            });
            
            // Center map on these locations
            const bounds = L.latLngBounds(locations.map(loc => [loc.lat, loc.lng]));
            map.fitBounds(bounds, { padding: [50, 50] });
            
            console.log('Custom hotspots added directly to map');
        } else {
            console.log('Map not available yet for direct hotspot addition');
        }
    }, 2000);
}

// Helper function to get color based on temperature
function getTemperatureColor(temp) {
    if (temp < 0) return '#0022FF';  // Very cold (blue)
    if (temp < 10) return '#0099FF'; // Cold (light blue)
    if (temp < 20) return '#00FFFF'; // Cool (cyan)
    if (temp < 25) return '#FFFF00'; // Warm (yellow)
    if (temp < 30) return '#FF9900'; // Hot (orange)
    return '#FF0000';                // Very hot (red)
}
