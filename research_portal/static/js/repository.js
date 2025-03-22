document.addEventListener('DOMContentLoaded', function() {
    // Handle search reset
    const resetButtons = document.querySelectorAll('.constraint-tag .remove');
    resetButtons.forEach(button => {
        button.addEventListener('click', function() {
            window.location.href = this.dataset.resetUrl;
        });
    });

    // Handle select all datasets
    const selectAllCheckbox = document.getElementById('select-all');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const datasetCheckboxes = document.querySelectorAll('input[name="dataset"]');
            datasetCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
        });
    }

    // Handle individual dataset selection
    const datasetCheckboxes = document.querySelectorAll('input[name="dataset"]');
    datasetCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const allChecked = Array.from(datasetCheckboxes).every(cb => cb.checked);
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = allChecked;
            }
        });
    });
}); 