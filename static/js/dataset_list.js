document.addEventListener('DOMContentLoaded', function() {
    // View type switching
    const treeView = document.getElementById('treeView');
    const facetsView = document.getElementById('facetsView');
    const sidebarContent = document.querySelector('.sidebar-content');
    const datasetList = document.querySelector('.dataset-list');

    // View mode handling
    let currentViewMode = 'grid';

    function toggleViewMode(mode) {
        currentViewMode = mode;
        const gridView = document.getElementById('datasetGrid');
        const treeView = document.getElementById('datasetTree');
        const gridBtn = document.querySelector('button[onclick="toggleViewMode(\'grid\')"]');
        const treeBtn = document.querySelector('button[onclick="toggleViewMode(\'tree\')"]');

        if (mode === 'grid') {
            gridView.style.display = 'block';
            treeView.style.display = 'none';
            gridBtn.classList.add('active');
            treeBtn.classList.remove('active');
        } else {
            gridView.style.display = 'none';
            treeView.style.display = 'block';
            gridBtn.classList.remove('active');
            treeBtn.classList.add('active');
            initializeTreeView();
        }
    }

    function initializeTreeView() {
        $('#jstree').jstree({
            'core': {
                'data': [
                    {
                        'text': 'Research Datasets',
                        'state': { 'opened': true },
                        'children': [
                            {
                                'text': 'Floods',
                                'state': { 'opened': true },
                                'children': [
                                    { 'text': 'Short Prediction', 'icon': 'fas fa-file-alt' },
                                    { 'text': '1 Week Prediction', 'icon': 'fas fa-file-alt' }
                                ]
                            },
                            {
                                'text': 'Drought',
                                'state': { 'opened': true },
                                'children': [
                                    { 'text': 'Short Prediction', 'icon': 'fas fa-file-alt' },
                                    { 'text': '1 Week Prediction', 'icon': 'fas fa-file-alt' }
                                ]
                            },
                            {
                                'text': 'Rainfall',
                                'state': { 'opened': true },
                                'children': [
                                    { 'text': 'Short Prediction', 'icon': 'fas fa-file-alt' },
                                    { 'text': '1 Week Prediction', 'icon': 'fas fa-file-alt' }
                                ]
                            },
                            {
                                'text': 'Water Quality',
                                'state': { 'opened': true },
                                'children': [
                                    { 'text': 'Short Prediction', 'icon': 'fas fa-file-alt' },
                                    { 'text': '1 Week Prediction', 'icon': 'fas fa-file-alt' }
                                ]
                            },
                            {
                                'text': 'Carbon Flux',
                                'state': { 'opened': true },
                                'children': [
                                    { 'text': 'Short Prediction', 'icon': 'fas fa-file-alt' },
                                    { 'text': '1 Week Prediction', 'icon': 'fas fa-file-alt' }
                                ]
                            }
                        ]
                    }
                ],
                'themes': {
                    'name': 'default',
                    'responsive': true
                }
            },
            'plugins': ['search', 'state', 'types', 'wholerow']
        });
    }

    function initializeFacetsView() {
        // Create facets structure
        const facets = {
            'Simulation Round': ['JOOUST2a', 'JOOUST2b', 'JOOUST3a', 'JOOUST3b'],
            'Data Type': ['DerivedOutputData', 'OutputData', 'InputData'],
            'Impact Model': ['CLM4.0', 'WATERGAP2-4c', 'Other'],
            'Climate Forcing': ['GSWP3', 'GFDL-ESM4', 'IPSL-CM6A', 'WATCH'],
            'Scenario': ['historical', 'rcp85', 'ssp585'],
            'Time Step': ['daily', 'monthly', 'annual'],
            'Variable': ['dis', 'evap', 'precip']
        };

        // Clear existing content
        sidebarContent.innerHTML = '';

        // Create facets
        Object.entries(facets).forEach(([category, values]) => {
            const facetGroup = document.createElement('div');
            facetGroup.className = 'facet-group mb-3';

            const title = document.createElement('h6');
            title.className = 'facet-title mb-2';
            title.textContent = category;
            facetGroup.appendChild(title);

            values.forEach(value => {
                const facetItem = document.createElement('div');
                facetItem.className = 'form-check';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'form-check-input';
                checkbox.id = `facet-${value}`;

                const label = document.createElement('label');
                label.className = 'form-check-label';
                label.htmlFor = `facet-${value}`;
                label.textContent = value;

                facetItem.appendChild(checkbox);
                facetItem.appendChild(label);
                facetGroup.appendChild(facetItem);
            });

            sidebarContent.appendChild(facetGroup);
        });
    }

    if (treeView && facetsView && sidebarContent) {
        // Initialize tree view by default
        initializeTreeView();

        treeView.addEventListener('change', () => {
            if (treeView.checked) {
                initializeTreeView();
            }
        });

        facetsView.addEventListener('change', () => {
            if (facetsView.checked) {
                initializeFacetsView();
            }
        });
    }

    // Handle dataset selection
    const checkboxes = document.querySelectorAll('.dataset-item input[type="checkbox"]');
    const selectionInfo = document.querySelector('.selection-info');
    
    function updateSelection() {
        const selectedDatasets = document.querySelectorAll('.dataset-item input[type="checkbox"]:checked');
        const count = selectedDatasets.length;
        const totalSize = Array.from(selectedDatasets).reduce((sum, checkbox) => {
            const size = parseInt(checkbox.dataset.size || 0);
            return sum + size;
        }, 0);
        
        if (selectionInfo) {
            selectionInfo.textContent = `You selected ${count} dataset of ${totalSize} B size.`;
        }
    }
    
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateSelection);
    });
    
    // Handle version display options
    const latestVersion = document.getElementById('latestVersion');
    const specificVersion = document.getElementById('specificVersion');
    
    if (latestVersion && specificVersion && datasetList) {
        latestVersion.addEventListener('change', () => {
            document.querySelectorAll('.dataset-version:not(.latest)').forEach(el => {
                el.style.display = 'none';
            });
        });
        
        specificVersion.addEventListener('change', () => {
            document.querySelectorAll('.dataset-version').forEach(el => {
                el.style.display = 'block';
            });
        });
    }
    
    // Handle archived files toggle
    const showArchived = document.getElementById('showArchived');
    
    if (showArchived) {
        showArchived.addEventListener('change', () => {
            document.querySelectorAll('.dataset-item.archived').forEach(el => {
                el.style.display = showArchived.checked ? 'block' : 'none';
            });
        });
    }
    
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => {
        new bootstrap.Tooltip(tooltip);
    });
    
    // Handle dataset actions
    document.querySelectorAll('.btn-link').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const action = this.textContent.trim();
            const datasetId = this.closest('.dataset-item').dataset.id;
            
            switch(action) {
                case 'Attributes':
                    showAttributes(datasetId);
                    break;
                case 'Files':
                    showFiles(datasetId);
                    break;
                case 'Configure download':
                    configureDownload(datasetId);
                    break;
                case 'Download file list':
                    downloadFileList(datasetId);
                    break;
                case 'Download all files':
                    downloadAllFiles(datasetId);
                    break;
            }
        });
    });

    // Initialize view mode on page load
    toggleViewMode('grid');

    // Filter functionality
    function applyFilters() {
        const selectedCategories = Array.from(document.querySelectorAll('.category-filter:checked'))
            .map(checkbox => checkbox.value);
        const selectedLicenses = Array.from(document.querySelectorAll('.license-filter:checked'))
            .map(checkbox => checkbox.value);
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;

        // Get all dataset cards
        const datasetCards = document.querySelectorAll('#datasetGrid .col-md-4');
        
        datasetCards.forEach(card => {
            const categoryId = card.dataset.categoryId;
            const licenseType = card.dataset.licenseType;
            const datasetDate = new Date(card.dataset.date);
            
            let showCard = true;

            // Category filter
            if (selectedCategories.length > 0 && !selectedCategories.includes(categoryId)) {
                showCard = false;
            }

            // License filter
            if (selectedLicenses.length > 0 && !selectedLicenses.includes(licenseType)) {
                showCard = false;
            }

            // Date range filter
            if (startDate) {
                const start = new Date(startDate);
                if (datasetDate < start) {
                    showCard = false;
                }
            }
            if (endDate) {
                const end = new Date(endDate);
                if (datasetDate > end) {
                    showCard = false;
                }
            }

            // Show/hide card based on filters
            card.style.display = showCard ? 'block' : 'none';
        });

        // Update tree view if active
        if (currentViewMode === 'tree') {
            updateTreeView();
        }

        // Show message if no results
        const visibleCards = document.querySelectorAll('#datasetGrid .col-md-4[style="display: block"]');
        const noResultsMessage = document.getElementById('noResultsMessage');
        
        if (visibleCards.length === 0) {
            if (!noResultsMessage) {
                const message = document.createElement('div');
                message.id = 'noResultsMessage';
                message.className = 'col-12 alert alert-info';
                message.innerHTML = `
                    <h4 class="alert-heading">No datasets found</h4>
                    <p>There are currently no datasets matching your filter criteria. Try adjusting your filters.</p>
                `;
                document.getElementById('datasetGrid').appendChild(message);
            }
        } else if (noResultsMessage) {
            noResultsMessage.remove();
        }
    }

    function resetFilters() {
        // Reset category filters
        document.querySelectorAll('.category-filter').forEach(checkbox => {
            checkbox.checked = false;
        });

        // Reset license filters
        document.querySelectorAll('.license-filter').forEach(checkbox => {
            checkbox.checked = false;
        });

        // Reset date range
        document.getElementById('startDate').value = '';
        document.getElementById('endDate').value = '';

        // Show all cards
        document.querySelectorAll('#datasetGrid .col-md-4').forEach(card => {
            card.style.display = 'block';
        });

        // Remove no results message if exists
        const noResultsMessage = document.getElementById('noResultsMessage');
        if (noResultsMessage) {
            noResultsMessage.remove();
        }

        // Update tree view if active
        if (currentViewMode === 'tree') {
            updateTreeView();
        }
    }

    function updateTreeView() {
        // Get filtered dataset IDs
        const visibleCards = document.querySelectorAll('#datasetGrid .col-md-4[style="display: block"]');
        const visibleDatasetIds = Array.from(visibleCards).map(card => card.dataset.id);

        // Update tree view to show only filtered datasets
        $('#jstree').jstree(true).refresh();
    }
}); 