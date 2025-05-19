// Waterinfo Sidebar Functionality
document.addEventListener('DOMContentLoaded', function() {
    const dropdowns = document.querySelectorAll('.theme-dropdown');
    // Close all dropdowns by default
    dropdowns.forEach(dropdown => dropdown.classList.remove('active'));
    // Optionally, open the first dropdown by default (remove the next line if you want all closed)
    // if (dropdowns.length > 0) dropdowns[0].classList.add('active');
    dropdowns.forEach(dropdown => {
        const header = dropdown.querySelector('.dropdown-header');
        header.addEventListener('click', function() {
            // Close all dropdowns
            dropdowns.forEach(d => d.classList.remove('active'));
            // Open the clicked dropdown
            dropdown.classList.add('active');
        });
    });
}); 