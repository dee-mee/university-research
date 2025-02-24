let index = 0;
const slides = document.querySelectorAll(".slides img");

function showSlides() {
    slides.forEach((slide, i) => {
        slide.style.display = (i === index) ? "block" : "none";
    });
    index = (index + 1) % slides.length;
    setTimeout(showSlides, 3000);
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
