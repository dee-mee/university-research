/**
 * Station Data Page
 * Handles displaying and downloading weather station data
 */

/**
 * Global variables for date filtering
 */
let globalStationId = null;
let globalStartDate = null;
let globalEndDate = null;
let globalClimateData = [];

/**
 * Initialize the page
 */
document.addEventListener('DOMContentLoaded', function() {
    // Get station ID from URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const stationId = urlParams.get('id');
    globalStationId = stationId;
    
    if (stationId) {
        // Load station data
        loadStationData(stationId);
        
        // Set up download buttons
        document.getElementById('download-json').addEventListener('click', function() {
            downloadData(stationId, 'json');
        });
        
        document.getElementById('download-csv').addEventListener('click', function() {
            downloadData(stationId, 'csv');
        });
        
        // Set up refresh preview button
        document.getElementById('refresh-preview').addEventListener('click', function() {
            updateDataPreview();
        });
        
        // Set badge information
        updateStationBadges(stationId);
        
        // Set up date filter functionality
        setupDateFilter();
    } else {
        console.error('No station ID provided');
        alert('No station ID provided. Please go back to the map and select a station.');
    }
});

/**
 * Load station data from API
 * @param {string} stationId - The ID of the station
 */
function loadStationData(stationId) {
    // First try to load from the API
    fetch(`/api/weather-stations/${stationId}/`)
        .then(response => {
            if (!response.ok) {
                // If API fails, try to use custom data for demo stations
                return loadCustomStationData(stationId);
            }
            return response.json();
        })
        .then(stationData => {
            if (!stationData) {
                showError("Station data not found");
                return;
            }
            
            // Display station info
            displayStationInfo(stationData);
            
            // Construct API URL with date filter if available
            let apiUrl = `/api/climate-data/station/${stationId}/`;
            
            // Add date range parameters if available
            if (globalStartDate && globalEndDate) {
                const startIso = globalStartDate.toISOString();
                const endIso = globalEndDate.toISOString();
                apiUrl += `?start_date=${encodeURIComponent(startIso)}&end_date=${encodeURIComponent(endIso)}`;
            } else {
                // Default to last 72 hours if no date range specified
                apiUrl += '?hours=72';
            }
            
            // Load climate data for this station
            return fetch(apiUrl);
        })
        .then(response => {
            if (!response || !response.ok) {
                // If API fails, use custom climate data
                return loadCustomClimateData(stationId);
            }
            return response.json();
        })
        .then(climateData => {
            if (!climateData) {
                showError("Climate data not found");
                return;
            }
            
            // Store climate data globally
            globalClimateData = climateData;
            
            // Filter data by date range if needed
            const filteredData = filterClimateDataByDate(climateData, globalStartDate, globalEndDate);
            
            // Display climate data
            displayClimateData(filteredData);
            
            // Create charts
            createCharts(filteredData);
            
            // Update data count display
            updateDataCountDisplay(filteredData.length);
        })
        .catch(error => {
            console.error('Error loading data:', error);
            showError("Error loading station data");
        });
}

/**
 * Load custom station data for demo stations
 * @param {string} stationId - The ID of the station
 */
function loadCustomStationData(stationId) {
    // Custom data for demo stations
    const customStations = {
        'jooust-station': {
            id: 'jooust-station',
            name: 'JOOUST Weather Station',
            description: 'Jaramogi Oginga Odinga University of Science and Technology Weather Station',
            latitude: -0.093889,
            longitude: 34.258611,
            altitude: 1200,
            date_installed: '2023-01-15',
            is_active: true
        },
        'kisumu-station': {
            id: 'kisumu-station',
            name: 'Kisumu Weather Station',
            description: 'Kisumu City Weather Monitoring Station',
            latitude: -0.0917,
            longitude: 34.7680,
            altitude: 1150,
            date_installed: '2023-02-20',
            is_active: true
        },
        'siaya-station': {
            id: 'siaya-station',
            name: 'Siaya Weather Station',
            description: 'Siaya County Weather Monitoring Station',
            latitude: -0.0617,
            longitude: 34.2422,
            altitude: 1180,
            date_installed: '2023-03-10',
            is_active: true
        },
        'bondo-station': {
            id: 'bondo-station',
            name: 'Bondo Weather Station',
            description: 'Bondo Regional Climate Research Station',
            latitude: -0.1003,
            longitude: 34.2755,
            altitude: 1220,
            date_installed: '2023-01-05',
            is_active: true
        }
    };
    
    return customStations[stationId];
}

/**
 * Load custom climate data for demo stations
 * @param {string} stationId - The ID of the station
 */
function loadCustomClimateData(stationId) {
    // Generate sample climate data for the past 72 hours
    const climateData = [];
    const now = new Date();
    
    // Base values for each station
    const baseValues = {
        'jooust-station': { temp: 26.5, precip: 12.3, humidity: 68, wind: 3.2 },
        'kisumu-station': { temp: 28.2, precip: 5.7, humidity: 62, wind: 4.1 },
        'siaya-station': { temp: 27.8, precip: 18.5, humidity: 75, wind: 2.8 },
        'bondo-station': { temp: 25.9, precip: 22.1, humidity: 72, wind: 3.5 }
    };
    
    const base = baseValues[stationId] || { temp: 25, precip: 10, humidity: 65, wind: 3 };
    
    // Generate data for the past 72 hours
    for (let i = 72; i >= 0; i--) {
        const date = new Date(now);
        date.setHours(date.getHours() - i);
        
        // Add some random variation
        const tempVariation = (Math.random() * 4) - 2; // -2 to +2
        const precipVariation = (Math.random() * 5) - 1; // -1 to +4
        const humidityVariation = (Math.random() * 10) - 5; // -5 to +5
        const windVariation = (Math.random() * 2) - 1; // -1 to +1
        
        // Create hourly reading
        climateData.push({
            timestamp: date.toISOString(),
            temperature: (base.temp + tempVariation).toFixed(1),
            precipitation: Math.max(0, (base.precip + precipVariation)).toFixed(1),
            humidity: Math.max(0, Math.min(100, (base.humidity + humidityVariation))).toFixed(0),
            wind_speed: Math.max(0, (base.wind + windVariation)).toFixed(1)
        });
    }
    
    return climateData;
}

/**
 * Display station information
 * @param {Object} stationData - The station data
 */
function displayStationInfo(stationData) {
    document.getElementById('station-name').textContent = stationData.name;
    document.getElementById('station-description').textContent = stationData.description;
    document.getElementById('station-location').textContent = `${stationData.latitude}, ${stationData.longitude}`;
    document.getElementById('station-altitude').textContent = stationData.altitude;
    document.getElementById('station-installed').textContent = formatDate(stationData.date_installed);
    document.getElementById('last-updated').textContent = formatDate(new Date().toISOString());
}

/**
 * Display climate data in table
 * @param {Array} climateData - The climate data array
 */
function displayClimateData(climateData) {
    const tableBody = document.getElementById('data-table-body');
    tableBody.innerHTML = '';
    
    // Sort data by timestamp (newest first)
    const sortedData = [...climateData].sort((a, b) => 
        new Date(b.timestamp) - new Date(a.timestamp)
    );
    
    // Display only the most recent 24 entries in the table
    const recentData = sortedData.slice(0, 24);
    
    recentData.forEach(reading => {
        const row = document.createElement('tr');
        
        // Format the values to ensure consistent decimal places
        const temp = parseFloat(reading.temperature).toFixed(1);
        const precip = parseFloat(reading.precipitation).toFixed(1);
        const humidity = parseFloat(reading.humidity).toFixed(0);
        const windSpeed = parseFloat(reading.wind_speed).toFixed(1);
        
        row.innerHTML = `
            <td><strong>${formatDate(reading.timestamp)}</strong></td>
            <td><span class="badge bg-danger text-white p-2">${temp} °C</span></td>
            <td><span class="badge bg-primary text-white p-2">${precip} mm</span></td>
            <td><span class="badge bg-info text-white p-2">${humidity} %</span></td>
            <td><span class="badge bg-success text-white p-2">${windSpeed} m/s</span></td>
        `;
        
        tableBody.appendChild(row);
    });
}

/**
 * Create temperature and precipitation charts
 * @param {Array} climateData - The climate data array
 */
function createCharts(climateData) {
    // Clear any existing charts first
    if (window.temperatureChart) {
        window.temperatureChart.destroy();
    }
    if (window.precipitationChart) {
        window.precipitationChart.destroy();
    }
    
    // Make sure we have data
    if (!climateData || climateData.length === 0) {
        console.error('No climate data available for charts');
        return;
    }
    
    // Sort data by timestamp (oldest first for charts)
    const sortedData = [...climateData].sort((a, b) => 
        new Date(a.timestamp) - new Date(b.timestamp)
    );
    
    // Limit to last 24 entries for better visibility
    const limitedData = sortedData.slice(-24);
    
    // Prepare data for charts
    const labels = limitedData.map(reading => formatTime(reading.timestamp));
    const temperatureData = limitedData.map(reading => parseFloat(reading.temperature));
    const precipitationData = limitedData.map(reading => parseFloat(reading.precipitation));
    
    // Wait for DOM to be fully ready
    setTimeout(() => {
        createTemperatureChart(labels, temperatureData, limitedData);
        createPrecipitationChart(labels, precipitationData, limitedData);
    }, 100);
}

/**
 * Create the temperature chart
 */
function createTemperatureChart(labels, temperatureData, limitedData) {
    // Get the canvas element
    const tempCtx = document.getElementById('temperature-chart');
    if (!tempCtx) {
        console.error('Temperature chart canvas not found');
        return;
    }
    
    // Explicitly set canvas dimensions
    tempCtx.height = 500;
    tempCtx.style.height = '500px';
    tempCtx.parentNode.style.height = '500px';
    
    // Calculate min/max for better y-axis scaling
    const tempMin = Math.min(...temperatureData) - 2;
    const tempMax = Math.max(...temperatureData) + 2;
    
    // Create the chart with specific dimensions
    window.temperatureChart = new Chart(tempCtx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Temperature (°C)',
                data: temperatureData,
                borderColor: 'rgba(255, 99, 132, 1)',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                borderWidth: 2,
                tension: 0.3,
                fill: true,
                pointRadius: 3,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            devicePixelRatio: 1,
            height: 1000,
            layout: {
                padding: {
                    top: 10,
                    right: 10,
                    bottom: 10,
                    left: 10
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        title: function(tooltipItems) {
                            const index = tooltipItems[0].dataIndex;
                            return new Date(limitedData[index].timestamp).toLocaleString();
                        }
                    }
                }
            },
            scales: {
                y: {
                    min: tempMin,
                    max: tempMax,
                    title: {
                        display: true,
                        text: 'Temperature (°C)'
                    },
                    ticks: {
                        font: {
                            size: 11
                        }
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    },
                    ticks: {
                        maxTicksLimit: 6,
                        autoSkip: true,
                        font: {
                            size: 10
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create the precipitation chart
 */
function createPrecipitationChart(labels, precipitationData, limitedData) {
    // Get the canvas element
    const precipCtx = document.getElementById('precipitation-chart');
    if (!precipCtx) {
        console.error('Precipitation chart canvas not found');
        return;
    }
    
    // Explicitly set canvas dimensions
    precipCtx.height = 500;
    precipCtx.style.height = '500px';
    precipCtx.parentNode.style.height = '500px';
    
    // Calculate max for better y-axis scaling
    const precipMax = Math.max(...precipitationData) * 1.2;
    
    // Create the chart with specific dimensions
    window.precipitationChart = new Chart(precipCtx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Precipitation (mm)',
                data: precipitationData,
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            devicePixelRatio: 1,
            height: 1000,
            layout: {
                padding: {
                    top: 10,
                    right: 10,
                    bottom: 10,
                    left: 10
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        title: function(tooltipItems) {
                            const index = tooltipItems[0].dataIndex;
                            return new Date(limitedData[index].timestamp).toLocaleString();
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: precipMax > 0 ? precipMax : 10,
                    title: {
                        display: true,
                        text: 'Precipitation (mm)'
                    },
                    ticks: {
                        font: {
                            size: 11
                        }
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    },
                    ticks: {
                        maxTicksLimit: 6,
                        autoSkip: true,
                        font: {
                            size: 10
                        }
                    }
                }
            }
        }
    });
}

/**
 * Download station data as JSON or CSV
 * @param {string} stationId - The ID of the station
 * @param {string} format - The format to download (json or csv)
 */
function downloadData(stationId, format) {
    // Check if we already have the data in memory
    if (globalClimateData && globalClimateData.length > 0) {
        prepareAndDownloadData(stationId, format);
        return;
    }
    
    // If we don't have data yet, fetch it first
    // First get station data
    const stationPromise = fetch(`/api/weather-stations/${stationId}/`)
        .then(response => {
            if (!response.ok) {
                return loadCustomStationData(stationId);
            }
            return response.json();
        });
    
    // Construct API URL with date filter if available
    let apiUrl = `/api/climate-data/station/${stationId}/`;
    
    // Add date range parameters if available
    if (globalStartDate && globalEndDate) {
        const startIso = globalStartDate.toISOString();
        const endIso = globalEndDate.toISOString();
        apiUrl += `?start_date=${encodeURIComponent(startIso)}&end_date=${encodeURIComponent(endIso)}`;
    } else {
        // Default to last 72 hours if no date range specified
        apiUrl += '?hours=72';
    }
    
    // Then get climate data
    const climatePromise = fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                return loadCustomClimateData(stationId);
            }
            return response.json();
        });
    
    // Process both promises
    Promise.all([stationPromise, climatePromise])
        .then(([stationData, climateData]) => {
            if (!stationData) {
                showError("Station data not found");
                return;
            }
            
            if (!climateData) {
                climateData = [];
            }
            
            // Store data globally
            globalClimateData = climateData;
            
            // Now prepare and download
            prepareAndDownloadData(stationId, format);
        })
        .catch(error => {
            console.error('Error downloading data:', error);
            showError("Error preparing download");
        });
}

/**
 * Prepare and download data in the specified format
 * @param {string} stationId - The ID of the station
 * @param {string} format - The format to download (json or csv)
 */
function prepareAndDownloadData(stationId, format) {
    // Get station data
    let stationData;
    if (isNaN(stationId)) {
        // For custom stations
        stationData = loadCustomStationData(stationId);
    } else {
        // Try to get from API
        fetch(`/api/weather-stations/${stationId}/`)
            .then(response => {
                if (response.ok) {
                    return response.json();
                }
                return loadCustomStationData(stationId);
            })
            .then(data => {
                stationData = data;
                continueDownload();
            })
            .catch(() => {
                stationData = loadCustomStationData(stationId);
                continueDownload();
            });
        return;
    }
    
    // If we already have station data, continue
    if (stationData) {
        continueDownload();
    }
    
    function continueDownload() {
        // Filter data by date range
        const filteredData = filterClimateDataByDate(globalClimateData, globalStartDate, globalEndDate);
        
        if (format === 'json') {
            // Check if metadata should be included
            const includeMetadata = document.getElementById('include-metadata').checked;
            
            let downloadData;
            if (includeMetadata) {
                // Include minimal metadata
                downloadData = {
                    station: {
                        id: stationData.id,
                        name: stationData.name,
                        location: `${stationData.latitude}, ${stationData.longitude}`,
                        altitude: stationData.altitude,
                        date_range: {
                            start: globalStartDate ? globalStartDate.toISOString() : null,
                            end: globalEndDate ? globalEndDate.toISOString() : null
                        }
                    },
                    readings: filteredData.map(reading => ({
                        timestamp: reading.timestamp,
                        temperature: parseFloat(reading.temperature),
                        precipitation: parseFloat(reading.precipitation),
                        humidity: parseFloat(reading.humidity),
                        wind_speed: parseFloat(reading.wind_speed)
                    }))
                };
            } else {
                // Only include the readings
                downloadData = filteredData.map(reading => ({
                    timestamp: reading.timestamp,
                    temperature: parseFloat(reading.temperature),
                    precipitation: parseFloat(reading.precipitation),
                    humidity: parseFloat(reading.humidity),
                    wind_speed: parseFloat(reading.wind_speed)
                }));
            }
            
            downloadJSON(downloadData, `${stationData.name.replace(/\s+/g, '_')}_data.json`);
        } else if (format === 'csv') {
            // For CSV, only include the readings (no metadata)
            const csvData = filteredData.map(reading => ({
                timestamp: reading.timestamp,
                temperature: parseFloat(reading.temperature),
                precipitation: parseFloat(reading.precipitation),
                humidity: parseFloat(reading.humidity),
                wind_speed: parseFloat(reading.wind_speed)
            }));
            
            downloadCSV(csvData, `${stationData.name.replace(/\s+/g, '_')}_data.csv`);
        }
    }
}

/**
 * Download data as JSON
 * @param {Object} data - The data to download
 * @param {string} filename - The filename
 */
function downloadJSON(data, filename) {
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    
    downloadBlob(blob, filename);
}

/**
 * Download data as CSV
 * @param {Array} data - The data array to download
 * @param {string} filename - The filename
 */
function downloadCSV(data, filename) {
    // CSV header
    const header = 'Timestamp,Temperature (°C),Precipitation (mm),Humidity (%),Wind Speed (m/s)\n';
    
    // Convert data to CSV rows
    const rows = data.map(reading => {
        return `"${formatDate(reading.timestamp)}",${reading.temperature},${reading.precipitation},${reading.humidity},${reading.wind_speed}`;
    }).join('\n');
    
    // Combine header and rows
    const csvContent = header + rows;
    const blob = new Blob([csvContent], { type: 'text/csv' });
    
    downloadBlob(blob, filename);
}

/**
 * Download a Blob as a file
 * @param {Blob} blob - The blob to download
 * @param {string} filename - The filename
 */
function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Format a date string
 * @param {string} dateString - The date string to format
 * @returns {string} The formatted date
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

/**
 * Format a time string (for charts)
 * @param {string} dateString - The date string to format
 * @returns {string} The formatted time
 */
function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/**
 * Show an error message
 * @param {string} message - The error message
 */
function showError(message) {
    const container = document.querySelector('.card-body');
    container.innerHTML = `
        <div class="alert alert-danger" role="alert">
            <h4>Error</h4>
            <p>${message}</p>
            <a href="{% url 'map' %}" class="btn btn-primary">Back to Map</a>
        </div>
    `;
}

/**
 * Set up date filter functionality
 */
function setupDateFilter() {
    // Set default dates (last 24 hours)
    setDefaultDates('24h');
    
    // Add event listeners for preset radio buttons
    document.querySelectorAll('input[name="time-preset"]').forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'custom') {
                // Enable custom date inputs
                document.getElementById('start-date').disabled = false;
                document.getElementById('end-date').disabled = false;
                document.getElementById('start-time').disabled = false;
                document.getElementById('end-time').disabled = false;
            } else {
                // Set preset dates and disable custom inputs
                setDefaultDates(this.value);
                document.getElementById('start-date').disabled = true;
                document.getElementById('end-date').disabled = true;
                document.getElementById('start-time').disabled = true;
                document.getElementById('end-time').disabled = true;
            }
        });
    });
    
    // Add event listener for apply filter button
    document.getElementById('apply-filter').addEventListener('click', function() {
        applyDateFilter();
    });
    
    // Initially disable date inputs since we're using a preset
    document.getElementById('start-date').disabled = true;
    document.getElementById('end-date').disabled = true;
    document.getElementById('start-time').disabled = true;
    document.getElementById('end-time').disabled = true;
}

/**
 * Set default dates based on preset
 * @param {string} preset - The preset value (24h, week, month, year, 5years, 10years, all)
 */
function setDefaultDates(preset) {
    const now = new Date();
    let startDate = new Date();
    
    // Calculate start date based on preset
    switch(preset) {
        case '24h':
            startDate.setHours(now.getHours() - 24);
            break;
        case 'week':
            startDate.setDate(now.getDate() - 7);
            break;
        case 'month':
            startDate.setMonth(now.getMonth() - 1);
            break;
        case 'year':
            startDate.setFullYear(now.getFullYear() - 1);
            break;
        case '5years':
            startDate.setFullYear(now.getFullYear() - 5);
            break;
        case '10years':
            startDate.setFullYear(now.getFullYear() - 10);
            break;
        case 'all':
            // Set to a very old date to get all data (e.g., 50 years ago)
            startDate = new Date(1970, 0, 1); // January 1, 1970 (Unix epoch)
            break;
        default:
            startDate.setHours(now.getHours() - 24);
    }
    
    // Format dates for input fields
    const startDateStr = startDate.toISOString().split('T')[0];
    const endDateStr = now.toISOString().split('T')[0];
    
    // Format times for input fields
    const startTimeStr = startDate.toTimeString().slice(0, 5);
    const endTimeStr = now.toTimeString().slice(0, 5);
    
    // Set input values
    document.getElementById('start-date').value = startDateStr;
    document.getElementById('end-date').value = endDateStr;
    document.getElementById('start-time').value = startTimeStr;
    document.getElementById('end-time').value = endTimeStr;
    
    // Store globally
    globalStartDate = startDate;
    globalEndDate = now;
}

/**
 * Apply date filter to data
 */
function applyDateFilter() {
    // Get date range values
    const startDateStr = document.getElementById('start-date').value;
    const endDateStr = document.getElementById('end-date').value;
    const startTimeStr = document.getElementById('start-time').value || '00:00';
    const endTimeStr = document.getElementById('end-time').value || '23:59';
    
    // Create Date objects
    const startDate = new Date(`${startDateStr}T${startTimeStr}:00`);
    const endDate = new Date(`${endDateStr}T${endTimeStr}:00`);
    
    // Validate dates
    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
        alert('Please enter valid dates and times');
        return;
    }
    
    if (startDate > endDate) {
        alert('Start date must be before end date');
        return;
    }
    
    // Store globally
    globalStartDate = startDate;
    globalEndDate = endDate;
    
    // Reload data with new date range
    if (globalStationId) {
        loadStationData(globalStationId);
    }
}

/**
 * Filter climate data by date range
 * @param {Array} climateData - The climate data array
 * @param {Date} startDate - The start date
 * @param {Date} endDate - The end date
 * @returns {Array} The filtered climate data
 */
function filterClimateDataByDate(climateData, startDate, endDate) {
    if (!startDate || !endDate) {
        return climateData;
    }
    
    return climateData.filter(reading => {
        const readingDate = new Date(reading.timestamp);
        return readingDate >= startDate && readingDate <= endDate;
    });
}

/**
 * Update data count display
 * @param {number} count - The number of data points
 */
function updateDataCountDisplay(count) {
    // Add a small info text below the filter button
    const filterForm = document.getElementById('date-filter-form');
    let countDisplay = document.getElementById('data-count-display');
    
    if (!countDisplay) {
        countDisplay = document.createElement('div');
        countDisplay.id = 'data-count-display';
        countDisplay.className = 'mt-3 text-muted small';
        filterForm.appendChild(countDisplay);
    }
    
    // Format date range for display
    let dateRangeText = '';
    if (globalStartDate && globalEndDate) {
        const startStr = globalStartDate.toLocaleString();
        const endStr = globalEndDate.toLocaleString();
        dateRangeText = `from ${startStr} to ${endStr}`;
    }
    
    countDisplay.innerHTML = `<strong>${count}</strong> data points found ${dateRangeText}`;
    
    // Also update the data preview
    updateDataPreview();
}

/**
 * Update data preview table
 */
function updateDataPreview() {
    const previewTableBody = document.getElementById('preview-table-body');
    if (!previewTableBody || !globalClimateData) {
        return;
    }
    
    // Clear existing preview
    previewTableBody.innerHTML = '';
    
    // Filter data by date range
    const filteredData = filterClimateDataByDate(globalClimateData, globalStartDate, globalEndDate);
    
    // Show only first 5 records
    const previewData = filteredData.slice(0, 5);
    
    if (previewData.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="5" class="text-center">No data available for the selected date range</td>';
        previewTableBody.appendChild(row);
        return;
    }
    
    // Add preview rows
    previewData.forEach(reading => {
        const row = document.createElement('tr');
        
        // Format the values to ensure consistent decimal places
        const temp = parseFloat(reading.temperature).toFixed(1);
        const precip = parseFloat(reading.precipitation).toFixed(1);
        const humidity = parseFloat(reading.humidity).toFixed(0);
        const windSpeed = parseFloat(reading.wind_speed).toFixed(1);
        
        row.innerHTML = `
            <td>${formatDate(reading.timestamp)}</td>
            <td>${temp} °C</td>
            <td>${precip} mm</td>
            <td>${humidity} %</td>
            <td>${windSpeed} m/s</td>
        `;
        
        previewTableBody.appendChild(row);
    });
    
    // Add a message if there are more records
    if (filteredData.length > 5) {
        const row = document.createElement('tr');
        row.innerHTML = `<td colspan="5" class="text-center text-muted">... and ${filteredData.length - 5} more records</td>`;
        previewTableBody.appendChild(row);
    }
}

/**
 * Update station badges based on station ID
 * @param {string} stationId - The ID of the station
 */
function updateStationBadges(stationId) {
    // Update breadcrumb
    const breadcrumbElement = document.getElementById('breadcrumb-station-name');
    if (breadcrumbElement) {
        if (isNaN(stationId)) {
            // For custom stations, use the ID to create a readable name
            const stationName = stationId.split('-').map(word => 
                word.charAt(0).toUpperCase() + word.slice(1)
            ).join(' ');
            breadcrumbElement.textContent = stationName;
        } else {
            // For numeric IDs, use a generic name
            breadcrumbElement.textContent = `Station #${stationId}`;
        }
    }
    
    // Set station type badge
    const typeElement = document.getElementById('station-type-badge');
    if (typeElement) {
        if (isNaN(stationId)) {
            typeElement.textContent = 'Custom Station';
            typeElement.classList.remove('bg-info');
            typeElement.classList.add('bg-warning');
        } else {
            typeElement.textContent = 'Monitoring Station';
        }
    }
    
    // Set region badge based on station ID
    const regionElement = document.getElementById('station-region-badge');
    if (regionElement) {
        if (stationId === 'jooust-station' || stationId === '1') {
            regionElement.textContent = 'JOOUST Campus';
        } else if (stationId === 'kisumu-station' || stationId === '2') {
            regionElement.textContent = 'Kisumu County';
        } else if (stationId === 'siaya-station' || stationId === '3') {
            regionElement.textContent = 'Siaya County';
        } else if (stationId === 'bondo-station' || stationId === '4') {
            regionElement.textContent = 'Bondo Region';
        } else {
            regionElement.textContent = 'Lake Victoria Basin';
        }
    }
}
