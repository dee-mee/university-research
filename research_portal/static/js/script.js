// Combine duplicate scroll-to-top functionality
document.addEventListener('DOMContentLoaded', function() {
    // Navbar scroll effect
    const navbar = document.querySelector('.custom-navbar');
    const scrollToTopBtn = document.getElementById('scrollToTopBtn');
    
    // Scroll event handler - handles both navbar and scroll button
    window.onscroll = function() {
        // Navbar effect
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
        
        // Scroll to top button visibility
        if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
            scrollToTopBtn.style.display = 'block';
        } else {
            scrollToTopBtn.style.display = 'none';
        }
    };
    
    // Enhanced dropdown behavior for both hover and click
    const dropdowns = document.querySelectorAll('.dropdown');
    
    // For desktop: hover behavior
    if (window.innerWidth >= 992) {
        dropdowns.forEach(dropdown => {
            dropdown.addEventListener('mouseenter', function() {
                if (window.innerWidth >= 992) {
                    this.querySelector('.dropdown-menu').classList.add('show');
                    this.querySelector('.dropdown-toggle').setAttribute('aria-expanded', 'true');
                }
            });
            
            dropdown.addEventListener('mouseleave', function() {
                if (window.innerWidth >= 992) {
                    this.querySelector('.dropdown-menu').classList.remove('show');
                    this.querySelector('.dropdown-toggle').setAttribute('aria-expanded', 'false');
                }
            });
        });
    }
    
    // For mobile: ensure proper behavior
    const dropdownToggles = document.querySelectorAll('.dropdown-toggle');
    
    dropdownToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            if (window.innerWidth < 992) {
                e.preventDefault();
                const dropdown = this.parentElement;
                const dropdownMenu = dropdown.querySelector('.dropdown-menu');
                
                // Toggle current dropdown
                dropdownMenu.classList.toggle('show');
                this.setAttribute('aria-expanded', 
                    this.getAttribute('aria-expanded') === 'true' ? 'false' : 'true');
            }
        });
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (window.innerWidth < 992 && !e.target.closest('.dropdown')) {
            dropdownToggles.forEach(toggle => {
                toggle.setAttribute('aria-expanded', 'false');
                toggle.nextElementSibling.classList.remove('show');
            });
        }
    });
    
    // Get the projects wrapper element
    const projectsWrapper = document.querySelector('.projects-wrapper');
    
    // Clone the project items for a seamless continuous scroll effect
    if (projectsWrapper) {
        const projectItems = document.querySelectorAll('.project-item');
        
        // Only clone if there are items to clone
        if (projectItems.length > 0) {
            // Clone each project item and append to wrapper for continuous scrolling
            projectItems.forEach(item => {
                const clone = item.cloneNode(true);
                projectsWrapper.appendChild(clone);
            });
        }
        
        // Add pause/play functionality when hovering
        const scrollContainer = document.querySelector('.projects-scroll-container');
        if (scrollContainer) {
            scrollContainer.addEventListener('mouseenter', function() {
                projectsWrapper.style.animationPlayState = 'paused';
            });
            
            scrollContainer.addEventListener('mouseleave', function() {
                projectsWrapper.style.animationPlayState = 'running';
            });
        }
        
        // Adjust animation speed based on screen size
        function adjustScrollSpeed() {
            if (window.innerWidth < 768) {
                projectsWrapper.style.animationDuration = '20s'; // Slower on mobile
            } else {
                projectsWrapper.style.animationDuration = '25s'; // Default speed
            }
        }
        
        // Call initially and on window resize
        adjustScrollSpeed();
        window.addEventListener('resize', adjustScrollSpeed);
    }
    
    // Image slideshow functionality
    const slides = document.querySelectorAll(".slides img");
    if (slides.length > 0) {
        let index = 0;
        
        function showSlides() {
            slides.forEach((slide, i) => {
                slide.style.display = (i === index) ? "block" : "none";
            });
            index = (index + 1) % slides.length;
            setTimeout(showSlides, 2000); // Changed from 500ms to 2000ms for better viewing
        }
        
        showSlides();
    }
});

// Scroll to top function
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}