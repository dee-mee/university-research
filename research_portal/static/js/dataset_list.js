document.addEventListener('DOMContentLoaded', function() {
    // View type switching
    const treeView = document.getElementById('treeView');
    const facetsView = document.getElementById('facetsView');
    const sidebarContent = document.querySelector('.sidebar-content');
    const datasetList = document.querySelector('.dataset-list');

    function initializeTreeView() {
        // Create tree structure
        const tree = {
            'JOOUST2a': {
                'DerivedOutputData': {
                    'Research2023': ['GSWP3', 'GFDL-ESM4'],
                    'Other2023': ['GSWP3', 'WATCH']
                },
                'OutputData': {
                    'CLM4.0': ['historical', 'rcp85']
                }
            },
            'JOOUST2b': {
                'OutputData': {
                    'WATERGAP2-4c': ['GFDL-ESM4', 'IPSL-CM6A']
                }
            },
            'JOOUST3a': {},
            'JOOUST3b': {}
        };

        function createTreeNode(key, value) {
            const item = document.createElement('div');
            item.className = 'tree-item';
            
            const content = document.createElement('div');
            content.className = 'tree-content';
            
            const toggle = document.createElement('span');
            toggle.className = 'tree-toggle';
            toggle.textContent = typeof value === 'object' ? '▶' : '•';
            toggle.style.cursor = typeof value === 'object' ? 'pointer' : 'default';
            
            const label = document.createElement('span');
            label.className = 'tree-label';
            label.textContent = key;
            
            content.appendChild(toggle);
            content.appendChild(label);
            item.appendChild(content);
            
            if (typeof value === 'object') {
                const children = document.createElement('div');
                children.className = 'tree-children';
                children.style.display = 'none';
                
                if (Array.isArray(value)) {
                    value.forEach(child => {
                        children.appendChild(createTreeNode(child, null));
                    });
                } else {
                    Object.entries(value).forEach(([childKey, childValue]) => {
                        children.appendChild(createTreeNode(childKey, childValue));
                    });
                }
                
                item.appendChild(children);
                
                toggle.addEventListener('click', () => {
                    const isExpanded = toggle.textContent === '▼';
                    toggle.textContent = isExpanded ? '▶' : '▼';
                    children.style.display = isExpanded ? 'none' : 'block';
                });
            }
            
            return item;
        }

        // Clear existing content
        sidebarContent.innerHTML = '';
        
        // Create and append tree structure
        Object.entries(tree).forEach(([key, value]) => {
            sidebarContent.appendChild(createTreeNode(key, value));
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
}); 