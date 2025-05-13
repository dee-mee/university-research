/**
 * Sidebar Toggle Functionality
 * This script handles the toggling of the filter sidebar on the map page
 */
document.addEventListener('DOMContentLoaded', function() {
    // Get the sidebar and toggle button elements
    const sidebar = document.getElementById('filter-sidebar');
    const toggleBtn = document.getElementById('toggle-sidebar');
    const sidebarIcon = document.getElementById('sidebar-icon');
    
    // Add click event to toggle button
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function() {
            toggleSidebar();
        });
        
        // Add keyboard shortcut (Escape key)
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                toggleSidebar();
            }
        });
    }
    
    /**
     * Toggle the sidebar visibility
     */
    function toggleSidebar() {
        if (sidebar) {
            sidebar.classList.toggle('hidden');
            
            // Update the icon
            if (sidebarIcon) {
                if (sidebar.classList.contains('hidden')) {
                    sidebarIcon.classList.remove('fa-chevron-left');
                    sidebarIcon.classList.add('fa-chevron-right');
                } else {
                    sidebarIcon.classList.remove('fa-chevron-right');
                    sidebarIcon.classList.add('fa-chevron-left');
                }
            }
            
            // Trigger a resize event to ensure the map adjusts
            setTimeout(function() {
                window.dispatchEvent(new Event('resize'));
            }, 300);
        }
    }
});
