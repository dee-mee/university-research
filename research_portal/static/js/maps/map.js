// This file can be included in the template if you want to separate the JavaScript
class WeatherStationMap {
    constructor(mapElement, apiBaseUrl) {
        this.mapElement = mapElement;
        this.apiBaseUrl = apiBaseUrl;
        this.map = null;
        this.stationsLayer = null;
        this.activeIcon = null;
        this.inactiveIcon = null;
        this.info = null;
        this.legend = null;
        this.stationData = {};
        this.climateData = {};
        
        this.initialize();
    }
    
    initialize() {
        // Initialize map
        this.map = L.map(this.mapElement).setView([0, 0], 2);
        
        // Add tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(this.map);
        
        // Initialize icons
        this.initializeIcons();
        
        // Add controls
        this.addControls();
        
        // Load data
        this.loadStations();
    }
    
    initializeIcons() {
        this.activeIcon = L.icon({
            iconUrl: "/static/maps/images/marker-active.png",
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowUrl: "/static/maps/images/marker-shadow.png",
            shadowSize: [41, 41]
        });
        
        this.inactiveIcon = L.icon({
            iconUrl: "/static/maps/images/marker-inactive.png",
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowUrl: "/static/maps/images/marker-shadow.png",
            shadowSize: [41, 41]
        });
    }
    
    addControls() {
        // Add legend
        this.legend = L.control({position: 'bottomright'});
        this.legend.onAdd = () => {
            const div = L.DomUtil.create('div', 'info-container legend');
            div.innerHTML = `
                <h4>Station Status</h4>
                <i style="background-color: #38a169"></i> Active<br>
                <i style="background-color: #718096"></i> Inactive<br>
            `;
            return div;
        };
        this.legend.addTo(this.map);
        
        // Add info panel
        this.info = L.control();
        this.info.onAdd = () => {
            this._div = L.DomUtil.create('div', 'info-container');
            this.updateInfo();
            return this._div;
        };
        this.info.updateInfo = (props) => {
            this._div.innerHTML = props ? 
                `<h4>${props.name}</h4>
                 <p>${props.description || 'No description available'}</p>
                 <p>Altitude: ${props.altitude ? props.altitude + ' m' : 'Unknown'}</p>
                 <p>Status: ${props.is_active ? 'Active' : 'Inactive'}</p>
                 <p>Installed: ${props.date_installed || 'Unknown'}</p>
                 <p><a href="${this.apiBaseUrl}/stations/${props.id}/data/">View Data</a></p>`
                : 'Hover over a station';
        };
        this.info.addTo(this.map);
    }
    
    loadStations() {
        fetch(`${this.apiBaseUrl}/stations/`)
            .then(response => response.json())
            .then(data => {
                this.stationData = data;
                this.renderStations();
                this.loadClimateData();
            })
            .catch(error => {
                console.error('Error loading stations:', error);
            });
    }
    
    renderStations() {
        if (this.stationsLayer) {
            this.map.removeLayer(this.stationsLayer);
        }
        
        this.stationsLayer = L.geoJSON(this.stationData, {
            pointToLayer: (feature, latlng) => {
                const icon = feature.properties.is_active ? this.activeIcon : this.inactiveIcon;
                return L.marker(latlng, {icon: icon});
            },
            onEachFeature: (feature, layer) => {
                // Add popup with station info
                layer.bindPopup(`
                    <strong>${feature.properties.name}</strong><br>
                    ${feature.properties.description || ''}<br>
                    Status: ${feature.properties.is_active ? 'Active' : 'Inactive'}<br>
                    <a href="${this.apiBaseUrl}/stations/${feature.properties.id}/data/">View Data</a>
                `);
                
                // Events
                layer.on({
                    mouseover: function() {
                        this.openPopup();
                        this.info.updateInfo(feature.properties);
                    },
                    mouseout: function() {
                        this.closePopup();
                        this.info.updateInfo();
                    },
                    click: (e) => {
                        this.loadStationData(feature.properties.id);
                    }
                });
            }
        }).addTo(this.map);
        
        // Fit bounds
        if (this.stationData.features && this.stationData.features.length > 0) {
            this.map.fitBounds(this.stationsLayer.getBounds());
        }
    }
    
    loadClimateData() {
        fetch(`${this.apiBaseUrl}/climate-data/recent/`)
            .then(response => response.json())
            .then(data => {
                this.climateData = data;
                this.updateStationMarkers();
            })
            .catch(error => {
                console.error('Error loading climate data:', error);
            });
    }
    
    loadStationData(stationId) {
        fetch(`${this.apiBaseUrl}/stations/${stationId}/data/`)
            .then(response => response.json())
            .then(data => {
                // You could show a chart or detailed info for the selected station
                console.log('Station data:', data);
            })
            .catch(error => {
                console.error(`Error loading data for station ${stationId}:`, error);
            });
    }
    
    updateStationMarkers() {
        // Update markers with climate data
        // This would depend on how you want to visualize the data
    }
}

// Usage:
// const map = new WeatherStationMap('map', '/api');