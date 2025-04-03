// Header Scroll Effect
document.addEventListener('DOMContentLoaded', function() {
    const navbar = document.querySelector('.custom-navbar');
    
    if (navbar) {
        let lastScroll = 0;
        
        window.addEventListener('scroll', () => {
            const currentScroll = window.pageYOffset;
            
            if (currentScroll <= 0) {
                navbar.classList.remove('scrolled');
                return;
            }
            
            if (currentScroll > lastScroll && !navbar.classList.contains('scrolled')) {
                // Scrolling down
                navbar.classList.add('scrolled');
            } else if (currentScroll < lastScroll && navbar.classList.contains('scrolled')) {
                // Scrolling up
                navbar.classList.remove('scrolled');
            }
            
            lastScroll = currentScroll;
        });
    }

    // Initialize Bootstrap components
    const toastTrigger = document.getElementById('liveToastBtn');
    const toastLiveExample = document.getElementById('liveToast');
    
    if (toastTrigger && toastLiveExample) {
        const toast = new bootstrap.Toast(toastLiveExample);
        toastTrigger.addEventListener('click', () => {
            toast.show();
        });
    }

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Initialize dropdowns
    const dropdowns = document.querySelectorAll('.dropdown-toggle');
    dropdowns.forEach(dropdown => {
        new bootstrap.Dropdown(dropdown);
    });

    // Handle authentication
    const authBtn = document.getElementById('auth-btn');
    const isAuthenticated = JSON.parse('{{ request.user.is_authenticated|lower }}');
    const csrfToken = '{{ csrf_token }}';

    if (authBtn) {
        authBtn.addEventListener('click', function(event) {
            event.preventDefault();
            
            if (isAuthenticated) {
                // Handle logout
                fetch('/accounts/logout/', {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        window.location.href = '/';
                    }
                });
            } else {
                // Handle login
                window.location.href = '/accounts/login/';
            }
        });
    }
});
