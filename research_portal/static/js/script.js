let index = 0;
const slides = document.querySelectorAll(".slides img");

function showSlides() {
    slides.forEach((slide, i) => {
        slide.style.display = (i === index) ? "block" : "none";
    });
    index = (index + 1) % slides.length;
    setTimeout(showSlides, 1000);
}

showSlides();

// Scroll to Top Button
window.onscroll = function() {scrollFunction()};

function scrollFunction() {
    const scrollToTopBtn = document.getElementById("scrollToTopBtn");
    if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
        scrollToTopBtn.style.display = "block";
    } else {
        scrollToTopBtn.style.display = "none";
    }
}

function scrollToTop() {
    document.body.scrollTop = 0;
    document.documentElement.scrollTop = 0;
}
// Add this to your script.js file to provide additional scrolling controls and functionality

document.addEventListener('DOMContentLoaded', function() {
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
    }
    
    // Adjust animation speed based on screen size
    function adjustScrollSpeed() {
        if (window.innerWidth < 768) {
            if (projectsWrapper) {
                projectsWrapper.style.animationDuration = '20s'; // Slower on mobile
            }
        } else {
            if (projectsWrapper) {
                projectsWrapper.style.animationDuration = '25s'; // Default speed
            }
        }
    }
    
    // Call initially and on window resize
    adjustScrollSpeed();
    window.addEventListener('resize', adjustScrollSpeed);
});