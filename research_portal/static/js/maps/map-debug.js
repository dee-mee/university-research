/**
 * Map Debug Helper
 * This file helps troubleshoot issues with the Weather Station Map
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Map debug helper loaded');
    
    // Check if the map initialization happened
    setTimeout(() => {
        if (window.weatherMap) {
            console.log('Weather map initialized correctly');
        } else {
            console.error('Weather map not initialized. Check for JavaScript errors.');
        }
        
        // Check popup functionality
        testPopupContent();
    }, 3000);
    
    // Function to test popup content rendering
    function testPopupContent() {
        const popupContent = `
            <div class="info-container">
                <h4>Test Station</h4>
                <p>This is a test popup to verify button styling</p>
                <div class="button-container mt-3">
                    <a href="/maps/stations/1/statistics/" 
                       class="btn btn-lg btn-success w-100 mb-2 station-stats-direct-link">
                        <i class="fas fa-chart-bar me-1"></i> Test Statistics Button
                    </a>
                </div>
            </div>
        `;
        
        // Create a temporary debug container
        const debugContainer = document.createElement('div');
        debugContainer.style.position = 'fixed';
        debugContainer.style.right = '20px';
        debugContainer.style.bottom = '20px';
        debugContainer.style.backgroundColor = '#fff';
        debugContainer.style.padding = '10px';
        debugContainer.style.border = '1px solid #ddd';
        debugContainer.style.borderRadius = '5px';
        debugContainer.style.zIndex = '9999';
        debugContainer.style.maxWidth = '300px';
        debugContainer.style.boxShadow = '0 0 15px rgba(0,0,0,0.2)';
        debugContainer.innerHTML = `
            <div>
                <h5>Button Debug</h5>
                <p>Click the button below to test styling:</p>
                ${popupContent}
            </div>
        `;
        
        document.body.appendChild(debugContainer);
        
        // Create a close button
        const closeBtn = document.createElement('button');
        closeBtn.textContent = 'Close';
        closeBtn.className = 'btn btn-sm btn-secondary';
        closeBtn.style.marginTop = '10px';
        closeBtn.onclick = function() {
            document.body.removeChild(debugContainer);
        };
        
        debugContainer.appendChild(closeBtn);
    }
});
