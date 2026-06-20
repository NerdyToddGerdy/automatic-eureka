// Global state
let tokens = [];
let filteredTokens = [];
let selectedTokenIds = new Set();
let tokensAbortController = null;
let currentFilters = {
    search: '',
    image_type: '',
    species: '',
    class: '',
    theme: '',
    source: '',
    campaign: '',
    sort_by: 'filename',
    sort_order: 'ASC'
};
let tagSchemas = {
    'Token': ['Species', 'Class', 'Source', 'Campaign'],
    'Map': ['Scale', 'Theme', 'Source', 'Campaign'],
    'Handout': ['Type', 'Source', 'Campaign'],
    'Portrait': ['Subject', 'Style', 'Source', 'Campaign'],
    'Scene': ['Location', 'Mood', 'Source', 'Campaign'],
    'Item': ['Rarity', 'Category', 'Attunement', 'Source', 'Campaign']
};
let currentTagDropdowns = {};
let batchTagDropdowns = {};
let uploadImageTagDropdowns = {};
let filterMultiSelects = {
    species: null,
    class: null,
    theme: null,
    source: null,
    campaign: null
};

// Image Type Selection State
let pendingUploadFiles = null;  // Stores files waiting for type selection
let selectedImageType = null;   // Stores the user's type selection

// Wizard State
let wizardState = {
    subfolders: [],         // Selected subfolders from selection step
    currentStep: 0,         // Current wizard step index
    assignments: [],        // Array of {subfolder, imageType, tags, files}
    duplicates: []          // Files with duplicate issues
};

// ============================================================================
// ELECTRON INTEGRATION
// ============================================================================

/**
 * Detect if running in Electron environment
 * Note: This app is Electron-only. Browser mode has been removed.
 */
const isElectron = typeof window.electronAPI !== 'undefined' && window.electronAPI.isElectron;

/**
 * Extract absolute file paths from File objects.
 * Requires Electron - throws error if not available.
 */
function getFilePaths(files) {
  if (!isElectron) {
    throw new Error('This app requires the Electron desktop application. Browser mode is not supported.');
  }

  const paths = [];
  for (const file of files) {
    const path = window.electronAPI.getFileAbsolutePath(file);
    if (path) {
      paths.push({ file, path });
    } else {
      console.warn(`Could not get path for file: ${file.name}`);
      throw new Error(`Could not get path for file: ${file.name}`);
    }
  }
  return paths;
}

/**
 * Update UI to show current mode indicator
 */
function updateModeIndicator() {
  const indicator = document.getElementById('modeIndicator');
  if (!indicator) return;

  indicator.textContent = '📌 Reference Mode (Files stay in place)';
  indicator.className = 'mode-indicator reference-mode';
  indicator.style.display = 'block';
}

// DOM Elements
const tokenGallery = document.getElementById('tokenGallery');
const loadingIndicator = document.getElementById('loadingIndicator');
const emptyState = document.getElementById('emptyState');
const emptyStateTitle = document.getElementById('emptyStateTitle');
const emptyStateMessage = document.getElementById('emptyStateMessage');
const emptyStateClearFiltersBtn = document.getElementById('emptyStateClearFiltersBtn');
const tokenCount = document.getElementById('tokenCount');
const searchInput = document.getElementById('searchInput');
const imageTypeFilter = document.getElementById('imageTypeFilter');
const sortBySelect = document.getElementById('sortBy');
const bulkActionsBar = document.getElementById('bulkActionsBar');
const selectedCount = document.getElementById('selectedCount');
const gridViewBtn = document.getElementById('gridViewBtn');
const listViewBtn = document.getElementById('listViewBtn');

// TagDropdown class for Airtable/Notion-style tag selection
class TagDropdown {
    constructor(container, fieldName, imageType, initialValue = '') {
        this.container = container;
        this.fieldName = fieldName;
        this.imageType = imageType;
        this.value = initialValue;
        this.options = [];
        this.isOpen = false;
        this.filteredOptions = [];

        this.render();
        this.loadOptions();
    }

    render() {
        this.container.innerHTML = `
            <div class="tag-dropdown">
                <div class="tag-dropdown-selected" data-field="${this.fieldName}">
                    <span class="tag-dropdown-value">${this.value || 'Select or type...'}</span>
                    <span class="tag-dropdown-arrow">▼</span>
                </div>
                <div class="tag-dropdown-menu" style="display: none;">
                    <input type="text" class="tag-dropdown-search" placeholder="Search or create new..." />
                    <div class="tag-dropdown-options"></div>
                </div>
            </div>
        `;

        this.selectedEl = this.container.querySelector('.tag-dropdown-selected');
        this.menuEl = this.container.querySelector('.tag-dropdown-menu');
        this.searchEl = this.container.querySelector('.tag-dropdown-search');
        this.optionsEl = this.container.querySelector('.tag-dropdown-options');
        this.valueEl = this.container.querySelector('.tag-dropdown-value');

        this.setupEvents();
    }

    setupEvents() {
        // Toggle dropdown
        this.selectedEl.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggle();
        });

        // Search input
        this.searchEl.addEventListener('input', () => {
            this.filterOptions(this.searchEl.value);
        });

        this.searchEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const searchValue = this.searchEl.value.trim();
                if (searchValue) {
                    this.selectValue(searchValue);
                    this.close();
                }
            } else if (e.key === 'Escape') {
                this.close();
            }
        });

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (this.isOpen && !this.container.contains(e.target)) {
                this.close();
            }
        });
    }

    async loadOptions() {
        try {
            // Global tags: Source and Campaign show all values from entire vault
            const globalTags = ['source', 'campaign'];
            const fieldLower = this.fieldName.toLowerCase();

            let url;
            if (globalTags.includes(fieldLower)) {
                // Use global endpoint for Source and Campaign
                url = `/api/tags/${fieldLower}`;
            } else {
                // Use image-type-specific endpoint for other tags
                url = `/api/tags/${this.imageType}/${fieldLower}`;
            }

            const response = await fetch(url);
            const data = await response.json();

            if (data.success) {
                this.options = data.values || [];
                this.filteredOptions = [...this.options];
                // Re-render if dropdown is already open
                if (this.isOpen) {
                    this.renderOptions();
                }
            }
        } catch (error) {
            console.error('Error loading tag options:', error);
        }
    }

    filterOptions(searchTerm) {
        searchTerm = searchTerm.toLowerCase();
        this.filteredOptions = this.options.filter(opt =>
            opt.toLowerCase().includes(searchTerm)
        );
        this.renderOptions(searchTerm);
    }

    renderOptions(searchTerm = '') {
        this.optionsEl.innerHTML = '';

        // Show filtered existing options
        this.filteredOptions.forEach(option => {
            const optionEl = document.createElement('div');
            optionEl.className = 'tag-dropdown-option';
            optionEl.textContent = option;
            optionEl.addEventListener('click', () => {
                this.selectValue(option);
                this.close();
            });
            this.optionsEl.appendChild(optionEl);
        });

        // Show "Create new" option if search term doesn't match any existing
        if (searchTerm && !this.options.some(opt => opt.toLowerCase() === searchTerm.toLowerCase())) {
            const createEl = document.createElement('div');
            createEl.className = 'tag-dropdown-option tag-dropdown-create';
            createEl.innerHTML = `<strong>Create:</strong> "${searchTerm}"`;
            createEl.addEventListener('click', () => {
                this.selectValue(searchTerm);
                this.close();
            });
            this.optionsEl.appendChild(createEl);
        }

        // Show "Clear" option if there's a value
        if (this.value) {
            const clearEl = document.createElement('div');
            clearEl.className = 'tag-dropdown-option tag-dropdown-clear';
            clearEl.textContent = 'Clear selection';
            clearEl.addEventListener('click', () => {
                this.selectValue('');
                this.close();
            });
            this.optionsEl.appendChild(clearEl);
        }

        // Show empty state
        if (this.filteredOptions.length === 0 && !searchTerm && !this.value) {
            this.optionsEl.innerHTML = '<div class="tag-dropdown-empty">No options available</div>';
        }
    }

    selectValue(value) {
        this.value = value;
        this.valueEl.textContent = value || 'Select or type...';
        this.valueEl.classList.toggle('has-value', !!value);
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    open() {
        this.isOpen = true;
        this.menuEl.style.display = 'block';
        this.searchEl.value = '';
        this.renderOptions();
        this.searchEl.focus();
    }

    close() {
        this.isOpen = false;
        this.menuEl.style.display = 'none';
    }

    getValue() {
        return this.value;
    }

    setValue(value) {
        this.value = value;
        this.valueEl.textContent = value || 'Select or type...';
        this.valueEl.classList.toggle('has-value', !!value);
    }
}

// ============================================================================
// TAG MULTI-SELECT (For multi-value fields like Map Themes)
// ============================================================================

class TagMultiSelect {
    constructor(container, fieldName, imageType, initialValues = []) {
        this.container = container;
        this.fieldName = fieldName;
        this.imageType = imageType;
        this.values = Array.isArray(initialValues) ? initialValues :
                      (initialValues ? [initialValues] : []); // Handle string or array
        this.options = [];
        this.isOpen = false;
        this.filteredOptions = [];
        this.render();
        this.loadOptions();
    }

    render() {
        this.container.innerHTML = `
            <div class="tag-multiselect">
                <div class="tag-multiselect-selected">
                    <div class="tag-pills"></div>
                    <input type="text"
                           class="tag-multiselect-input"
                           placeholder="${this.values.length ? 'Add more...' : 'Select or type...'}"
                    />
                </div>
                <div class="tag-multiselect-dropdown" style="display: none;">
                    <div class="tag-multiselect-options"></div>
                </div>
            </div>
        `;

        this.inputEl = this.container.querySelector('.tag-multiselect-input');
        this.pillsEl = this.container.querySelector('.tag-pills');
        this.dropdownEl = this.container.querySelector('.tag-multiselect-dropdown');
        this.optionsEl = this.container.querySelector('.tag-multiselect-options');

        this.renderPills();
        this.attachEventListeners();
    }

    renderPills() {
        this.pillsEl.innerHTML = this.values.map(value => `
            <span class="tag-pill">
                <span>${this.escapeHtml(value)}</span>
                <button type="button" class="tag-pill-remove" data-value="${this.escapeHtml(value)}">&times;</button>
            </span>
        `).join('');

        // Update input placeholder
        this.inputEl.placeholder = this.values.length ? 'Add more...' : 'Select or type...';
    }

    attachEventListeners() {
        // Input focus/blur
        this.inputEl.addEventListener('focus', () => this.openDropdown());
        this.inputEl.addEventListener('blur', (e) => {
            setTimeout(() => this.closeDropdown(), 200);
        });

        // Input typing (filter options)
        this.inputEl.addEventListener('input', (e) => {
            this.filterOptions(e.target.value);
        });

        // Input enter key (add custom value)
        this.inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const value = this.inputEl.value.trim();
                if (value) {
                    this.addValue(value);
                    this.inputEl.value = '';
                    this.filterOptions('');
                }
            }
        });

        // Remove pill clicks
        this.pillsEl.addEventListener('click', (e) => {
            if (e.target.classList.contains('tag-pill-remove')) {
                const value = e.target.getAttribute('data-value');
                this.removeValue(value);
            }
        });

        // Dropdown option clicks
        this.optionsEl.addEventListener('click', (e) => {
            if (e.target.classList.contains('tag-multiselect-option')) {
                const value = e.target.getAttribute('data-value');
                this.addValue(value);
                this.inputEl.value = '';
                this.inputEl.focus();
                this.filterOptions('');
            }
        });
    }

    async loadOptions() {
        try {
            const fieldLower = this.fieldName.toLowerCase();
            // Use imageType as-is (e.g., "Map" not "map") for the API call
            const response = await fetch(`/api/tags/${this.imageType}/${fieldLower}`);
            const data = await response.json();
            this.options = data.values || [];
            this.filterOptions('');
        } catch (error) {
            console.error(`Failed to load options for ${this.fieldName}:`, error);
            this.options = [];
        }
    }

    filterOptions(query) {
        const lowerQuery = query.toLowerCase();
        this.filteredOptions = this.options
            .filter(opt => !this.values.includes(opt)) // Exclude already selected
            .filter(opt => !query || opt.toLowerCase().includes(lowerQuery));

        this.renderOptions();
    }

    renderOptions() {
        if (this.filteredOptions.length === 0) {
            this.optionsEl.innerHTML = '<div class="tag-multiselect-empty">No options available</div>';
            return;
        }

        this.optionsEl.innerHTML = this.filteredOptions.map(option => `
            <div class="tag-multiselect-option" data-value="${this.escapeHtml(option)}">
                ${this.escapeHtml(option)}
            </div>
        `).join('');
    }

    openDropdown() {
        this.isOpen = true;
        this.dropdownEl.style.display = 'block';
        this.filterOptions(this.inputEl.value);
    }

    closeDropdown() {
        this.isOpen = false;
        this.dropdownEl.style.display = 'none';
    }

    addValue(value) {
        value = value.trim();
        if (!value || this.values.includes(value)) return;

        this.values.push(value);
        this.renderPills();
        this.filterOptions(''); // Refresh to exclude newly added value
    }

    removeValue(value) {
        this.values = this.values.filter(v => v !== value);
        this.renderPills();
        this.filterOptions(''); // Refresh to include removed value
    }

    getValue() {
        return this.values; // Returns array
    }

    setValue(values) {
        this.values = Array.isArray(values) ? values : (values ? [values] : []);
        this.renderPills();
        this.filterOptions('');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// FilterMultiSelect class for multi-value filter inputs
class FilterMultiSelect {
    constructor(container, filterName, options = []) {
        this.container = container;
        this.filterName = filterName;
        this.values = [];
        this.options = options;
        this.isOpen = false;
        this.render();
    }

    render() {
        this.container.innerHTML = `
            <div class="filter-multiselect">
                <div class="filter-multiselect-selected">
                    <div class="filter-pills"></div>
                    <input type="text"
                           class="filter-multiselect-input"
                           placeholder="Select ${this.filterName}..."
                    />
                    <button type="button" class="filter-dropdown-toggle">▼</button>
                </div>
                <div class="filter-multiselect-dropdown" style="display: none;">
                    <div class="filter-multiselect-options"></div>
                </div>
            </div>
        `;

        this.inputEl = this.container.querySelector('.filter-multiselect-input');
        this.pillsEl = this.container.querySelector('.filter-pills');
        this.dropdownEl = this.container.querySelector('.filter-multiselect-dropdown');
        this.optionsEl = this.container.querySelector('.filter-multiselect-options');
        this.toggleBtn = this.container.querySelector('.filter-dropdown-toggle');

        this.renderPills();
        this.renderOptions();
        this.attachEventListeners();
    }

    renderPills() {
        if (this.values.length === 0) {
            this.pillsEl.innerHTML = '';
            this.inputEl.placeholder = `Select ${this.filterName}...`;
        } else {
            this.pillsEl.innerHTML = this.values.map(value => `
                <span class="filter-pill">
                    <span>${this.escapeHtml(value)}</span>
                    <button type="button" class="filter-pill-remove" data-value="${this.escapeHtml(value)}">&times;</button>
                </span>
            `).join('');
            this.inputEl.placeholder = '';
        }
    }

    renderOptions() {
        const availableOptions = this.options.filter(opt => !this.values.includes(opt));

        if (availableOptions.length === 0) {
            this.optionsEl.innerHTML = '<div class="filter-multiselect-empty">No options available</div>';
            return;
        }

        this.optionsEl.innerHTML = availableOptions.map(option => `
            <div class="filter-multiselect-option" data-value="${this.escapeHtml(option)}">
                ${this.escapeHtml(option)}
            </div>
        `).join('');
    }

    attachEventListeners() {
        // Toggle dropdown
        this.toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.isOpen ? this.closeDropdown() : this.openDropdown();
        });

        // Input focus
        this.inputEl.addEventListener('focus', () => this.openDropdown());

        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this.closeDropdown();
            }
        });

        // Remove pill clicks
        this.pillsEl.addEventListener('click', (e) => {
            if (e.target.classList.contains('filter-pill-remove')) {
                const value = e.target.getAttribute('data-value');
                this.removeValue(value);
            }
        });

        // Dropdown option clicks
        this.optionsEl.addEventListener('click', (e) => {
            if (e.target.classList.contains('filter-multiselect-option')) {
                const value = e.target.getAttribute('data-value');
                this.addValue(value);
            }
        });

        // Filter options as user types
        this.inputEl.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            const filteredOptions = this.options
                .filter(opt => !this.values.includes(opt))
                .filter(opt => opt.toLowerCase().includes(query));

            this.optionsEl.innerHTML = filteredOptions.map(option => `
                <div class="filter-multiselect-option" data-value="${this.escapeHtml(option)}">
                    ${this.escapeHtml(option)}
                </div>
            `).join('');
        });
    }

    openDropdown() {
        this.isOpen = true;
        this.dropdownEl.style.display = 'block';
    }

    closeDropdown() {
        this.isOpen = false;
        this.dropdownEl.style.display = 'none';
        this.inputEl.value = '';
        this.renderOptions();
    }

    addValue(value) {
        if (!this.values.includes(value)) {
            this.values.push(value);
            this.renderPills();
            this.renderOptions();
            this.onChange();
        }
    }

    removeValue(value) {
        this.values = this.values.filter(v => v !== value);
        this.renderPills();
        this.renderOptions();
        this.onChange();
    }

    getValues() {
        return this.values;
    }

    setOptions(options) {
        this.options = options;
        this.renderOptions();
    }

    clearValues() {
        this.values = [];
        this.renderPills();
        this.renderOptions();
    }

    onChange() {
        // Trigger filter update
        handleFilterChange();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Lightbox functions for full-size image viewing
function openLightbox(imageSrc) {
    const lightbox = document.getElementById('imageLightbox');
    const lightboxImage = document.getElementById('lightboxImage');

    lightboxImage.src = imageSrc;
    lightbox.style.display = 'flex';

    // Prevent body scroll
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    const lightbox = document.getElementById('imageLightbox');
    lightbox.style.display = 'none';
    document.body.style.overflow = '';
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadTokens();
    loadFilterOptions();
    setupEventListeners();
    setupScrollToTop();
    updateModeIndicator(); // Show reference vs copy mode indicator
});

// Setup event listeners
function setupEventListeners() {
    // Upload button - show file selection modal
    document.getElementById('uploadBtn').addEventListener('click', () => {
        document.getElementById('addFilesModal').style.display = 'flex';
    });

    // Folder import form
    document.getElementById('folderImportForm').addEventListener('submit', handleFolderImport);

    // File input change
    document.getElementById('fileInput').addEventListener('change', handleFileUpload);

    // Setup drag and drop
    setupDragDrop();
    setupFolderDragDrop();

    // Rescan button
    document.getElementById('scanBtn').addEventListener('click', rescanFolder);

    // Stats button
    document.getElementById('statsBtn').addEventListener('click', showStats);
    document.getElementById('manageTagsBtn').addEventListener('click', showTagManagerModal);
    document.getElementById('tagManagerField').addEventListener('change', loadTagManagerValues);

    // Search and filters
    searchInput.addEventListener('input', debounce(handleSearchChange, 300));
    imageTypeFilter.addEventListener('change', handleImageTypeChange);
    sortBySelect.addEventListener('change', handleSortChange);

    // Clear filters
    document.getElementById('clearFiltersBtn').addEventListener('click', clearFilters);
    emptyStateClearFiltersBtn.addEventListener('click', clearFilters);

    // View toggle
    gridViewBtn.addEventListener('click', () => setView('grid'));
    listViewBtn.addEventListener('click', () => setView('list'));

    // Bulk actions
    document.getElementById('bulkEditBtn').addEventListener('click', showBulkEditModal);
    document.getElementById('bulkDeleteBtn').addEventListener('click', bulkDeleteTokens);
    document.getElementById('deselectAllBtn').addEventListener('click', deselectAll);

    // Modal close buttons
    document.querySelectorAll('.modal-close, .modal-close-btn').forEach(btn => {
        btn.addEventListener('click', closeModals);
    });

    // Modal overlays
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', closeModals);
    });

    // Token edit form
    document.getElementById('tokenEditForm').addEventListener('submit', handleTokenUpdate);
    document.getElementById('deleteTokenBtn').addEventListener('click', handleTokenDelete);
    document.getElementById('editImageType').addEventListener('change', handleImageTypeChangeInModal);

    // File path link
    document.getElementById('modalFilePath').addEventListener('click', handleFilePathClick);

    // Show in Finder button
    document.getElementById('showInFinderBtn').addEventListener('click', handleShowInFinder);

    // Bulk edit form
    document.getElementById('bulkEditForm').addEventListener('submit', handleBulkUpdate);

    // Image type selection form (handler defined in showImageTypeModal)
    // Event listener will be attached dynamically when modal is shown

    // Lightbox event listeners
    const modalImage = document.getElementById('modalImage');
    if (modalImage) {
        modalImage.addEventListener('click', () => {
            openLightbox(modalImage.src);
        });
    }

    const lightboxClose = document.querySelector('.lightbox-close');
    if (lightboxClose) {
        lightboxClose.addEventListener('click', closeLightbox);
    }

    const lightboxOverlay = document.querySelector('.lightbox-overlay');
    if (lightboxOverlay) {
        lightboxOverlay.addEventListener('click', closeLightbox);
    }

    // ESC key to close lightbox
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const lightbox = document.getElementById('imageLightbox');
            if (lightbox && lightbox.style.display === 'flex') {
                closeLightbox();
            }
        }
    });
}

// Load tokens from API
async function loadTokens() {
    // Cancel any in-flight request superseded by this one
    if (tokensAbortController) {
        tokensAbortController.abort();
    }
    tokensAbortController = new AbortController();

    showLoading();

    try {
        const params = new URLSearchParams(currentFilters);
        const response = await fetch(`/api/tokens?${params}`, { signal: tokensAbortController.signal });
        const data = await response.json();

        if (data.success) {
            tokens = data.tokens;
            filteredTokens = tokens;
            renderTokens();
            updateTokenCount();
        } else {
            showError('Failed to load tokens');
        }
    } catch (error) {
        if (error.name === 'AbortError') return; // Superseded by a newer request
        showError('Error loading tokens: ' + error.message);
    } finally {
        hideLoading();
    }
}

// Load filter options
async function loadFilterOptions() {
    try {
        // Get current image type selection
        const imageType = currentFilters.image_type;

        // Define all possible filters with their type-specific visibility
        const allFilters = [
            { name: 'species', container: 'speciesFilterContainer', label: 'Species', types: ['Token'] },
            { name: 'class', container: 'classFilterContainer', label: 'Class', types: ['Token'] },
            { name: 'theme', container: 'themeFilterContainer', label: 'Theme', types: ['Map'] },
            { name: 'source', container: 'sourceFilterContainer', label: 'Source', types: [] }, // Always visible
            { name: 'campaign', container: 'campaignFilterContainer', label: 'Campaign', types: [] } // Always visible
        ];

        for (const filter of allFilters) {
            const container = document.getElementById(filter.container);
            if (!container) continue;

            // Determine if this filter should be visible
            const shouldShow = filter.types.length === 0 || // Always show if no type restriction
                               (imageType && filter.types.includes(imageType)); // Show if matches current type

            // Show/hide container
            container.style.display = shouldShow ? 'block' : 'none';

            // Only load data for visible filters
            if (shouldShow) {
                const response = await fetch(`/api/tags/${filter.name}`);
                const data = await response.json();

                if (data.success) {
                    // Create or update filter
                    if (!filterMultiSelects[filter.name]) {
                        filterMultiSelects[filter.name] = new FilterMultiSelect(
                            container,
                            filter.label,
                            data.values || []
                        );
                    } else {
                        // Update existing filter options
                        filterMultiSelects[filter.name].setOptions(data.values || []);
                    }

                    // Populate datalist for bulk edit autocomplete
                    const datalist = document.getElementById(`${filter.name}List`);
                    if (datalist) {
                        datalist.innerHTML = '';
                        (data.values || []).forEach(value => {
                            const opt = document.createElement('option');
                            opt.value = value;
                            datalist.appendChild(opt);
                        });
                    }
                }
            } else {
                // Clear filter values when hidden
                if (filterMultiSelects[filter.name]) {
                    filterMultiSelects[filter.name].clearValues();
                }

                // Still populate datalist for bulk edit autocomplete even when filter is hidden
                const datalist = document.getElementById(`${filter.name}List`);
                if (datalist && datalist.options.length === 0) {
                    const response = await fetch(`/api/tags/${filter.name}`);
                    const data = await response.json();
                    if (data.success) {
                        (data.values || []).forEach(value => {
                            const opt = document.createElement('option');
                            opt.value = value;
                            datalist.appendChild(opt);
                        });
                    }
                }
            }
        }
    } catch (error) {
        console.error('Error loading filter options:', error);
    }
}

// Populate filter dropdown
function populateFilter(filterType, values) {
    const select = document.getElementById(`${filterType}Filter`);
    const datalist = document.getElementById(`${filterType}List`);

    // Clear existing options (except first)
    while (select.options.length > 1) {
        select.remove(1);
    }

    // Add new options
    values.forEach(value => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);

        // Also add to datalist for edit forms
        if (datalist) {
            const datalistOption = document.createElement('option');
            datalistOption.value = value;
            datalist.appendChild(datalistOption);
        }
    });
}

// Whether any search/filter is currently narrowing the image gallery
function hasActiveFilters() {
    return !!(currentFilters.search || currentFilters.image_type || currentFilters.species ||
        currentFilters.class || currentFilters.theme || currentFilters.source || currentFilters.campaign);
}

// Render tokens to the gallery
function renderTokens() {
    tokenGallery.innerHTML = '';

    if (filteredTokens.length === 0) {
        if (hasActiveFilters()) {
            emptyStateTitle.textContent = 'No Matches Found';
            emptyStateMessage.textContent = 'No images match your current search or filters.';
            emptyStateClearFiltersBtn.style.display = 'inline-block';
        } else {
            emptyStateTitle.textContent = 'No Tokens Found';
            emptyStateMessage.textContent = 'Upload some PNG tokens to get started!';
            emptyStateClearFiltersBtn.style.display = 'none';
        }
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';

    filteredTokens.forEach(token => {
        const card = createTokenCard(token);
        tokenGallery.appendChild(card);
    });
}

// Render token tags based on image type
function renderTokenTags(token) {
    const imageType = token.image_type || 'Token';
    const schema = tagSchemas[imageType] || [];

    let tagsHtml = '';

    for (const field of schema) {
        const fieldLower = field.toLowerCase();
        const value = token[fieldLower];

        if (value) {
            tagsHtml += `<span class="tag tag-${fieldLower}">${value}</span>`;
        }
    }

    return tagsHtml;
}

// Create a token card element
function createTokenCard(token) {
    const card = document.createElement('div');
    card.className = 'token-card';
    card.dataset.tokenId = token.id;

    if (selectedTokenIds.has(token.id)) {
        card.classList.add('selected');
    }

    // Add missing class if file is missing
    if (token.is_missing) {
        card.classList.add('missing');
    }

    const displayName = token.name || token.filename;
    const imageType = token.image_type || 'Token';

    // Warning icon for missing files
    const warningIcon = token.is_missing
        ? '<div class="token-warning" title="File not found at original location. Click to repair.">⚠️</div>'
        : '';

    card.innerHTML = `
        <input type="checkbox" class="token-card-checkbox"
               ${selectedTokenIds.has(token.id) ? 'checked' : ''}>
        ${warningIcon}
        <div class="token-image-container">
            <img src="/api/thumbnail/${token.id}" alt="${displayName}" class="token-image"
                 onerror="this.src='/static/img/missing.png'">
            <span class="image-type-badge image-type-${imageType.toLowerCase()}">${imageType}</span>
        </div>
        <div class="token-info">
            <div class="token-name">${displayName}</div>
            <div class="token-tags">
                ${renderTokenTags(token)}
            </div>
        </div>
    `;

    // Checkbox event
    const checkbox = card.querySelector('.token-card-checkbox');
    checkbox.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleTokenSelection(token.id, checkbox.checked);
    });

    // Warning icon click event
    if (token.is_missing) {
        const warningEl = card.querySelector('.token-warning');
        warningEl.addEventListener('click', (e) => {
            e.stopPropagation();
            showRepairModal(token);
        });
    }

    // Card click event (open modal)
    card.addEventListener('click', (e) => {
        if (e.target !== checkbox && !e.target.classList.contains('token-warning')) {
            openTokenModal(token);
        }
    });

    return card;
}

// Toggle token selection
function toggleTokenSelection(tokenId, selected) {
    if (selected) {
        selectedTokenIds.add(tokenId);
    } else {
        selectedTokenIds.delete(tokenId);
    }

    updateBulkActionsBar();
    updateTokenCardSelection(tokenId, selected);
}

// Update token card visual selection
function updateTokenCardSelection(tokenId, selected) {
    const card = document.querySelector(`[data-token-id="${tokenId}"]`);
    if (card) {
        if (selected) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    }
}

// Update bulk actions bar visibility
function updateBulkActionsBar() {
    selectedCount.textContent = selectedTokenIds.size;

    if (selectedTokenIds.size > 0) {
        bulkActionsBar.style.display = 'flex';
    } else {
        bulkActionsBar.style.display = 'none';
    }
}

// Deselect all tokens
function deselectAll() {
    selectedTokenIds.clear();
    document.querySelectorAll('.token-card-checkbox').forEach(cb => {
        cb.checked = false;
    });
    document.querySelectorAll('.token-card').forEach(card => {
        card.classList.remove('selected');
    });
    updateBulkActionsBar();
}

// Render dynamic tag fields based on image type
function renderDynamicTagFields(imageType, token = {}) {
    const schema = tagSchemas[imageType] || [];
    const container = document.getElementById('dynamicTagFields');

    // Clear existing dropdowns
    currentTagDropdowns = {};

    let html = '';

    for (const field of schema) {
        const fieldLower = field.toLowerCase();
        const fieldId = `edit${field.replace(/\s+/g, '')}`;

        html += `
            <div class="form-group">
                <label for="${fieldId}">${field}</label>
                <div id="${fieldId}Container" class="tag-dropdown-container"></div>
            </div>
        `;
    }

    container.innerHTML = html;

    // Initialize TagDropdown or TagMultiSelect for each field
    for (const field of schema) {
        const fieldLower = field.toLowerCase();
        const fieldId = `edit${field.replace(/\s+/g, '')}`;
        const containerId = `${fieldId}Container`;
        const dropdownContainer = document.getElementById(containerId);
        const value = token[fieldLower] || '';

        if (dropdownContainer) {
            // Use TagMultiSelect for Theme on Maps
            if (imageType === 'Map' && field === 'Theme') {
                currentTagDropdowns[field] = new TagMultiSelect(
                    dropdownContainer,
                    field,
                    imageType,
                    value  // Can be string or array
                );
            } else {
                // Use regular TagDropdown for all other fields
                currentTagDropdowns[field] = new TagDropdown(dropdownContainer, field, imageType, value);
            }
        }
    }
}

// Handle image type change in modal
function handleImageTypeChangeInModal() {
    const imageType = document.getElementById('editImageType').value;
    renderDynamicTagFields(imageType);
}

// Open token detail modal
async function openTokenModal(token) {
    const modal = document.getElementById('tokenModal');

    document.getElementById('editTokenId').value = token.id;
    document.getElementById('modalImage').src = `/api/image/${token.id}`;
    document.getElementById('modalTitle').textContent = token.name || token.filename;
    document.getElementById('modalFilename').textContent = token.filename;
    document.getElementById('modalDateAdded').textContent = formatDate(token.date_added);

    document.getElementById('editName').value = token.name || '';
    document.getElementById('editNotes').value = token.notes || '';

    // Set image type and render appropriate fields
    const imageType = token.image_type || 'Token';
    document.getElementById('editImageType').value = imageType;
    renderDynamicTagFields(imageType, token);

    // Fetch and display file path
    try {
        const response = await fetch(`/api/tokens/${token.id}/filepath`);
        const data = await response.json();

        if (data.success) {
            const filePathLink = document.getElementById('modalFilePath');
            const filePathText = document.getElementById('modalFilePathText');

            filePathText.textContent = data.filepath;
            filePathLink.dataset.filepath = data.filepath;

            // Show "Show in Finder" button only in Electron mode
            const showInFinderBtn = document.getElementById('showInFinderBtn');
            if (isElectron && window.electronAPI && window.electronAPI.showItemInFolder) {
                showInFinderBtn.style.display = 'inline-block';
            } else {
                showInFinderBtn.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error fetching file path:', error);
    }

    modal.style.display = 'flex';
}

// Handle token update
async function handleTokenUpdate(e) {
    e.preventDefault();

    const tokenId = parseInt(document.getElementById('editTokenId').value);
    const imageType = document.getElementById('editImageType').value;

    const updates = {
        Name: document.getElementById('editName').value,
        ImageType: imageType,
        Notes: document.getElementById('editNotes').value
    };

    // Collect values from tag dropdowns
    for (const field in currentTagDropdowns) {
        const dropdown = currentTagDropdowns[field];
        updates[field] = dropdown.getValue();
    }

    try {
        const response = await fetch(`/api/tokens/${tokenId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        const data = await response.json();

        if (data.success) {
            closeModals();
            loadTokens();
            loadFilterOptions();
            showSuccess('Token updated successfully');
        } else {
            showError('Failed to update token');
        }
    } catch (error) {
        showError('Error updating token: ' + error.message);
    }
}

// Handle token delete
async function handleTokenDelete() {
    const tokenId = parseInt(document.getElementById('editTokenId').value);

    if (!confirm('Are you sure you want to delete this token? This will delete the file permanently.')) {
        return;
    }

    try {
        const response = await fetch(`/api/tokens/${tokenId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            closeModals();
            loadTokens();
            showSuccess('Token deleted successfully');
        } else {
            showError('Failed to delete token');
        }
    } catch (error) {
        showError('Error deleting token: ' + error.message);
    }
}

// Handle file path link click
async function handleFilePathClick(e) {
    e.preventDefault();

    const filepath = e.currentTarget.dataset.filepath;

    if (!filepath) {
        showError('File path not available');
        return;
    }

    // Copy to clipboard
    try {
        await navigator.clipboard.writeText(filepath);
        showSuccess('File path copied to clipboard!');
    } catch (error) {
        // Fallback for older browsers
        try {
            const textArea = document.createElement('textarea');
            textArea.value = filepath;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            showSuccess('File path copied to clipboard!');
        } catch (fallbackError) {
            showError('Failed to copy to clipboard');
        }
    }

    // Open file location in Finder/Explorer
    // Get the directory path
    const folderPath = filepath.substring(0, filepath.lastIndexOf('/'));
    const fileUrl = `file://${folderPath}`;

    // Try to open the folder
    try {
        window.open(fileUrl, '_blank');
    } catch (error) {
        console.error('Error opening file location:', error);
    }
}

// Handle "Show in Finder" button click
async function handleShowInFinder(e) {
    e.preventDefault();
    e.stopPropagation();

    const filepath = document.getElementById('modalFilePath').dataset.filepath;

    if (!filepath) {
        showError('No file path available');
        return;
    }

    if (!window.electronAPI || !window.electronAPI.showItemInFolder) {
        showError('This feature is only available in desktop mode');
        return;
    }

    try {
        const result = await window.electronAPI.showItemInFolder(filepath);
        if (result.success) {
            showSuccess('Opening file location...');
        } else {
            showError(`Failed to open: ${result.error}`);
        }
    } catch (error) {
        showError(`Error: ${error.message}`);
    }
}

// Show bulk edit modal
function showBulkEditModal() {
    if (selectedTokenIds.size === 0) {
        showError('No images selected');
        return;
    }

    document.getElementById('bulkImageType').value = '';
    document.getElementById('bulkSpecies').value = '';
    document.getElementById('bulkClass').value = '';
    document.getElementById('bulkSource').value = '';
    document.getElementById('bulkCampaign').value = '';

    document.getElementById('bulkEditModal').style.display = 'flex';
}

// Handle bulk update
async function handleBulkUpdate(e) {
    e.preventDefault();

    const updates = {};

    const imageType = document.getElementById('bulkImageType').value;
    const species = document.getElementById('bulkSpecies').value;
    const tokenClass = document.getElementById('bulkClass').value;
    const source = document.getElementById('bulkSource').value;
    const campaign = document.getElementById('bulkCampaign').value;

    if (imageType) updates.ImageType = imageType;
    if (species) updates.Species = species;
    if (tokenClass) updates.Class = tokenClass;
    if (source) updates.Source = source;
    if (campaign) updates.Campaign = campaign;

    if (Object.keys(updates).length === 0) {
        showError('Please enter at least one value to update');
        return;
    }

    try {
        const response = await fetch('/api/tokens/bulk-update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token_ids: Array.from(selectedTokenIds),
                updates: updates
            })
        });

        const data = await response.json();

        if (data.success) {
            closeModals();
            deselectAll();
            loadTokens();
            loadFilterOptions();
            showSuccess(`Updated ${data.results.updated} tokens`);
        } else {
            showError('Failed to update tokens');
        }
    } catch (error) {
        showError('Error updating tokens: ' + error.message);
    }
}

// Bulk delete tokens
async function bulkDeleteTokens() {
    if (selectedTokenIds.size === 0) {
        showError('No images selected');
        return;
    }

    if (!confirm(`Are you sure you want to delete ${selectedTokenIds.size} tokens? This will delete the files permanently.`)) {
        return;
    }

    try {
        const response = await fetch('/api/tokens/bulk-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token_ids: Array.from(selectedTokenIds)
            })
        });

        const data = await response.json();

        if (data.success) {
            deselectAll();
            loadTokens();
            showSuccess(`Deleted ${data.results.deleted} tokens`);
        } else {
            showError('Failed to delete tokens');
        }
    } catch (error) {
        showError('Error deleting tokens: ' + error.message);
    }
}

// Show image type selection modal
function showImageTypeModal(files) {
    return new Promise((resolve, reject) => {
        const modal = document.getElementById('imageTypeModal');
        const form = document.getElementById('imageTypeForm');
        const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-btn');

        // Reset form
        form.reset();

        // Handle form submission
        const handleSubmit = (e) => {
            e.preventDefault();

            const selectedType = form.querySelector('input[name="imageType"]:checked');
            if (selectedType) {
                modal.style.display = 'none';
                cleanup();
                resolve(selectedType.value);
            }
        };

        // Handle cancellation
        const handleCancel = () => {
            modal.style.display = 'none';
            cleanup();
            reject(new Error('User cancelled image type selection'));
        };

        // Cleanup listeners
        const cleanup = () => {
            form.removeEventListener('submit', handleSubmit);
            closeButtons.forEach(btn => btn.removeEventListener('click', handleCancel));
        };

        // Attach listeners
        form.addEventListener('submit', handleSubmit);
        closeButtons.forEach(btn => btn.addEventListener('click', handleCancel));

        // Show modal
        modal.style.display = 'flex';
    });
}

// Render tag input fields for batch upload based on image type
function renderBatchTagFields(imageType, container) {
    const schema = tagSchemas[imageType] || [];
    batchTagDropdowns = {}; // Clear existing dropdowns

    schema.forEach(tagField => {
        const formGroup = document.createElement('div');
        formGroup.className = 'form-group';

        const label = document.createElement('label');
        label.textContent = tagField;

        const dropdownContainer = document.createElement('div');
        dropdownContainer.id = `batch${tagField.replace(/\s+/g, '')}Container`;
        dropdownContainer.className = 'tag-dropdown-container';
        dropdownContainer.dataset.tagField = tagField;

        formGroup.appendChild(label);
        formGroup.appendChild(dropdownContainer);
        container.appendChild(formGroup);

        // Use TagMultiSelect for Theme on Maps
        if (imageType === 'Map' && tagField === 'Theme') {
            batchTagDropdowns[tagField] = new TagMultiSelect(dropdownContainer, tagField, imageType, []);
        } else {
            // Use regular TagDropdown for all other fields
            batchTagDropdowns[tagField] = new TagDropdown(dropdownContainer, tagField, imageType, '');
        }
    });
}

// Build tag fields for simplified image upload modal based on image type
function buildUploadImageTagFields(imageType) {
    const container = document.getElementById('uploadImageDynamicTagFields');
    if (!container) return;

    const schema = tagSchemas[imageType] || [];
    container.innerHTML = '';
    uploadImageTagDropdowns = {};

    schema.forEach(tagField => {
        const formGroup = document.createElement('div');
        formGroup.className = 'form-group';

        const label = document.createElement('label');
        label.textContent = tagField;

        const dropdownContainer = document.createElement('div');
        dropdownContainer.id = `upload${tagField.replace(/\s+/g, '')}Container`;
        dropdownContainer.className = 'tag-dropdown-container';
        dropdownContainer.dataset.tagField = tagField;

        formGroup.appendChild(label);
        formGroup.appendChild(dropdownContainer);
        container.appendChild(formGroup);

        // Use TagMultiSelect for Theme on Maps
        if (imageType === 'Map' && tagField === 'Theme') {
            uploadImageTagDropdowns[tagField] = new TagMultiSelect(dropdownContainer, tagField, imageType, []);
        } else {
            uploadImageTagDropdowns[tagField] = new TagDropdown(dropdownContainer, tagField, imageType, '');
        }
    });
}

// Show batch tag setting modal
function showBatchTagModal(imageType, fileCount) {
    return new Promise((resolve, reject) => {
        const modal = document.getElementById('batchTagModal');
        const form = document.getElementById('batchTagForm');
        const fieldsContainer = document.getElementById('batchDynamicTagFields');
        const fileCountSpan = document.getElementById('batchFileCount');
        const skipBtn = document.getElementById('skipTagsBtn');
        const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-btn');

        // Update file count display
        fileCountSpan.textContent = fileCount;

        // Clear and render tag fields for selected image type
        fieldsContainer.innerHTML = '';
        renderBatchTagFields(imageType, fieldsContainer);

        // Handle form submission (Continue with Tags)
        const handleSubmit = (e) => {
            e.preventDefault();

            // Collect tag values from stored dropdown instances
            const tags = {};
            for (const field in batchTagDropdowns) {
                const dropdown = batchTagDropdowns[field];
                const value = dropdown.getValue();

                // Handle both single values (string) and multiple values (array)
                if (Array.isArray(value) && value.length > 0) {
                    tags[field] = value; // TagMultiSelect returns array
                } else if (typeof value === 'string' && value) {
                    tags[field] = value; // TagDropdown returns string
                }
            }

            modal.style.display = 'none';
            cleanup();
            resolve(tags);  // Return tag object
        };

        // Handle skip tags
        const handleSkip = () => {
            modal.style.display = 'none';
            cleanup();
            resolve({});  // Return empty object to proceed without tags
        };

        // Handle cancellation
        const handleCancel = () => {
            modal.style.display = 'none';
            cleanup();
            reject(new Error('User cancelled batch tag upload'));
        };

        // Cleanup listeners
        const cleanup = () => {
            form.removeEventListener('submit', handleSubmit);
            skipBtn.removeEventListener('click', handleSkip);
            closeButtons.forEach(btn => btn.removeEventListener('click', handleCancel));
        };

        // Attach listeners
        form.addEventListener('submit', handleSubmit);
        skipBtn.addEventListener('click', handleSkip);
        closeButtons.forEach(btn => btn.addEventListener('click', handleCancel));

        // Show modal
        modal.style.display = 'flex';
    });
}

// Handle file upload
async function handleFileUpload(e) {
    const files = Array.from(e.target.files);

    if (files.length === 0) return;

    try {
        // STEP 1: Show image type selector
        const imageType = await showImageTypeModal(files);
        selectedImageType = imageType;

        showLoading();

        // STEP 2: Get file paths (Electron required)
        const filePaths = getFilePaths(files);

        // STEP 3: Check for duplicates
        const duplicateInfo = await checkForDuplicatesByPath(filePaths.map(fp => fp.path));

        // STEP 4: Show batch tag modal
        hideLoading();
        const tags = await showBatchTagModal(imageType, files.length);
        showLoading();

        // STEP 5: Handle duplicates or proceed
        if (duplicateInfo.duplicates.length > 0) {
            hideLoading();
            const userChoices = await showDuplicateConfirmation(
                duplicateInfo.duplicates,
                filePaths
            );

            if (userChoices === null) {
                e.target.value = '';
                selectedImageType = null;
                return;
            }

            showLoading();
            await addFileReferencesWithChoices(filePaths, userChoices, imageType, tags);
        } else {
            // No duplicates
            await addFileReferencesDirectly(filePaths, imageType, tags);
        }

        loadTokens();
        loadFilterOptions();
    } catch (error) {
        if (error.message === 'User cancelled image type selection' ||
            error.message === 'User cancelled batch tag upload') {
            // Silent cancellation
        } else {
            showError('Error processing images: ' + error.message);
        }
    } finally {
        hideLoading();
        e.target.value = '';
        selectedImageType = null;
    }
}

// Rescan folder
async function rescanFolder() {
    showLoading();

    try {
        const response = await fetch('/api/scan', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            const results = data.results;
            showSuccess(`Scan complete: ${results.added} added, ${results.updated} updated, ${results.removed} removed`);
            loadTokens();
            loadFilterOptions();
        } else {
            showError('Failed to scan folder');
        }
    } catch (error) {
        showError('Error scanning folder: ' + error.message);
    } finally {
        hideLoading();
    }
}

// Show stats
async function showStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        if (data.success) {
            const stats = data.stats;
            const statsContent = document.getElementById('statsContent');

            statsContent.innerHTML = `
                <div class="total-stat">${stats.total_tokens}</div>
                <p style="text-align: center; color: var(--text-secondary); margin-bottom: 30px;">Total Images</p>

                ${renderStatSection('Species', stats.species)}
                ${renderStatSection('Classes', stats.classes)}
                ${renderStatSection('Sources', stats.sources)}
                ${renderStatSection('Campaigns', stats.campaigns)}
            `;

            document.getElementById('statsModal').style.display = 'flex';
        } else {
            showError('Failed to load stats');
        }
    } catch (error) {
        showError('Error loading stats: ' + error.message);
    }
}

// Render stat section
function renderStatSection(title, data) {
    if (Object.keys(data).length === 0) return '';

    const items = Object.entries(data)
        .map(([label, value]) => `
            <div class="stat-item">
                <span class="stat-label">${label}</span>
                <span class="stat-value">${value}</span>
            </div>
        `).join('');

    return `
        <div class="stat-section">
            <h3>${title}</h3>
            ${items}
        </div>
    `;
}

// Tag Manager
async function showTagManagerModal() {
    document.getElementById('tagManagerModal').style.display = 'flex';
    await loadTagManagerValues();
}

async function loadTagManagerValues() {
    const field = document.getElementById('tagManagerField').value;
    const listEl = document.getElementById('tagManagerList');
    listEl.innerHTML = '<p class="modal-subtitle">Loading...</p>';

    try {
        const response = await fetch(`/api/tags/${field}/manage`);
        const data = await response.json();

        if (!data.success || data.values.length === 0) {
            listEl.innerHTML = '<p class="modal-subtitle">No values found for this field.</p>';
            return;
        }

        const rows = data.values.map(({value, count}) => `
            <tr data-value="${escapeHtml(value)}">
                <td class="tag-manager-value">${escapeHtml(value)}</td>
                <td class="tag-manager-count">${count}</td>
                <td>
                    <button class="btn btn-small tag-rename-btn" data-value="${escapeHtml(value)}">Rename</button>
                </td>
            </tr>
            <tr class="tag-rename-row" data-for="${escapeHtml(value)}" style="display:none;">
                <td colspan="3">
                    <div class="tag-rename-form">
                        <input type="text" class="form-input tag-rename-input" value="${escapeHtml(value)}" placeholder="New value" />
                        <button class="btn btn-primary btn-small tag-rename-save" data-old="${escapeHtml(value)}">Save</button>
                        <button class="btn btn-secondary btn-small tag-rename-cancel">Cancel</button>
                    </div>
                </td>
            </tr>
        `).join('');

        listEl.innerHTML = `
            <table class="tag-manager-table">
                <thead>
                    <tr>
                        <th>Value</th>
                        <th>Tokens</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;

        listEl.querySelectorAll('.tag-rename-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const renameRow = listEl.querySelector(`.tag-rename-row[data-for="${btn.dataset.value}"]`);
                renameRow.style.display = renameRow.style.display === 'none' ? '' : 'none';
            });
        });

        listEl.querySelectorAll('.tag-rename-cancel').forEach(btn => {
            btn.addEventListener('click', () => {
                btn.closest('.tag-rename-row').style.display = 'none';
            });
        });

        listEl.querySelectorAll('.tag-rename-save').forEach(btn => {
            btn.addEventListener('click', () => executeTagRename(btn));
        });

    } catch (error) {
        listEl.innerHTML = `<p class="modal-subtitle">Error loading tags: ${error.message}</p>`;
    }
}

async function executeTagRename(btn) {
    const field = document.getElementById('tagManagerField').value;
    const oldVal = btn.dataset.old;
    const newVal = btn.closest('.tag-rename-form').querySelector('.tag-rename-input').value.trim();

    if (!newVal) { showError('New value cannot be empty'); return; }
    if (newVal === oldVal) { showError('New value is the same as the old value'); return; }

    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
        const response = await fetch(`/api/tags/${field}/rename`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from: oldVal, to: newVal })
        });
        const data = await response.json();

        if (data.success) {
            const s = data.updated !== 1 ? 's' : '';
            showSuccess(`Renamed "${oldVal}" → "${newVal}" on ${data.updated} token${s}`);
            if (data.errors > 0) showError(`${data.errors} PNG file(s) could not be updated`);
            await loadTagManagerValues();
            loadFilterOptions();
            loadTokens();
        } else {
            showError(data.error || 'Failed to rename tag');
            btn.disabled = false;
            btn.textContent = 'Save';
        }
    } catch (error) {
        showError('Error: ' + error.message);
        btn.disabled = false;
        btn.textContent = 'Save';
    }
}

// Handle search change
function handleSearchChange() {
    currentFilters.search = searchInput.value;
    loadTokens();
}

// Handle image type filter change
function handleImageTypeChange() {
    currentFilters.image_type = imageTypeFilter.value;
    loadTokens();
    loadFilterOptions(); // Reload filter options based on selected image type
}

// Handle filter change
function handleFilterChange() {
    // Collect multi-select filter values
    currentFilters.species = filterMultiSelects.species ? filterMultiSelects.species.getValues().join(',') : '';
    currentFilters.class = filterMultiSelects.class ? filterMultiSelects.class.getValues().join(',') : '';
    currentFilters.theme = filterMultiSelects.theme ? filterMultiSelects.theme.getValues().join(',') : '';
    currentFilters.source = filterMultiSelects.source ? filterMultiSelects.source.getValues().join(',') : '';
    currentFilters.campaign = filterMultiSelects.campaign ? filterMultiSelects.campaign.getValues().join(',') : '';
    loadTokens();
}

// Handle sort change
function handleSortChange() {
    currentFilters.sort_by = sortBySelect.value;
    loadTokens();
}

// Clear all filters
function clearFilters() {
    searchInput.value = '';
    imageTypeFilter.value = '';
    sortBySelect.value = 'filename';

    // Clear multi-select filters
    for (const filterName in filterMultiSelects) {
        if (filterMultiSelects[filterName]) {
            filterMultiSelects[filterName].clearValues();
        }
    }

    currentFilters = {
        search: '',
        image_type: '',
        species: '',
        class: '',
        theme: '',
        source: '',
        campaign: '',
        sortBy: 'filename',
        sortOrder: 'ASC'
    };

    loadTokens();
    loadFilterOptions();
}

// Set view mode
function setView(view) {
    if (view === 'grid') {
        tokenGallery.classList.remove('list-view');
        tokenGallery.classList.add('grid-view');
        gridViewBtn.classList.add('active');
        listViewBtn.classList.remove('active');
    } else {
        tokenGallery.classList.remove('grid-view');
        tokenGallery.classList.add('list-view');
        listViewBtn.classList.add('active');
        gridViewBtn.classList.remove('active');
    }
}

// Close all modals
function closeModals() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.style.display = 'none';
    });
}

// Update token count display
function updateTokenCount() {
    tokenCount.textContent = `${filteredTokens.length} image${filteredTokens.length !== 1 ? 's' : ''}`;
}

// Show loading indicator
function showLoading() {
    loadingIndicator.style.display = 'flex';
}

// Hide loading indicator
function hideLoading() {
    loadingIndicator.style.display = 'none';
}

// Show success message
function showSuccess(message) {
    showNotification(message, 'success');
}

// Show error message
function showError(message) {
    showNotification(message, 'error');
}

// Format date
function formatDate(dateString) {
    if (!dateString) return 'N/A';

    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Duplicate Detection Functions

// Show duplicate confirmation modal and return user choices
async function showDuplicateConfirmation(duplicates, files) {
    return new Promise((resolve) => {
        const modal = document.getElementById('duplicateModal');
        const duplicateList = document.getElementById('duplicateList');
        const confirmBtn = document.getElementById('confirmDuplicatesBtn');
        const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-btn');

        // Build duplicate items
        duplicateList.innerHTML = '';
        const userChoices = {};

        duplicates.forEach((dup, index) => {
            const hasDuplicate = dup.content_duplicate || dup.name_collision;
            if (!hasDuplicate) return;

            const itemDiv = document.createElement('div');
            const duplicateType = dup.content_duplicate ? 'has-content-duplicate' : 'has-name-collision';
            itemDiv.className = `duplicate-item ${duplicateType}`;

            const warningType = dup.content_duplicate ? 'content' : 'name';
            const warningIcon = dup.content_duplicate ? '⛔' : '⚠️';
            const warningText = dup.content_duplicate
                ? 'Same content already exists'
                : 'File with same name already exists';
            const warningClass = dup.content_duplicate ? '' : 'warning-name';

            const existing = dup.content_duplicate || dup.name_collision;

            itemDiv.innerHTML = `
                <div class="duplicate-thumbnails">
                    <div>
                        <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">New File</div>
                        <div style="width: 80px; height: 80px; background: var(--bg-light); border: 2px solid var(--gold); border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 12px; color: var(--text-secondary); text-align: center; padding: 5px;">
                            ${dup.filename}
                        </div>
                    </div>
                </div>
                <div class="duplicate-info">
                    <h4>${dup.filename}</h4>
                    <div class="duplicate-warning ${warningClass}">
                        <span class="duplicate-warning-icon">${warningIcon}</span>
                        <span>${warningText}</span>
                    </div>
                    <div class="duplicate-existing-info">
                        Existing: <strong>${existing.name || existing.filename}</strong>
                        ${existing.species ? `(${existing.species})` : ''}
                        ${existing.class ? `[${existing.class}]` : ''}
                    </div>
                </div>
                <div class="duplicate-actions">
                    <label class="duplicate-action-radio selected" data-index="${index}">
                        <input type="radio" name="action_${index}" value="skip" checked />
                        <span class="duplicate-action-label">Skip</span>
                    </label>
                    <label class="duplicate-action-radio" data-index="${index}">
                        <input type="radio" name="action_${index}" value="rename" />
                        <span class="duplicate-action-label">Rename</span>
                    </label>
                    <label class="duplicate-action-radio" data-index="${index}">
                        <input type="radio" name="action_${index}" value="overwrite" />
                        <span class="duplicate-action-label">Overwrite</span>
                    </label>
                </div>
                <div class="rename-options" id="renameOptions_${index}" style="display: none;">
                    <div class="rename-type-selector">
                        <label class="rename-type-option">
                            <input type="radio" name="renameType_${index}" value="auto" checked />
                            <span>Auto-number (${dup.filename.replace(/\.[^/.]+$/, '')}_1${dup.filename.match(/\.[^/.]+$/)?.[0] || ''})</span>
                        </label>
                        <label class="rename-type-option">
                            <input type="radio" name="renameType_${index}" value="manual" />
                            <span>Enter custom name</span>
                        </label>
                    </div>
                    <div class="manual-rename-input" id="manualRenameInput_${index}" style="display: none;">
                        <input type="text" class="form-input" id="customName_${index}" placeholder="Enter new filename (without extension)" />
                        <small>Extension ${dup.filename.match(/\.[^/.]+$/)?.[0] || ''} will be added automatically</small>
                    </div>
                </div>
            `;

            duplicateList.appendChild(itemDiv);
            userChoices[dup.filename] = 'skip'; // Default action
        });

        // Setup radio button handlers
        const radioLabels = duplicateList.querySelectorAll('.duplicate-action-radio');
        radioLabels.forEach(label => {
            label.addEventListener('click', function() {
                const index = this.dataset.index;
                const actionName = `action_${index}`;

                // Remove selected class from all options for this duplicate
                duplicateList.querySelectorAll(`[data-index="${index}"]`).forEach(l => {
                    l.classList.remove('selected');
                });

                // Add selected class to clicked option
                this.classList.add('selected');

                // Update user choices
                const radio = this.querySelector('input[type="radio"]');
                const filename = duplicates[index].filename;
                const renameOptions = document.getElementById(`renameOptions_${index}`);

                if (radio.value === 'rename') {
                    // Show rename options
                    if (renameOptions) renameOptions.style.display = 'block';

                    // Set default rename choice
                    userChoices[filename] = {
                        action: 'rename',
                        renameType: 'auto',
                        customName: ''
                    };
                } else {
                    // Hide rename options
                    if (renameOptions) renameOptions.style.display = 'none';

                    // Simple action (skip or overwrite)
                    userChoices[filename] = radio.value;
                }
            });
        });

        // Setup rename type handlers
        duplicates.forEach((dup, index) => {
            const renameTypeRadios = duplicateList.querySelectorAll(`input[name="renameType_${index}"]`);
            const manualInput = document.getElementById(`manualRenameInput_${index}`);
            const customNameInput = document.getElementById(`customName_${index}`);

            renameTypeRadios.forEach(radio => {
                radio.addEventListener('change', function() {
                    const filename = dup.filename;

                    if (this.value === 'manual') {
                        // Show manual input
                        if (manualInput) manualInput.style.display = 'block';

                        // Update user choice
                        if (typeof userChoices[filename] === 'object') {
                            userChoices[filename].renameType = 'manual';
                        }
                    } else {
                        // Hide manual input
                        if (manualInput) manualInput.style.display = 'none';

                        // Update user choice
                        if (typeof userChoices[filename] === 'object') {
                            userChoices[filename].renameType = 'auto';
                            userChoices[filename].customName = '';
                        }
                    }
                });
            });

            // Listen for custom name input
            if (customNameInput) {
                customNameInput.addEventListener('input', function() {
                    const filename = dup.filename;
                    if (typeof userChoices[filename] === 'object') {
                        userChoices[filename].customName = this.value.trim();
                    }
                });
            }
        });

        // Confirm button
        const handleConfirm = () => {
            modal.style.display = 'none';
            resolve(userChoices);
            cleanup();
        };

        // Cancel buttons
        const handleCancel = () => {
            modal.style.display = 'none';
            resolve(null);
            cleanup();
        };

        const cleanup = () => {
            confirmBtn.removeEventListener('click', handleConfirm);
            closeButtons.forEach(btn => btn.removeEventListener('click', handleCancel));
        };

        confirmBtn.addEventListener('click', handleConfirm);
        closeButtons.forEach(btn => btn.addEventListener('click', handleCancel));

        // Show modal
        modal.style.display = 'flex';
    });
}

// ============================================================================
// REFERENCE MODE FUNCTIONS (Electron-only)
// ============================================================================

/**
 * Check for duplicates by file path (reference mode)
 */
async function checkForDuplicatesByPath(filepaths) {
    const response = await fetch('/api/tokens/check-duplicates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepaths })
    });

    if (!response.ok) {
        throw new Error('Failed to check for duplicates');
    }

    return await response.json();
}

/**
 * Add file references directly (no duplicates)
 */
async function addFileReferencesDirectly(filePaths, imageType, tags = {}) {
    const results = { added: 0, errors: 0, error_files: [] };

    for (const { file, path } of filePaths) {
        try {
            const response = await fetch('/api/tokens/add-reference', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filepath: path,
                    image_type: imageType,
                    ...tags
                })
            });

            const data = await response.json();

            if (data.success) {
                results.added++;
            } else {
                results.errors++;
                results.error_files.push(file.name);
            }
        } catch (error) {
            results.errors++;
            results.error_files.push(file.name);
            console.error(`Error adding reference for ${file.name}:`, error);
        }
    }

    if (results.added > 0) {
        showSuccess(`Referenced ${results.added} images in place`);
    }
    if (results.errors > 0) {
        showError(`Failed to reference ${results.errors} images: ${results.error_files.join(', ')}`);
    }
}

/**
 * Add file references with user choices for duplicates
 */
async function addFileReferencesWithChoices(filePaths, userChoices, imageType, tags = {}) {
    const results = { added: 0, skipped: 0, overwritten: 0, errors: 0 };

    for (const { file, path } of filePaths) {
        const choice = userChoices[file.name];

        if (choice === 'skip') {
            results.skipped++;
            continue;
        }

        try {
            const overwrite = choice === 'overwrite';

            const response = await fetch('/api/tokens/add-reference', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filepath: path,
                    image_type: imageType,
                    overwrite_existing: overwrite,
                    ...tags
                })
            });

            const data = await response.json();

            if (data.success) {
                if (overwrite) {
                    results.overwritten++;
                } else {
                    results.added++;
                }
            } else {
                results.errors++;
            }
        } catch (error) {
            results.errors++;
            console.error(`Error adding reference for ${file.name}:`, error);
        }
    }

    // Show results
    let message = [];
    if (results.added > 0) message.push(`${results.added} added`);
    if (results.overwritten > 0) message.push(`${results.overwritten} overwritten`);
    if (results.skipped > 0) message.push(`${results.skipped} skipped`);

    if (message.length > 0) {
        showSuccess(`Referenced in place: ${message.join(', ')}`);
    }
    if (results.errors > 0) {
        showError(`${results.errors} files had errors`);
    }
}

// Drag and Drop Setup
function setupDragDrop() {
    const dropZone = document.getElementById('dragDropZone');

    if (!dropZone) return;

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop zone when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drag-over');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drag-over');
        }, false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', handleDrop, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

async function handleDrop(e) {
    const dt = e.dataTransfer;

    // Reject folders (direct user to Import Folder feature)
    if (dt.items && dt.items.length > 0) {
        for (let i = 0; i < dt.items.length; i++) {
            const item = dt.items[i];
            if (item.kind === 'file') {
                const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
                if (entry && entry.isDirectory) {
                    showError('To import folders, please use the "Import Folder" button.\n\nOn Mac: Right-click folder → Hold Option → "Copy as Pathname"');
                    return;
                }
            }
        }
    }

    // Filter for image files only
    const files = Array.from(dt.files).filter(f => {
        const name = f.name.toLowerCase();
        return name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg');
    });

    if (files.length === 0) {
        showError('No image files found. Please drop PNG or JPEG files.\n\nFor folders, use "Import Folder" instead.');
        return;
    }

    // Close add files modal if open
    document.getElementById('addFilesModal').style.display = 'none';

    try {
        // STEP 1: Show image type selector
        const imageType = await showImageTypeModal(files);
        selectedImageType = imageType;

        showLoading();

        // STEP 2: Get file paths (Electron required)
        const filePaths = getFilePaths(files);

        // STEP 3: Check for duplicates
        const duplicateInfo = await checkForDuplicatesByPath(filePaths.map(fp => fp.path));

        // STEP 4: Show batch tag modal
        hideLoading();
        const tags = await showBatchTagModal(imageType, files.length);
        showLoading();

        // STEP 5: Handle duplicates or proceed
        if (duplicateInfo.duplicates.length > 0) {
            hideLoading();
            const userChoices = await showDuplicateConfirmation(
                duplicateInfo.duplicates,
                filePaths
            );

            if (userChoices === null) {
                selectedImageType = null;
                return;
            }

            showLoading();
            await addFileReferencesWithChoices(filePaths, userChoices, imageType, tags);
        } else {
            await addFileReferencesDirectly(filePaths, imageType, tags);
        }

        loadTokens();
        loadFilterOptions();
    } catch (error) {
        if (error.message === 'User cancelled image type selection' ||
            error.message === 'User cancelled batch tag upload') {
            // Silent cancellation
        } else {
            showError('Error processing files: ' + error.message);
        }
    } finally {
        hideLoading();
        selectedImageType = null;
    }
}

// Handle folder import
async function handleFolderImport(e) {
    e.preventDefault();

    const folderPath = document.getElementById('folderPathInput').value.trim();
    const recursive = document.getElementById('recursiveCheckbox').checked;

    if (!folderPath) {
        showError('Please enter a folder path');
        return;
    }

    // Close folder modal
    document.getElementById('folderImportModal').style.display = 'none';

    try {
        showLoading();

        // Scan folder with subfolder grouping enabled if recursive
        const response = await fetch('/api/tokens/scan-folder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                folder_path: folderPath,
                recursive: recursive,
                group_by_subfolder: recursive  // Enable grouping only if recursive
            })
        });

        const data = await response.json();

        if (!data.success) {
            showError(data.error || 'Failed to scan folder');
            return;
        }

        hideLoading();

        // Check if we got subfolder groups
        if (data.grouped_by_subfolder && data.subfolders && data.subfolders.length > 1) {
            // Show subfolder selection UI
            const selectedSubfolders = await showSubfolderSelectionModal(
                data.subfolders,
                data.folder
            );

            if (selectedSubfolders.length === 0) {
                showSuccess('No subfolders selected');
                return;
            }

            // Start wizard for selected subfolders
            await startSubfolderWizard(selectedSubfolders);

        } else {
            // Fallback to old behavior for non-grouped results or single subfolder
            const results = data.results || (data.subfolders && data.subfolders.length === 1 ? data.subfolders[0].files : []);

            if (results.length === 0) {
                showSuccess('No PNG files found in the specified folder');
                document.getElementById('folderPathInput').value = '';
                return;
            }

            // Use original single-batch workflow
            await handleLegacyFolderImport(results);
        }

        // Clear form
        document.getElementById('folderPathInput').value = '';

    } catch (error) {
        if (error.message === 'User cancelled subfolder selection' ||
            error.message === 'User cancelled wizard' ||
            error.message === 'User cancelled image type selection' ||
            error.message === 'User cancelled batch tag upload') {
            // Silent cancellation
        } else {
            showError('Error scanning folder: ' + error.message);
        }
    } finally {
        hideLoading();
        selectedImageType = null;
    }
}

// Legacy single-batch import (for backwards compatibility)
async function handleLegacyFolderImport(results) {
    showLoading();

    // Original workflow: single image type and tags for all files
    const imageType = await showImageTypeModal(results);
    selectedImageType = imageType;
    hideLoading();

    const tags = await showBatchTagModal(imageType, results.length);
    showLoading();

    const filesWithDuplicates = results.filter(r => r.content_duplicate || r.name_collision);

    if (filesWithDuplicates.length > 0) {
        hideLoading();
        const userChoices = await showFolderScanDuplicateConfirmation(results);

        if (userChoices === null) {
            return;
        }

        showLoading();
        await addScannedFilesWithChoices(results, userChoices, imageType, tags);
    } else {
        await addScannedFilesDirectly(results, imageType, tags);
    }

    loadTokens();
    loadFilterOptions();
}

// Show duplicate confirmation for folder scan results
async function showFolderScanDuplicateConfirmation(results) {
    // Filter to only files with duplicates
    const duplicates = results
        .filter(r => r.content_duplicate || r.name_collision)
        .map(r => ({
            filename: r.filepath.split('/').pop(),
            filepath: r.filepath,
            hash: r.hash,
            content_duplicate: r.content_duplicate,
            name_collision: r.name_collision
        }));

    return await showDuplicateConfirmation(duplicates, []);
}

// Add scanned files directly (no duplicates)
async function addScannedFilesDirectly(results, imageType, tags = {}) {
    let addedCount = 0;

    for (const result of results) {
        try {
            const response = await fetch('/api/tokens/add-reference', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    filepath: result.filepath,
                    overwrite_existing: false,
                    image_type: imageType,  // Add image type
                    ...tags  // Add tag values
                })
            });

            const data = await response.json();
            if (data.success) {
                addedCount++;
            }
        } catch (error) {
            console.error(`Error adding ${result.filepath}:`, error);
        }
    }

    showSuccess(`Added ${addedCount} file references to vault`);
}

// Add scanned files with user choices
async function addScannedFilesWithChoices(results, userChoices, imageType, tags = {}) {
    let addedCount = 0;
    let skippedCount = 0;

    for (const result of results) {
        const filename = result.filepath.split('/').pop();
        const action = userChoices[filename] || 'add';

        if (action === 'skip') {
            skippedCount++;
            continue;
        }

        try {
            const response = await fetch('/api/tokens/add-reference', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    filepath: result.filepath,
                    overwrite_existing: action === 'overwrite',
                    image_type: imageType,  // Add image type
                    ...tags  // Add tag values
                })
            });

            const data = await response.json();
            if (data.success) {
                addedCount++;
            }
        } catch (error) {
            console.error(`Error adding ${result.filepath}:`, error);
        }
    }

    showSuccess(`Added ${addedCount} file references, skipped ${skippedCount}`);
}

// Repair Modal Functions
let currentRepairToken = null;

function showRepairModal(token) {
    currentRepairToken = token;

    const modal = document.getElementById('repairModal');
    document.getElementById('repairTokenName').textContent = token.name || token.filename;
    document.getElementById('repairOriginalPath').textContent = token.filepath;
    document.getElementById('repairLastVerified').textContent = token.last_verified
        ? formatDate(token.last_verified)
        : 'Never';

    // Show initial actions, hide form
    document.getElementById('repairActions').style.display = 'flex';
    document.getElementById('repairForm').style.display = 'none';

    // Setup event listeners
    setupRepairModalListeners();

    modal.style.display = 'flex';
}

function setupRepairModalListeners() {
    // Locate file button
    const locateBtn = document.getElementById('locateFileBtn');
    const newLocateHandler = () => {
        // Show form to enter new path
        document.getElementById('repairActions').style.display = 'none';
        document.getElementById('repairForm').style.display = 'block';
        document.getElementById('repairNewPath').value = '';
        document.getElementById('repairNewPath').focus();
    };
    locateBtn.replaceWith(locateBtn.cloneNode(true));
    document.getElementById('locateFileBtn').addEventListener('click', newLocateHandler);

    // Remove entry button
    const removeBtn = document.getElementById('removeEntryBtn');
    const newRemoveHandler = async () => {
        if (!confirm(`Remove "${currentRepairToken.name || currentRepairToken.filename}" from vault?\n\nThis will delete the database entry but not the file itself.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/tokens/${currentRepairToken.id}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                showSuccess('Token removed from vault');
                document.getElementById('repairModal').style.display = 'none';
                loadTokens();
            } else {
                showError('Failed to remove token');
            }
        } catch (error) {
            showError('Error removing token: ' + error.message);
        }
    };
    removeBtn.replaceWith(removeBtn.cloneNode(true));
    document.getElementById('removeEntryBtn').addEventListener('click', newRemoveHandler);

    // Cancel repair button
    const cancelBtn = document.getElementById('cancelRepairBtn');
    const newCancelHandler = () => {
        document.getElementById('repairActions').style.display = 'flex';
        document.getElementById('repairForm').style.display = 'none';
    };
    cancelBtn.replaceWith(cancelBtn.cloneNode(true));
    document.getElementById('cancelRepairBtn').addEventListener('click', newCancelHandler);

    // Repair form submission
    const repairForm = document.getElementById('repairForm');
    const newFormHandler = async (e) => {
        e.preventDefault();

        const newPath = document.getElementById('repairNewPath').value.trim();

        if (!newPath) {
            showError('Please enter a file path');
            return;
        }

        showLoading();

        try {
            // Update the file path in database
            const response = await fetch(`/api/tokens/${currentRepairToken.id}/update-path`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    filepath: newPath
                })
            });

            const data = await response.json();

            if (data.success) {
                showSuccess('File path updated successfully');
                document.getElementById('repairModal').style.display = 'none';
                loadTokens();
            } else {
                showError(data.error || 'Failed to update file path');
            }
        } catch (error) {
            showError('Error updating file path: ' + error.message);
        } finally {
            hideLoading();
        }
    };
    repairForm.replaceWith(repairForm.cloneNode(true));
    document.getElementById('repairForm').addEventListener('submit', newFormHandler);
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Helper function to check if a filename exists in the database
async function checkFilenameExists(filename) {
    try {
        const response = await fetch(`/api/tokens?filename=${encodeURIComponent(filename)}`);
        const data = await response.json();
        return data.success && data.tokens && data.tokens.length > 0;
    } catch (error) {
        console.error('Error checking filename:', error);
        return false;
    }
}

// Generate auto-numbered filename that doesn't conflict with existing files
async function generateAutoNumberedFilename(baseFilename, existingRenames = []) {
    // Parse filename: "dragon.png" → base="dragon", ext=".png"
    const lastDot = baseFilename.lastIndexOf('.');
    const base = lastDot > 0 ? baseFilename.substring(0, lastDot) : baseFilename;
    const ext = lastDot > 0 ? baseFilename.substring(lastDot) : '';

    let counter = 1;
    let newFilename;

    // Safety limit to prevent infinite loops
    while (counter < 1000) {
        newFilename = `${base}_${counter}${ext}`;

        // Check if filename exists in database
        const existsInDb = await checkFilenameExists(newFilename);

        // Check if filename is already used in current batch of renames
        const existsInBatch = existingRenames.includes(newFilename);

        if (!existsInDb && !existsInBatch) {
            break;
        }

        counter++;
    }

    return newFilename;
}

// Validate custom filename
function validateCustomFilename(filename, originalExtension) {
    // Check if empty
    if (!filename || filename.trim() === '') {
        return { valid: false, error: 'Filename cannot be empty' };
    }

    const trimmed = filename.trim();

    // Check for invalid characters (path separators, etc.)
    const invalidChars = /[/\\:*?"<>|]/;
    if (invalidChars.test(trimmed)) {
        return { valid: false, error: 'Filename contains invalid characters: / \\ : * ? " < > |' };
    }

    // Check for dots at the start (hidden files)
    if (trimmed.startsWith('.')) {
        return { valid: false, error: 'Filename cannot start with a dot' };
    }

    // Check length (most filesystems have 255 char limit)
    if (trimmed.length + originalExtension.length > 255) {
        return { valid: false, error: 'Filename is too long' };
    }

    return { valid: true, filename: trimmed + originalExtension };
}

// Scroll to Top Button
function setupScrollToTop() {
    const scrollBtn = document.getElementById('scrollToTopBtn');

    if (!scrollBtn) return;

    // Show/hide button based on scroll position
    window.addEventListener('scroll', () => {
        if (window.pageYOffset > 300) {
            scrollBtn.classList.add('visible');
        } else {
            scrollBtn.classList.remove('visible');
        }
    });

    // Scroll to top when clicked
    scrollBtn.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

// ========== SUBFOLDER WIZARD FUNCTIONS ==========

// Show subfolder selection modal
async function showSubfolderSelectionModal(subfolders, folderName) {
    return new Promise((resolve, reject) => {
        const modal = document.getElementById('subfolderSelectionModal');
        const subfolderList = document.getElementById('subfolderList');
        const totalCountSpan = document.getElementById('subfolderTotalCount');
        const totalFilesSpan = document.getElementById('subfolderTotalFiles');
        const selectedCountSpan = document.getElementById('selectedSubfolderCount');
        const continueBtn = document.getElementById('continueSubfolderSelectionBtn');
        const selectAllBtn = document.getElementById('selectAllSubfoldersBtn');
        const deselectAllBtn = document.getElementById('deselectAllSubfoldersBtn');
        const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-btn');

        // Calculate totals
        const totalFiles = subfolders.reduce((sum, sf) => sum + sf.files.length, 0);
        totalCountSpan.textContent = subfolders.length;
        totalFilesSpan.textContent = totalFiles;

        // Track selected subfolders
        const selectedSubfolders = new Set();

        // Render subfolder list
        subfolderList.innerHTML = '';
        subfolders.forEach((subfolder, index) => {
            const item = document.createElement('div');
            item.className = 'subfolder-item';
            item.dataset.index = index;

            // Show first 3 file names as preview
            const previewFiles = subfolder.files.slice(0, 3);
            const previewHTML = previewFiles.map(f =>
                `<div class="subfolder-preview-thumb" title="${f.filename}">📄</div>`
            ).join('');

            item.innerHTML = `
                <label class="subfolder-item-label">
                    <input type="checkbox" class="subfolder-checkbox" data-index="${index}" />
                    <div class="subfolder-item-content">
                        <div class="subfolder-item-header">
                            <h3 class="subfolder-name">${subfolder.display_name}</h3>
                            <span class="subfolder-file-count">${subfolder.files.length} files</span>
                        </div>
                        <div class="subfolder-preview">
                            ${previewHTML}
                            ${subfolder.files.length > 3 ? `<span class="subfolder-more">+${subfolder.files.length - 3} more</span>` : ''}
                        </div>
                    </div>
                </label>
            `;

            subfolderList.appendChild(item);

            // Setup checkbox event
            const checkbox = item.querySelector('.subfolder-checkbox');
            checkbox.addEventListener('change', () => {
                if (checkbox.checked) {
                    selectedSubfolders.add(index);
                    item.classList.add('selected');
                } else {
                    selectedSubfolders.delete(index);
                    item.classList.remove('selected');
                }
                updateSelectedCount();
            });
        });

        function updateSelectedCount() {
            selectedCountSpan.textContent = selectedSubfolders.size;
            continueBtn.disabled = selectedSubfolders.size === 0;
        }

        // Select all handler
        selectAllBtn.addEventListener('click', () => {
            document.querySelectorAll('.subfolder-checkbox').forEach(cb => {
                cb.checked = true;
                const index = parseInt(cb.dataset.index);
                selectedSubfolders.add(index);
                cb.closest('.subfolder-item').classList.add('selected');
            });
            updateSelectedCount();
        });

        // Deselect all handler
        deselectAllBtn.addEventListener('click', () => {
            document.querySelectorAll('.subfolder-checkbox').forEach(cb => {
                cb.checked = false;
                const index = parseInt(cb.dataset.index);
                selectedSubfolders.delete(index);
                cb.closest('.subfolder-item').classList.remove('selected');
            });
            updateSelectedCount();
        });

        // Continue handler
        const handleContinue = () => {
            const selected = Array.from(selectedSubfolders).map(i => subfolders[i]);
            modal.style.display = 'none';
            cleanup();
            resolve(selected);
        };

        // Cancel handler
        const handleCancel = () => {
            modal.style.display = 'none';
            cleanup();
            reject(new Error('User cancelled subfolder selection'));
        };

        const cleanup = () => {
            continueBtn.removeEventListener('click', handleContinue);
            closeButtons.forEach(btn => btn.removeEventListener('click', handleCancel));
        };

        continueBtn.addEventListener('click', handleContinue);
        closeButtons.forEach(btn => btn.addEventListener('click', handleCancel));

        // Initialize
        updateSelectedCount();
        modal.style.display = 'flex';
    });
}

// Start the wizard after subfolder selection
async function startSubfolderWizard(selectedSubfolders) {
    try {
        wizardState.subfolders = selectedSubfolders;
        wizardState.currentStep = 0;
        wizardState.assignments = [];
        wizardState.duplicates = [];

        // Show wizard modal
        await showWizardStep(0);

    } catch (error) {
        if (error.message === 'User cancelled wizard') {
            // Silent cancellation
        } else {
            showError('Error in wizard: ' + error.message);
        }
    }
}

// Show wizard step for a specific subfolder
async function showWizardStep(stepIndex) {
    return new Promise((resolve, reject) => {
        const modal = document.getElementById('subfolderWizardModal');
        const form = document.getElementById('wizardTagForm');
        const subfolder = wizardState.subfolders[stepIndex];

        if (!subfolder) {
            // Reached end, show review modal
            showWizardReview();
            resolve();
            return;
        }

        // Update progress
        const totalSteps = wizardState.subfolders.length;
        document.getElementById('wizardCurrentStep').textContent = stepIndex + 1;
        document.getElementById('wizardTotalSteps').textContent = totalSteps;
        const progressPercent = ((stepIndex + 1) / totalSteps) * 100;
        document.getElementById('wizardProgressFill').style.width = progressPercent + '%';

        // Update subfolder info
        document.getElementById('wizardSubfolderName').textContent = subfolder.display_name;
        document.getElementById('wizardSubfolderPath').textContent = subfolder.path || '(Folder)';
        document.getElementById('wizardFileCount').textContent = subfolder.files.length;

        // Render preview grid (show first 12 file names)
        const previewGrid = document.getElementById('wizardPreviewGrid');
        previewGrid.innerHTML = '';
        const previewFiles = subfolder.files.slice(0, 12);

        previewFiles.forEach(fileData => {
            const thumb = document.createElement('div');
            thumb.className = 'wizard-preview-thumb';
            thumb.textContent = fileData.filename.substring(0, 20);
            thumb.title = fileData.filename;
            previewGrid.appendChild(thumb);
        });

        if (subfolder.files.length > 12) {
            const more = document.createElement('div');
            more.className = 'wizard-preview-more';
            more.textContent = `+${subfolder.files.length - 12} more`;
            previewGrid.appendChild(more);
        }

        // Check if any previous assignment exists for this subfolder
        const previousAssignment = wizardState.assignments.find(a => a.subfolder === subfolder);

        // Set up image type selector
        const imageTypeSelect = document.getElementById('wizardImageType');
        imageTypeSelect.value = previousAssignment?.imageType || 'Token';

        // Render dynamic tag fields
        renderWizardTagFields(imageTypeSelect.value, previousAssignment?.tags);

        // Update on image type change
        const imageTypeChangeHandler = () => {
            renderWizardTagFields(imageTypeSelect.value);
        };
        imageTypeSelect.removeEventListener('change', imageTypeChangeHandler);
        imageTypeSelect.addEventListener('change', imageTypeChangeHandler);

        // Check for duplicates
        const hasDuplicates = subfolder.files.some(f =>
            f.content_duplicate || f.name_collision
        );
        document.getElementById('wizardDuplicateWarning').style.display =
            hasDuplicates ? 'flex' : 'none';

        // Navigation buttons
        const prevBtn = document.getElementById('wizardPrevBtn');
        const nextBtn = document.getElementById('wizardNextBtn');
        const skipBtn = document.getElementById('wizardSkipBtn');
        const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-btn');

        prevBtn.style.display = stepIndex > 0 ? 'inline-flex' : 'none';
        nextBtn.textContent = stepIndex === totalSteps - 1 ? 'Review →' : 'Next →';

        // Form submission (Next button)
        const handleNext = (e) => {
            e.preventDefault();

            // Collect form data
            const imageType = imageTypeSelect.value;
            const tags = collectWizardTags();

            // Save assignment
            const assignmentIndex = wizardState.assignments.findIndex(a => a.subfolder === subfolder);
            const assignment = {
                subfolder: subfolder,
                imageType: imageType,
                tags: tags,
                files: subfolder.files
            };

            if (assignmentIndex >= 0) {
                wizardState.assignments[assignmentIndex] = assignment;
            } else {
                wizardState.assignments.push(assignment);
            }

            // Advance to next step
            cleanup();
            modal.style.display = 'none';
            showWizardStep(stepIndex + 1);
            resolve();
        };

        // Previous button
        const handlePrev = () => {
            cleanup();
            modal.style.display = 'none';
            showWizardStep(stepIndex - 1);
            resolve();
        };

        // Skip button
        const handleSkip = () => {
            // Remove this subfolder from wizard
            wizardState.subfolders.splice(stepIndex, 1);

            cleanup();
            modal.style.display = 'none';

            // Show next step (which is now at same index)
            showWizardStep(stepIndex);
            resolve();
        };

        // Cancel
        const handleCancel = () => {
            cleanup();
            modal.style.display = 'none';
            reject(new Error('User cancelled wizard'));
        };

        const cleanup = () => {
            form.removeEventListener('submit', handleNext);
            prevBtn.removeEventListener('click', handlePrev);
            skipBtn.removeEventListener('click', handleSkip);
            closeButtons.forEach(btn => btn.removeEventListener('click', handleCancel));
        };

        form.addEventListener('submit', handleNext);
        prevBtn.addEventListener('click', handlePrev);
        skipBtn.addEventListener('click', handleSkip);
        closeButtons.forEach(btn => btn.addEventListener('click', handleCancel));

        modal.style.display = 'flex';
    });
}

// Render dynamic tag fields in wizard
function renderWizardTagFields(imageType, previousTags = {}) {
    const container = document.getElementById('wizardDynamicTagFields');
    const schema = tagSchemas[imageType] || [];

    container.innerHTML = '';

    // Create tag dropdown for each field in schema
    schema.forEach(field => {
        const formGroup = document.createElement('div');
        formGroup.className = 'form-group';

        const label = document.createElement('label');
        label.textContent = field;

        const dropdownContainer = document.createElement('div');
        dropdownContainer.id = `wizard${field}Container`;
        dropdownContainer.className = 'tag-dropdown-container';

        formGroup.appendChild(label);
        formGroup.appendChild(dropdownContainer);
        container.appendChild(formGroup);

        // Initialize TagDropdown
        const initialValue = previousTags[field] || '';
        new TagDropdown(dropdownContainer, field, imageType, initialValue);
    });
}

// Collect wizard tags from form
function collectWizardTags() {
    const tags = {};
    const dropdowns = document.querySelectorAll('#wizardDynamicTagFields .tag-dropdown-container');

    dropdowns.forEach(container => {
        const dropdown = container.querySelector('.tag-dropdown');
        if (dropdown) {
            const field = dropdown.querySelector('.tag-dropdown-selected').dataset.field;
            const valueSpan = dropdown.querySelector('.tag-dropdown-value');
            const value = valueSpan ? valueSpan.textContent : '';

            if (value && value !== 'Select or type...') {
                tags[field] = value;
            }
        }
    });

    return tags;
}
// Show final review modal
async function showWizardReview() {
    return new Promise((resolve, reject) => {
        const wizardModal = document.getElementById('subfolderWizardModal');
        const reviewModal = document.getElementById('wizardReviewModal');
        const reviewList = document.getElementById('wizardReviewList');
        const duplicateSection = document.getElementById('wizardDuplicateSection');
        const duplicateList = document.getElementById('wizardDuplicateList');
        const importBtn = document.getElementById('wizardImportBtn');
        const backBtn = document.getElementById('wizardBackToEditBtn');
        const closeButtons = reviewModal.querySelectorAll('.modal-close, .modal-close-btn');

        // Close wizard modal
        wizardModal.style.display = 'none';

        // Render review list
        reviewList.innerHTML = '';
        let totalFiles = 0;
        let allDuplicates = [];

        wizardState.assignments.forEach((assignment, index) => {
            const item = document.createElement('div');
            item.className = 'wizard-review-item';

            const tagsList = Object.entries(assignment.tags)
                .map(([key, value]) => `<span class="tag">${key}: ${value}</span>`)
                .join('');

            // Check for duplicates in this subfolder
            const duplicatesInSubfolder = assignment.files.filter(f =>
                f.content_duplicate || f.name_collision
            );

            allDuplicates.push(...duplicatesInSubfolder.map(d => ({
                ...d,
                subfolder: assignment.subfolder.display_name,
                assignmentIndex: index
            })));

            totalFiles += assignment.files.length;

            item.innerHTML = `
                <div class="wizard-review-header">
                    <h3>${assignment.subfolder.display_name}</h3>
                    <button class="btn btn-small wizard-edit-btn" data-index="${index}">Edit</button>
                </div>
                <div class="wizard-review-details">
                    <p><strong>Type:</strong> ${assignment.imageType}</p>
                    <p><strong>Files:</strong> ${assignment.files.length}</p>
                    <div class="wizard-review-tags">${tagsList || '<span class="no-tags">No tags</span>'}</div>
                    ${duplicatesInSubfolder.length > 0 ?
                        `<p class="wizard-review-duplicates">⚠️ ${duplicatesInSubfolder.length} duplicate(s)</p>` : ''}
                </div>
            `;

            reviewList.appendChild(item);

            // Setup edit button
            item.querySelector('.wizard-edit-btn').addEventListener('click', () => {
                reviewModal.style.display = 'none';
                showWizardStep(index);
            });
        });

        // Update summary
        document.getElementById('reviewTotalFiles').textContent = totalFiles;
        document.getElementById('reviewTotalSubfolders').textContent = wizardState.assignments.length;

        // Show duplicate section if any exist
        if (allDuplicates.length > 0) {
            duplicateSection.style.display = 'block';
            renderWizardDuplicates(duplicateList, allDuplicates);
        } else {
            duplicateSection.style.display = 'none';
        }

        // Import button handler
        const handleImport = async () => {
            cleanup();
            reviewModal.style.display = 'none';

            // Execute import
            await executeWizardImport();
            resolve();
        };

        // Back button
        const handleBack = () => {
            cleanup();
            reviewModal.style.display = 'none';
            showWizardStep(wizardState.assignments.length - 1);
        };

        // Cancel
        const handleCancel = () => {
            cleanup();
            reviewModal.style.display = 'none';
            reject(new Error('User cancelled wizard'));
        };

        const cleanup = () => {
            importBtn.removeEventListener('click', handleImport);
            backBtn.removeEventListener('click', handleBack);
            closeButtons.forEach(btn => btn.removeEventListener('click', handleCancel));
        };

        importBtn.addEventListener('click', handleImport);
        backBtn.addEventListener('click', handleBack);
        closeButtons.forEach(btn => btn.addEventListener('click', handleCancel));

        reviewModal.style.display = 'flex';
    });
}

// Render duplicates in review modal
function renderWizardDuplicates(container, duplicates) {
    container.innerHTML = '';

    duplicates.forEach((dup, index) => {
        const item = document.createElement('div');
        item.className = 'duplicate-item';

        const warningType = dup.content_duplicate ? '⛔ Content duplicate' : '⚠️ Name collision';
        const existing = dup.content_duplicate || dup.name_collision;

        item.innerHTML = `
            <div class="duplicate-info">
                <h4>${dup.filename}</h4>
                <p class="duplicate-subfolder">Subfolder: ${dup.subfolder}</p>
                <div class="duplicate-warning">
                    <span>${warningType}</span>
                </div>
                <div class="duplicate-existing-info">
                    Existing: <strong>${existing.name || existing.filename}</strong>
                </div>
            </div>
            <div class="duplicate-actions">
                <label class="duplicate-action-radio selected" data-index="${index}">
                    <input type="radio" name="wizard_dup_${index}" value="skip" checked />
                    <span>Skip</span>
                </label>
                <label class="duplicate-action-radio" data-index="${index}">
                    <input type="radio" name="wizard_dup_${index}" value="rename" />
                    <span>Rename</span>
                </label>
                <label class="duplicate-action-radio" data-index="${index}">
                    <input type="radio" name="wizard_dup_${index}" value="overwrite" />
                    <span>Overwrite</span>
                </label>
            </div>
            <div class="rename-options" id="wizardRenameOptions_${index}" style="display: none;">
                <div class="rename-type-selector">
                    <label class="rename-type-option">
                        <input type="radio" name="wizardRenameType_${index}" value="auto" checked />
                        <span>Auto-number (${dup.filename.replace(/\.[^/.]+$/, '')}_1${dup.filename.match(/\.[^/.]+$/)?.[0] || ''})</span>
                    </label>
                    <label class="rename-type-option">
                        <input type="radio" name="wizardRenameType_${index}" value="manual" />
                        <span>Enter custom name</span>
                    </label>
                </div>
                <div class="manual-rename-input" id="wizardManualRenameInput_${index}" style="display: none;">
                    <input type="text" class="form-input" id="wizardCustomName_${index}" placeholder="Enter new filename (without extension)" />
                    <small>Extension ${dup.filename.match(/\.[^/.]+$/)?.[0] || ''} will be added automatically</small>
                </div>
            </div>
        `;

        container.appendChild(item);

        // Setup action radio handlers
        const radios = item.querySelectorAll('.duplicate-action-radio');
        radios.forEach(label => {
            label.addEventListener('click', function() {
                radios.forEach(r => r.classList.remove('selected'));
                this.classList.add('selected');

                // Store choice in duplicate object
                const radio = this.querySelector('input');
                const renameOptions = document.getElementById(`wizardRenameOptions_${index}`);

                if (radio.value === 'rename') {
                    // Show rename options
                    if (renameOptions) renameOptions.style.display = 'block';

                    // Set default rename choice
                    dup.action = 'rename';
                    dup.renameType = 'auto';
                    dup.customName = '';
                } else {
                    // Hide rename options
                    if (renameOptions) renameOptions.style.display = 'none';

                    // Simple action
                    dup.action = radio.value;
                    delete dup.renameType;
                    delete dup.customName;
                }
            });
        });

        // Setup rename type handlers
        const renameTypeRadios = item.querySelectorAll(`input[name="wizardRenameType_${index}"]`);
        const manualInput = document.getElementById(`wizardManualRenameInput_${index}`);
        const customNameInput = document.getElementById(`wizardCustomName_${index}`);

        renameTypeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                if (this.value === 'manual') {
                    // Show manual input
                    if (manualInput) manualInput.style.display = 'block';
                    dup.renameType = 'manual';
                } else {
                    // Hide manual input
                    if (manualInput) manualInput.style.display = 'none';
                    dup.renameType = 'auto';
                    dup.customName = '';
                }
            });
        });

        // Listen for custom name input
        if (customNameInput) {
            customNameInput.addEventListener('input', function() {
                dup.customName = this.value.trim();
            });
        }

        // Set default action
        dup.action = 'skip';
    });
}

// Execute the wizard import
async function executeWizardImport() {
    try {
        showLoading();

        // Track renamed files to avoid conflicts across subfolders
        const allRenamedFiles = [];

        // Prepare batch import request
        const subfolderAssignments = await Promise.all(wizardState.assignments.map(async assignment => {
            const filesWithActions = await Promise.all(assignment.files.map(async fileData => {
                // Check if file has duplicate resolution
                let fileAction = fileData.action || 'add';
                let newFilename = null;

                // Handle rename action
                if (fileAction === 'rename') {
                    const originalFilename = fileData.filename || fileData.filepath.split('/').pop();
                    const ext = originalFilename.substring(originalFilename.lastIndexOf('.'));

                    if (fileData.renameType === 'auto') {
                        // Generate auto-numbered filename
                        newFilename = await generateAutoNumberedFilename(originalFilename, allRenamedFiles);
                        allRenamedFiles.push(newFilename);
                    } else if (fileData.renameType === 'manual' && fileData.customName) {
                        // Validate custom filename
                        const validation = validateCustomFilename(fileData.customName, ext);

                        if (!validation.valid) {
                            console.error(`Invalid filename for ${originalFilename}: ${validation.error}`);
                            fileAction = 'skip'; // Fall back to skip if validation fails
                        } else {
                            newFilename = validation.filename;

                            // Check if already exists
                            if (await checkFilenameExists(newFilename) || allRenamedFiles.includes(newFilename)) {
                                console.error(`Filename ${newFilename} already exists, skipping ${originalFilename}`);
                                fileAction = 'skip';
                            } else {
                                allRenamedFiles.push(newFilename);
                            }
                        }
                    } else {
                        // No valid rename type - fall back to skip
                        fileAction = 'skip';
                    }
                }

                const fileEntry = {
                    filepath: fileData.filepath,
                    action: fileAction === 'rename' && newFilename ? 'add' : fileAction
                };

                // Add new_filename for renamed files
                if (fileAction === 'rename' && newFilename) {
                    fileEntry.new_filename = newFilename;
                }

                return fileEntry;
            }));

            return {
                subfolder_path: assignment.subfolder.path || assignment.subfolder.display_name,
                image_type: assignment.imageType,
                tags: assignment.tags,
                files: filesWithActions
            };
        }));

        // Call batch endpoint
        const response = await fetch('/api/tokens/add-references-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subfolder_assignments: subfolderAssignments })
        });

        const data = await response.json();

        if (data.success) {
            const results = data.results;
            showSuccess(
                `Import complete! Added ${results.added}, ` +
                `updated ${results.updated}, skipped ${results.skipped}`
            );
        } else {
            showError('Import failed: ' + (data.error || 'Unknown error'));
        }

        // Reload tokens
        await loadTokens();
        await loadFilterOptions();

    } catch (error) {
        showError('Error importing files: ' + error.message);
    } finally {
        hideLoading();
    }
}

// ========== DRAG AND DROP HANDLERS ==========

// Setup drag-and-drop for folder import modal
function setupFolderDragDrop() {
    const dropZone = document.getElementById('folderDropZone');
    const folderPathInput = document.getElementById('folderPathInput');

    if (!dropZone) return;

    // Prevent defaults
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        }, false);
    });

    // Visual feedback
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drag-over');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drag-over');
        }, false);
    });

    // Handle drop
    dropZone.addEventListener('drop', (e) => {
        // Due to browser security restrictions, we cannot get the actual filesystem path
        // from a dropped folder. Instead, show a helpful message to the user.
        alert('Please paste the folder path in the input field below.\n\nOn Mac: Right-click the folder in Finder, hold Option, then select "Copy as Pathname".');
        folderPathInput.focus();
    }, false);

    // Also make the drop zone clickable as a hint
    dropZone.addEventListener('click', () => {
        folderPathInput.focus();
    });
}

// ============================================================================
// Google Drive Integration
// ============================================================================

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Toast notification durations and icons by type
const TOAST_DURATIONS = { success: 4000, info: 4000, error: 6000 };
const TOAST_ICONS = { success: '✓', error: '⚠' };

// Show a toast notification (type: 'success' | 'error' | 'info')
function showNotification(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) {
        alert(message);
        return;
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');

    const icon = TOAST_ICONS[type];
    toast.innerHTML = `
        ${icon ? `<span class="toast-icon" aria-hidden="true">${icon}</span>` : ''}
        <span class="toast-message"></span>
        <button type="button" class="toast-close" aria-label="Dismiss notification">&times;</button>
    `;
    toast.querySelector('.toast-message').textContent = message;

    const dismiss = () => {
        if (toast.dataset.dismissed) return;
        toast.dataset.dismissed = 'true';
        toast.classList.add('toast-leaving');
        setTimeout(() => toast.remove(), 200);
    };

    toast.querySelector('.toast-close').addEventListener('click', dismiss);
    container.appendChild(toast);
    setTimeout(dismiss, TOAST_DURATIONS[type] || TOAST_DURATIONS.info);
}

// ============================================================================
// AUDIO FILE MANAGEMENT
// ============================================================================

// Audio state
let audioFiles = [];
let filteredAudioFiles = [];
let currentMediaTab = 'images';
let currentAudioPlayer = null;
let currentPlayingAudioId = null;
let audioTagDropdowns = {};
let pendingAudioUploadFiles = null;
let audioUploadInProgress = false;

// Audio filter state
let currentAudioFilters = {
    search: '',
    audio_type: '',
    genre: '',
    mood: '',
    source: '',
    campaign: '',
    sort_by: 'filename',
    sort_order: 'ASC'
};

// Audio tag schemas
const audioTagSchemas = {
    'Music': ['Genre', 'Mood', 'Source', 'Campaign'],
    'SoundEffect': ['Intensity', 'Location', 'Source', 'Campaign'],
    'Ambience': ['Mood', 'Intensity', 'Location', 'Source', 'Campaign'],
    'Dialogue': ['Character', 'Source', 'Campaign']
};

// Audio type icons
const audioTypeIcons = {
    'Music': '🎶',
    'SoundEffect': '💥',
    'Ambience': '🌲',
    'Dialogue': '💬'
};

// Initialize audio functionality
function initAudioListeners() {
    // Media tab switching
    document.querySelectorAll('.media-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            switchMediaTab(tabName);
        });
    });

    // Audio search
    const audioSearchInput = document.getElementById('audioSearchInput');
    if (audioSearchInput) {
        audioSearchInput.addEventListener('input', debounce(handleAudioSearchChange, 300));
    }

    // Audio type filter
    const audioTypeFilter = document.getElementById('audioTypeFilter');
    if (audioTypeFilter) {
        audioTypeFilter.addEventListener('change', handleAudioTypeFilterChange);
    }

    // Audio sort
    const audioSortBy = document.getElementById('audioSortBy');
    if (audioSortBy) {
        audioSortBy.addEventListener('change', handleAudioSortChange);
    }

    // Clear audio filters
    const clearAudioFiltersBtn = document.getElementById('clearAudioFiltersBtn');
    if (clearAudioFiltersBtn) {
        clearAudioFiltersBtn.addEventListener('click', clearAudioFilters);
    }

    // Audio edit form
    const audioEditForm = document.getElementById('audioEditForm');
    if (audioEditForm) {
        audioEditForm.addEventListener('submit', handleAudioUpdate);
    }

    // Audio type change in edit modal
    const editAudioType = document.getElementById('editAudioType');
    if (editAudioType) {
        editAudioType.addEventListener('change', handleAudioTypeChangeInModal);
    }

    // Delete audio button
    const deleteAudioBtn = document.getElementById('deleteAudioBtn');
    if (deleteAudioBtn) {
        deleteAudioBtn.addEventListener('click', handleAudioDelete);
    }

    // Audio upload form
    const audioUploadForm = document.getElementById('audioUploadForm');
    if (audioUploadForm) {
        audioUploadForm.addEventListener('submit', handleAudioUpload);
    }

    // Audio upload type change
    const uploadAudioType = document.getElementById('uploadAudioType');
    if (uploadAudioType) {
        uploadAudioType.addEventListener('change', handleUploadAudioTypeChange);
    }

    // Audio drop zone
    setupAudioDropZone();

    // Audio file input
    const audioFileInput = document.getElementById('audioFileInput');
    if (audioFileInput) {
        audioFileInput.addEventListener('change', handleAudioFileSelect);
    }

    // Audio file path link (copy to clipboard)
    const audioFilePathLink = document.getElementById('audioModalFilePath');
    if (audioFilePathLink) {
        audioFilePathLink.addEventListener('click', handleAudioFilePathClick);
    }

    // Audio Show in Finder button
    const audioShowInFinderBtn = document.getElementById('audioShowInFinderBtn');
    if (audioShowInFinderBtn) {
        audioShowInFinderBtn.addEventListener('click', handleAudioShowInFinder);
    }
}

// Switch between media tabs
function switchMediaTab(tabName) {
    currentMediaTab = tabName;

    // Update tab buttons
    document.querySelectorAll('.media-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Show/hide content sections
    const tokenGallery = document.getElementById('tokenGallery');
    const audioGallery = document.getElementById('audioGallery');
    const pdfGallery = document.getElementById('pdfGallery');
    const imageFilters = document.getElementById('imageFilters');
    const audioFilters = document.getElementById('audioFilters');
    const pdfFilters = document.getElementById('pdfFilters');
    const bulkActionsBar = document.getElementById('bulkActionsBar');
    const viewToggle = document.querySelector('.view-toggle');

    if (tabName === 'images') {
        tokenGallery.style.display = '';
        audioGallery.style.display = 'none';
        pdfGallery.style.display = 'none';
        imageFilters.style.display = '';
        audioFilters.style.display = 'none';
        pdfFilters.style.display = 'none';
        bulkActionsBar.style.display = selectedTokenIds.size > 0 ? 'flex' : 'none';
        viewToggle.style.display = '';

        // Update upload button text
        document.getElementById('uploadBtn').innerHTML = '<span>📤</span> Upload Images';
    } else if (tabName === 'audio') {
        tokenGallery.style.display = 'none';
        audioGallery.style.display = '';
        pdfGallery.style.display = 'none';
        imageFilters.style.display = 'none';
        audioFilters.style.display = '';
        pdfFilters.style.display = 'none';
        bulkActionsBar.style.display = 'none';
        viewToggle.style.display = 'none';

        // Update upload button text
        document.getElementById('uploadBtn').innerHTML = '<span>📤</span> Upload Audio';

        // Load audio files if not loaded
        if (audioFiles.length === 0) {
            loadAudioFiles();
        }
    } else if (tabName === 'pdfs') {
        tokenGallery.style.display = 'none';
        audioGallery.style.display = 'none';
        pdfGallery.style.display = '';
        imageFilters.style.display = 'none';
        audioFilters.style.display = 'none';
        pdfFilters.style.display = '';
        bulkActionsBar.style.display = 'none';
        viewToggle.style.display = 'none';

        // Update upload button text
        document.getElementById('uploadBtn').innerHTML = '<span>📤</span> Upload PDFs';

        // Load PDF files if not loaded
        if (pdfFiles.length === 0) {
            loadPdfFiles();
        }
        loadPdfFilterOptions();
    }
}

// Load audio files from API
async function loadAudioFiles() {
    const audioGallery = document.getElementById('audioGallery');
    audioGallery.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading audio files...</p></div>';

    try {
        const params = new URLSearchParams(currentAudioFilters);
        const response = await fetch(`/api/audio?${params}`);
        const data = await response.json();

        if (data.success) {
            audioFiles = data.audio_files;
            filteredAudioFiles = audioFiles;
            renderAudioFiles();
            updateAudioTabCount();
        } else {
            showError('Failed to load audio files');
        }
    } catch (error) {
        showError('Error loading audio files: ' + error.message);
    }
}

// Render audio files to gallery
function renderAudioFiles() {
    const audioGallery = document.getElementById('audioGallery');
    audioGallery.innerHTML = '';

    if (filteredAudioFiles.length === 0) {
        audioGallery.innerHTML = `
            <div class="empty-state">
                <h2>No Audio Files Found</h2>
                <p>Upload some audio files to get started!</p>
            </div>
        `;
        return;
    }

    filteredAudioFiles.forEach(audio => {
        const card = createAudioCard(audio);
        audioGallery.appendChild(card);
    });
}

// Create audio card element
function createAudioCard(audio) {
    const card = document.createElement('div');
    card.className = 'audio-card';
    card.dataset.audioId = audio.id;

    const displayName = audio.name || audio.filename;
    const audioType = audio.audio_type || 'Music';
    const icon = audioTypeIcons[audioType] || '🎵';
    const duration = formatDuration(audio.duration_seconds);

    // Get relevant tags for this audio type
    const schema = audioTagSchemas[audioType] || [];
    let tagsHtml = '';
    for (const field of schema) {
        const fieldLower = field.toLowerCase();
        const value = audio[fieldLower];
        if (value) {
            tagsHtml += `<span class="tag tag-${fieldLower}">${value}</span>`;
        }
    }

    const isPlaying = currentPlayingAudioId === audio.id;

    card.innerHTML = `
        <div class="audio-card-main">
            <div class="audio-card-icon">
                <span class="audio-type-icon-large">${icon}</span>
                <span class="audio-type-badge audio-type-${audioType.toLowerCase()}">${audioType}</span>
            </div>
            <div class="audio-card-content">
                <div class="audio-card-header">
                    <h3 class="audio-name">${escapeHtml(displayName)}</h3>
                    <span class="audio-duration">${duration}</span>
                </div>
                <div class="audio-tags">
                    ${tagsHtml || '<span class="no-tags">No tags</span>'}
                </div>
            </div>
            <div class="audio-card-actions">
                <button class="audio-play-btn ${isPlaying ? 'playing' : ''}" title="${isPlaying ? 'Pause' : 'Play'}">
                    ${isPlaying ? '⏸️' : '▶️'}
                </button>
            </div>
        </div>
    `;

    // Play button click
    const playBtn = card.querySelector('.audio-play-btn');
    playBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleAudioPlayback(audio.id, playBtn);
    });

    // Card click - open modal
    card.addEventListener('click', () => {
        openAudioModal(audio);
    });

    return card;
}

// Toggle audio playback
function toggleAudioPlayback(audioId, buttonEl) {
    if (currentPlayingAudioId === audioId) {
        // Pause current audio
        pauseAudio();
    } else {
        // Play new audio
        playAudio(audioId, buttonEl);
    }
}

// Play audio
function playAudio(audioId, buttonEl) {
    // Stop any currently playing audio
    pauseAudio();

    // Create or reuse audio element
    if (!currentAudioPlayer) {
        currentAudioPlayer = new Audio();
        currentAudioPlayer.addEventListener('ended', () => {
            pauseAudio();
        });
    }

    currentAudioPlayer.src = `/api/audio/stream/${audioId}`;
    currentAudioPlayer.play();

    currentPlayingAudioId = audioId;

    // Update button
    if (buttonEl) {
        buttonEl.classList.add('playing');
        buttonEl.innerHTML = '⏸️';
        buttonEl.title = 'Pause';
    }

    // Update all play buttons
    document.querySelectorAll('.audio-play-btn').forEach(btn => {
        const card = btn.closest('.audio-card');
        if (card && parseInt(card.dataset.audioId) === audioId) {
            btn.classList.add('playing');
            btn.innerHTML = '⏸️';
        } else {
            btn.classList.remove('playing');
            btn.innerHTML = '▶️';
        }
    });
}

// Pause audio
function pauseAudio() {
    if (currentAudioPlayer) {
        currentAudioPlayer.pause();
    }

    currentPlayingAudioId = null;

    // Update all play buttons
    document.querySelectorAll('.audio-play-btn').forEach(btn => {
        btn.classList.remove('playing');
        btn.innerHTML = '▶️';
        btn.title = 'Play';
    });
}

// Format duration in MM:SS
function formatDuration(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';

    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Open audio detail modal
function openAudioModal(audio) {
    const modal = document.getElementById('audioModal');
    const audioPlayer = document.getElementById('audioPlayer');

    // Populate basic info
    document.getElementById('editAudioId').value = audio.id;
    document.getElementById('audioModalFilename').textContent = audio.name || audio.filename;
    document.getElementById('audioModalDuration').textContent = formatDuration(audio.duration_seconds);
    document.getElementById('audioModalFile').textContent = audio.filename;
    document.getElementById('audioModalFormat').textContent = audio.format || 'Unknown';
    document.getElementById('audioModalSize').textContent = formatFileSize(audio.file_size);
    document.getElementById('audioModalDateAdded').textContent = formatDate(audio.date_added);
    document.getElementById('audioModalTypeIcon').textContent = audioTypeIcons[audio.audio_type] || '🎵';

    // File path and Show in Finder
    const filePathLink = document.getElementById('audioModalFilePath');
    const filePathText = document.getElementById('audioModalFilePathText');
    const showInFinderBtn = document.getElementById('audioShowInFinderBtn');

    if (audio.filepath) {
        filePathText.textContent = audio.filepath;
        filePathLink.dataset.filepath = audio.filepath;

        // Show "Show in Finder" button only in Electron mode
        if (window.electronAPI && window.electronAPI.showItemInFolder) {
            showInFinderBtn.style.display = 'inline-block';
        } else {
            showInFinderBtn.style.display = 'none';
        }
    } else {
        filePathText.textContent = 'Unknown';
        filePathLink.dataset.filepath = '';
        showInFinderBtn.style.display = 'none';
    }

    // Set audio player source
    audioPlayer.src = `/api/audio/stream/${audio.id}`;

    // Populate edit form
    document.getElementById('editAudioName').value = audio.name || '';
    document.getElementById('editAudioType').value = audio.audio_type || 'Music';
    document.getElementById('editAudioNotes').value = audio.notes || '';

    // Build dynamic tag fields
    buildAudioTagFields(audio.audio_type || 'Music', audio);

    modal.style.display = 'flex';
}

// Build audio tag fields based on audio type
function buildAudioTagFields(audioType, audio = {}) {
    const container = document.getElementById('audioDynamicTagFields');
    container.innerHTML = '';
    audioTagDropdowns = {};

    const schema = audioTagSchemas[audioType] || [];

    schema.forEach(field => {
        const fieldLower = field.toLowerCase();
        const value = audio[fieldLower] || '';

        const formGroup = document.createElement('div');
        formGroup.className = 'form-group';
        formGroup.innerHTML = `
            <label for="editAudio${field}">${field}</label>
            <div id="editAudio${field}Container" class="tag-dropdown-container"></div>
        `;
        container.appendChild(formGroup);

        // Create tag dropdown
        const dropdownContainer = formGroup.querySelector(`#editAudio${field}Container`);
        audioTagDropdowns[field] = new TagDropdown(dropdownContainer, field, audioType, value);
    });
}

// Handle audio type change in edit modal
function handleAudioTypeChangeInModal() {
    const newType = document.getElementById('editAudioType').value;
    buildAudioTagFields(newType);
}

// Handle audio file path click (copy to clipboard)
async function handleAudioFilePathClick(e) {
    e.preventDefault();
    e.stopPropagation();

    const filepath = e.currentTarget.dataset.filepath;
    if (!filepath) return;

    try {
        await navigator.clipboard.writeText(filepath);
        showSuccess('Path copied to clipboard');
    } catch (error) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = filepath;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        showSuccess('Path copied to clipboard');
    }
}

// Handle audio "Show in Finder" button click
async function handleAudioShowInFinder(e) {
    e.preventDefault();
    e.stopPropagation();

    const filepath = document.getElementById('audioModalFilePath').dataset.filepath;

    if (!filepath) {
        showError('No file path available');
        return;
    }

    if (!window.electronAPI || !window.electronAPI.showItemInFolder) {
        showError('This feature is only available in desktop mode');
        return;
    }

    try {
        const result = await window.electronAPI.showItemInFolder(filepath);
        if (result.success) {
            showSuccess('Opening file location...');
        } else {
            showError(`Failed to open: ${result.error}`);
        }
    } catch (error) {
        showError(`Error: ${error.message}`);
    }
}

// Handle audio update
async function handleAudioUpdate(e) {
    e.preventDefault();

    const audioId = document.getElementById('editAudioId').value;
    const audioType = document.getElementById('editAudioType').value;

    const updateData = {
        Name: document.getElementById('editAudioName').value,
        AudioType: audioType,
        Notes: document.getElementById('editAudioNotes').value
    };

    // Get dynamic tag values
    for (const [field, dropdown] of Object.entries(audioTagDropdowns)) {
        updateData[field] = dropdown.getValue();
    }

    try {
        const response = await fetch(`/api/audio/${audioId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData)
        });

        const data = await response.json();

        if (data.success) {
            closeModals();
            loadAudioFiles();
            showNotification('Audio file updated successfully');
        } else {
            showError(data.error || 'Failed to update audio file');
        }
    } catch (error) {
        showError('Error updating audio file: ' + error.message);
    }
}

// Handle audio delete
async function handleAudioDelete() {
    const audioId = document.getElementById('editAudioId').value;

    if (!confirm('Are you sure you want to delete this audio file?')) {
        return;
    }

    try {
        const response = await fetch(`/api/audio/${audioId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            closeModals();
            loadAudioFiles();
            showNotification('Audio file deleted');
        } else {
            showError(data.error || 'Failed to delete audio file');
        }
    } catch (error) {
        showError('Error deleting audio file: ' + error.message);
    }
}

// Handle audio search change
function handleAudioSearchChange(e) {
    currentAudioFilters.search = e.target.value;
    loadAudioFiles();
}

// Handle audio type filter change
function handleAudioTypeFilterChange(e) {
    currentAudioFilters.audio_type = e.target.value;
    loadAudioFiles();
}

// Handle audio sort change
function handleAudioSortChange(e) {
    currentAudioFilters.sort_by = e.target.value;
    loadAudioFiles();
}

// Clear audio filters
function clearAudioFilters() {
    currentAudioFilters = {
        search: '',
        audio_type: '',
        genre: '',
        mood: '',
        source: '',
        campaign: '',
        sort_by: 'filename',
        sort_order: 'ASC'
    };

    document.getElementById('audioSearchInput').value = '';
    document.getElementById('audioTypeFilter').value = '';
    document.getElementById('audioSortBy').value = 'filename';

    loadAudioFiles();
}

// Update audio tab count
function updateAudioTabCount() {
    const countEl = document.getElementById('audioTabCount');
    if (countEl) {
        countEl.textContent = audioFiles.length;
    }
}

// Update image tab count
function updateImageTabCount() {
    const countEl = document.getElementById('imageTabCount');
    if (countEl) {
        countEl.textContent = tokens.length;
    }
}

// Setup audio drop zone
function setupAudioDropZone() {
    const dropZone = document.getElementById('audioDropZone');
    if (!dropZone) return;

    dropZone.addEventListener('click', () => {
        document.getElementById('audioFileInput').click();
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');

        const files = Array.from(e.dataTransfer.files).filter(f =>
            f.name.match(/\.(mp3|wav|ogg|m4a|flac)$/i)
        );

        if (files.length > 0) {
            pendingAudioUploadFiles = files;
            showAudioFileList(files);
        }
    });
}

// Handle audio file selection
function handleAudioFileSelect(e) {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
        pendingAudioUploadFiles = files;
        showAudioFileList(files);
    }
}

// Show selected audio files
function showAudioFileList(files) {
    const listEl = document.getElementById('audioFileList');
    const submitBtn = document.getElementById('uploadAudioSubmitBtn');

    listEl.innerHTML = files.map(f => `
        <div class="audio-file-item">
            <span class="audio-file-icon">🎵</span>
            <span class="audio-file-name">${escapeHtml(f.name)}</span>
            <span class="audio-file-size">${formatFileSize(f.size)}</span>
        </div>
    `).join('');

    listEl.style.display = 'block';
    submitBtn.disabled = false;
}

// Handle audio upload
async function handleAudioUpload(e) {
    e.preventDefault();

    if (!pendingAudioUploadFiles || pendingAudioUploadFiles.length === 0) {
        showError('No files selected');
        return;
    }

    if (audioUploadInProgress) {
        showNotification('Upload already in progress...', 'info');
        return;
    }

    audioUploadInProgress = true;
    const submitBtn = document.getElementById('uploadAudioSubmitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Uploading...';

    const audioType = document.getElementById('uploadAudioType').value;

    const formData = new FormData();
    formData.append('audio_type', audioType);

    pendingAudioUploadFiles.forEach(file => {
        formData.append('files', file);
    });

    try {
        showNotification('Uploading audio files...', 'info');

        const response = await fetch('/api/audio/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            const results = data.results;
            showNotification(`Upload complete: ${results.added} added, ${results.errors} errors`);

            closeModals();
            pendingAudioUploadFiles = null;
            document.getElementById('audioFileList').style.display = 'none';
            document.getElementById('uploadAudioSubmitBtn').disabled = true;

            loadAudioFiles();
        } else {
            showError(data.error || 'Upload failed');
        }
    } catch (error) {
        showError('Error uploading audio: ' + error.message);
    } finally {
        audioUploadInProgress = false;
        submitBtn.textContent = 'Upload';
    }
}

// Handle upload audio type change (for dynamic tags in upload modal)
function handleUploadAudioTypeChange() {
    // Future: Build dynamic tag fields based on selected type
}

// ============================================
// SIMPLIFIED IMAGE UPLOAD
// ============================================

let pendingImageUploadFiles = null;
let imageUploadInProgress = false;

// Setup image drop zone for simplified upload
function setupImageDropZone() {
    const dropZone = document.getElementById('imageDropZone');
    if (!dropZone) return;

    dropZone.addEventListener('click', () => {
        document.getElementById('imageFileInputSimple').click();
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');

        const files = Array.from(e.dataTransfer.files).filter(f =>
            f.name.match(/\.(png|jpg|jpeg)$/i)
        );

        if (files.length > 0) {
            pendingImageUploadFiles = files;
            showImageFileList(files);
        }
    });
}

// Handle image file selection for simplified upload
function handleImageFileSelect(e) {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
        pendingImageUploadFiles = files;
        showImageFileList(files);
    }
}

// Show selected image files in upload modal
function showImageFileList(files) {
    const listEl = document.getElementById('imageFileList');
    const submitBtn = document.getElementById('uploadImageSubmitBtn');

    listEl.innerHTML = files.map(f => `
        <div class="audio-file-item">
            <span class="audio-file-icon">🖼️</span>
            <span class="audio-file-name">${escapeHtml(f.name)}</span>
            <span class="audio-file-size">${formatFileSize(f.size)}</span>
        </div>
    `).join('');

    listEl.style.display = 'block';
    submitBtn.disabled = false;
}

// Handle simplified image upload
async function handleSimpleImageUpload(e) {
    e.preventDefault();

    if (!pendingImageUploadFiles || pendingImageUploadFiles.length === 0) {
        showError('No files selected');
        return;
    }

    if (imageUploadInProgress) {
        showNotification('Upload already in progress...', 'info');
        return;
    }

    imageUploadInProgress = true;
    const submitBtn = document.getElementById('uploadImageSubmitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Uploading...';

    const imageType = document.getElementById('uploadImageType').value;

    // Collect tag values from upload tag dropdowns
    const tags = {};
    for (const field in uploadImageTagDropdowns) {
        const dropdown = uploadImageTagDropdowns[field];
        const value = dropdown.getValue();

        // Handle both single values (string) and multiple values (array)
        if (Array.isArray(value) && value.length > 0) {
            tags[field] = value; // TagMultiSelect returns array
        } else if (typeof value === 'string' && value) {
            tags[field] = value; // TagDropdown returns string
        }
    }

    try {
        showNotification('Uploading images...', 'info');

        // Get file paths (Electron required)
        const filePaths = getFilePaths(pendingImageUploadFiles);

        // Add files by path (reference mode)
        await addFileReferencesDirectly(filePaths, imageType, tags);

        showNotification(`Upload complete: ${pendingImageUploadFiles.length} images added`);

        closeModals();
        resetImageUploadModal();
        loadTokens();
        loadFilterOptions();
    } catch (error) {
        showError('Error uploading images: ' + error.message);
    } finally {
        imageUploadInProgress = false;
        submitBtn.disabled = false;
        submitBtn.textContent = 'Upload';
    }
}

// Reset the image upload modal state
function resetImageUploadModal() {
    pendingImageUploadFiles = null;
    const listEl = document.getElementById('imageFileList');
    const submitBtn = document.getElementById('uploadImageSubmitBtn');
    if (listEl) listEl.style.display = 'none';
    if (submitBtn) submitBtn.disabled = true;
    const simpleFileInput = document.getElementById('imageFileInputSimple');
    if (simpleFileInput) simpleFileInput.value = '';

    // Reset image type to default and rebuild tag fields
    const uploadImageType = document.getElementById('uploadImageType');
    if (uploadImageType) {
        uploadImageType.value = 'Token';
        buildUploadImageTagFields('Token');
    }
}

// Initialize simplified image upload listeners
function initImageUploadListeners() {
    // Simple image file input
    const imageFileInputSimple = document.getElementById('imageFileInputSimple');
    if (imageFileInputSimple) {
        imageFileInputSimple.addEventListener('change', handleImageFileSelect);
    }

    // Image upload form
    const imageUploadForm = document.getElementById('imageUploadForm');
    if (imageUploadForm) {
        imageUploadForm.addEventListener('submit', handleSimpleImageUpload);
    }

    // Image type dropdown - rebuild tag fields when type changes
    const uploadImageType = document.getElementById('uploadImageType');
    if (uploadImageType) {
        uploadImageType.addEventListener('change', () => {
            buildUploadImageTagFields(uploadImageType.value);
        });
        // Build initial tag fields for default type (Token)
        buildUploadImageTagFields(uploadImageType.value);
    }

    // Import folder link
    const importFolderLink = document.getElementById('importFolderLink');
    if (importFolderLink) {
        importFolderLink.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('addFilesModal').style.display = 'none';
            document.getElementById('folderImportModal').style.display = 'flex';
        });
    }

    // Setup image drop zone
    setupImageDropZone();
}

// Format file size
function formatFileSize(bytes) {
    if (!bytes) return 'Unknown';
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    return `${mb.toFixed(1)} MB`;
}

// Format date
function formatDate(dateStr) {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

// Override upload button click depending on the active media tab
const originalUploadBtnHandler = () => {
    if (currentMediaTab === 'audio') {
        document.getElementById('audioUploadModal').style.display = 'flex';
    } else if (currentMediaTab === 'pdfs') {
        document.getElementById('pdfUploadModal').style.display = 'flex';
    } else {
        document.getElementById('addFilesModal').style.display = 'flex';
    }
};

// Initialize audio when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initAudioListeners();
    initImageUploadListeners();
    initPdfListeners();

    // Override upload button
    const uploadBtn = document.getElementById('uploadBtn');
    if (uploadBtn) {
        // Remove existing listener and add new one
        const newUploadBtn = uploadBtn.cloneNode(true);
        uploadBtn.parentNode.replaceChild(newUploadBtn, uploadBtn);
        newUploadBtn.addEventListener('click', originalUploadBtnHandler);
    }

    // Load initial tab counts
    setTimeout(() => {
        updateImageTabCount();
        // Fetch audio count
        fetch('/api/audio')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('audioTabCount').textContent = data.count || 0;
                }
            })
            .catch(() => {});
        // Fetch PDF count
        fetch('/api/pdfs')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('pdfTabCount').textContent = data.count || 0;
                }
            })
            .catch(() => {});
    }, 100);
});

// ============================================================================
// PDF FILES
// ============================================================================

// PDF state
let pdfFiles = [];
let filteredPdfFiles = [];
let pendingPdfUploadFiles = null;
let pdfUploadInProgress = false;

// PDF filter state
let currentPdfFilters = {
    search: '',
    image_type: '',
    source: '',
    campaign: '',
    sort_by: 'filename',
    sort_order: 'ASC'
};

// Initialize PDF functionality
function initPdfListeners() {
    const pdfSearchInput = document.getElementById('pdfSearchInput');
    if (pdfSearchInput) {
        pdfSearchInput.addEventListener('input', debounce(handlePdfSearchChange, 300));
    }

    const pdfTypeFilter = document.getElementById('pdfTypeFilter');
    if (pdfTypeFilter) {
        pdfTypeFilter.addEventListener('change', handlePdfTypeFilterChange);
    }

    const pdfSourceFilter = document.getElementById('pdfSourceFilter');
    if (pdfSourceFilter) {
        pdfSourceFilter.addEventListener('change', handlePdfSourceFilterChange);
    }

    const pdfCampaignFilter = document.getElementById('pdfCampaignFilter');
    if (pdfCampaignFilter) {
        pdfCampaignFilter.addEventListener('change', handlePdfCampaignFilterChange);
    }

    const pdfSortBy = document.getElementById('pdfSortBy');
    if (pdfSortBy) {
        pdfSortBy.addEventListener('change', handlePdfSortChange);
    }

    const clearPdfFiltersBtn = document.getElementById('clearPdfFiltersBtn');
    if (clearPdfFiltersBtn) {
        clearPdfFiltersBtn.addEventListener('click', clearPdfFilters);
    }

    const pdfEditForm = document.getElementById('pdfEditForm');
    if (pdfEditForm) {
        pdfEditForm.addEventListener('submit', handlePdfUpdate);
    }

    const deletePdfBtn = document.getElementById('deletePdfBtn');
    if (deletePdfBtn) {
        deletePdfBtn.addEventListener('click', handlePdfDelete);
    }

    const pdfFilePathLink = document.getElementById('pdfModalFilePath');
    if (pdfFilePathLink) {
        pdfFilePathLink.addEventListener('click', handlePdfFilePathClick);
    }

    const pdfShowInFinderBtn = document.getElementById('pdfShowInFinderBtn');
    if (pdfShowInFinderBtn) {
        pdfShowInFinderBtn.addEventListener('click', handlePdfShowInFinder);
    }

    const pdfOpenBtn = document.getElementById('pdfOpenBtn');
    if (pdfOpenBtn) {
        pdfOpenBtn.addEventListener('click', handlePdfOpen);
    }

    const pdfUploadForm = document.getElementById('pdfUploadForm');
    if (pdfUploadForm) {
        pdfUploadForm.addEventListener('submit', handlePdfUpload);
    }

    const pdfFileInput = document.getElementById('pdfFileInput');
    if (pdfFileInput) {
        pdfFileInput.addEventListener('change', handlePdfFileSelect);
    }

    setupPdfDropZone();
}

// Load PDF files from API
async function loadPdfFiles() {
    const pdfGallery = document.getElementById('pdfGallery');
    pdfGallery.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading PDFs...</p></div>';

    try {
        const params = new URLSearchParams(currentPdfFilters);
        const response = await fetch(`/api/pdfs?${params}`);
        const data = await response.json();

        if (data.success) {
            pdfFiles = data.pdf_files;
            filteredPdfFiles = pdfFiles;
            renderPdfFiles();
            updatePdfTabCount();
        } else {
            showError('Failed to load PDF files');
        }
    } catch (error) {
        showError('Error loading PDF files: ' + error.message);
    }
}

// Render PDF files to gallery
function renderPdfFiles() {
    const pdfGallery = document.getElementById('pdfGallery');
    pdfGallery.innerHTML = '';

    if (filteredPdfFiles.length === 0) {
        pdfGallery.innerHTML = `
            <div class="empty-state" style="display: block;">
                <h2>No PDFs Found</h2>
                <p>Add some PDF references to get started!</p>
            </div>
        `;
        return;
    }

    filteredPdfFiles.forEach(pdf => {
        const card = createPdfCard(pdf);
        pdfGallery.appendChild(card);
    });
}

// Create a PDF card element
function createPdfCard(pdf) {
    const card = document.createElement('div');
    card.className = 'token-card';
    card.dataset.pdfId = pdf.id;

    if (pdf.is_missing) {
        card.classList.add('missing');
    }

    const displayName = pdf.name || pdf.filename;
    const imageType = pdf.image_type || 'Handout';
    const pageLabel = pdf.page_count ? `${pdf.page_count} page${pdf.page_count !== 1 ? 's' : ''}` : '';

    card.innerHTML = `
        <div class="token-image-container">
            <img src="/api/pdf-thumbnail/${pdf.id}" alt="${escapeHtml(displayName)}" class="token-image">
            <span class="image-type-badge image-type-${imageType.toLowerCase()}">${imageType}</span>
        </div>
        <div class="token-info">
            <div class="token-name">${escapeHtml(displayName)}</div>
            <div class="token-tags">
                ${pdf.source ? `<span class="tag tag-source">${escapeHtml(pdf.source)}</span>` : ''}
                ${pdf.campaign ? `<span class="tag tag-campaign">${escapeHtml(pdf.campaign)}</span>` : ''}
                ${pageLabel ? `<span class="tag tag-pages">${pageLabel}</span>` : ''}
            </div>
        </div>
    `;

    card.addEventListener('click', () => openPdfModal(pdf));

    return card;
}

// Open the PDF detail modal
function openPdfModal(pdf) {
    const modal = document.getElementById('pdfModal');

    document.getElementById('editPdfId').value = pdf.id;
    document.getElementById('pdfModalCover').src = `/api/pdf-thumbnail/${pdf.id}`;
    document.getElementById('pdfModalTitle').textContent = pdf.name || pdf.filename;
    document.getElementById('pdfModalFilename').textContent = pdf.filename;
    document.getElementById('pdfModalPageCount').textContent = pdf.page_count || 'Unknown';
    document.getElementById('pdfModalDateAdded').textContent = formatDate(pdf.date_added);

    document.getElementById('editPdfName').value = pdf.name || '';
    document.getElementById('editPdfImageType').value = pdf.image_type || 'Handout';
    document.getElementById('editPdfSource').value = pdf.source || '';
    document.getElementById('editPdfCampaign').value = pdf.campaign || '';
    document.getElementById('editPdfNotes').value = pdf.notes || '';

    const filePathLink = document.getElementById('pdfModalFilePath');
    const filePathText = document.getElementById('pdfModalFilePathText');
    filePathText.textContent = pdf.filepath;
    filePathLink.dataset.filepath = pdf.filepath;

    const showInFinderBtn = document.getElementById('pdfShowInFinderBtn');
    if (isElectron && window.electronAPI && window.electronAPI.showItemInFolder) {
        showInFinderBtn.style.display = 'inline-block';
    } else {
        showInFinderBtn.style.display = 'none';
    }

    const openBtn = document.getElementById('pdfOpenBtn');
    openBtn.dataset.filepath = pdf.filepath;
    openBtn.dataset.pdfId = pdf.id;

    modal.style.display = 'flex';
}

// Handle PDF update
async function handlePdfUpdate(e) {
    e.preventDefault();

    const pdfId = document.getElementById('editPdfId').value;

    const updateData = {
        Name: document.getElementById('editPdfName').value,
        ImageType: document.getElementById('editPdfImageType').value,
        Source: document.getElementById('editPdfSource').value,
        Campaign: document.getElementById('editPdfCampaign').value,
        Notes: document.getElementById('editPdfNotes').value
    };

    try {
        const response = await fetch(`/api/pdfs/${pdfId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData)
        });

        const data = await response.json();

        if (data.success) {
            closeModals();
            loadPdfFiles();
            loadPdfFilterOptions();
            showNotification('PDF updated successfully');
        } else {
            showError(data.error || 'Failed to update PDF');
        }
    } catch (error) {
        showError('Error updating PDF: ' + error.message);
    }
}

// Handle PDF delete
async function handlePdfDelete() {
    const pdfId = document.getElementById('editPdfId').value;

    if (!confirm('Are you sure you want to delete this PDF? This will delete the file permanently.')) {
        return;
    }

    try {
        const response = await fetch(`/api/pdfs/${pdfId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            closeModals();
            loadPdfFiles();
            showNotification('PDF deleted successfully');
        } else {
            showError(data.error || 'Failed to delete PDF');
        }
    } catch (error) {
        showError('Error deleting PDF: ' + error.message);
    }
}

// Handle PDF file path link click (copy to clipboard)
async function handlePdfFilePathClick(e) {
    e.preventDefault();
    e.stopPropagation();

    const filepath = e.currentTarget.dataset.filepath;
    if (!filepath) return;

    try {
        await navigator.clipboard.writeText(filepath);
        showSuccess('Path copied to clipboard');
    } catch (error) {
        const textArea = document.createElement('textarea');
        textArea.value = filepath;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        showSuccess('Path copied to clipboard');
    }
}

// Handle PDF "Show in Finder" button click
async function handlePdfShowInFinder(e) {
    e.preventDefault();
    e.stopPropagation();

    const filepath = document.getElementById('pdfModalFilePath').dataset.filepath;

    if (!filepath) {
        showError('No file path available');
        return;
    }

    if (!window.electronAPI || !window.electronAPI.showItemInFolder) {
        showError('This feature is only available in desktop mode');
        return;
    }

    try {
        const result = await window.electronAPI.showItemInFolder(filepath);
        if (result.success) {
            showSuccess('Opening file location...');
        } else {
            showError(`Failed to open: ${result.error}`);
        }
    } catch (error) {
        showError(`Error: ${error.message}`);
    }
}

// Handle PDF "Open PDF" button click - Electron opens system viewer, browser opens a new tab
async function handlePdfOpen(e) {
    e.preventDefault();

    const btn = e.currentTarget;
    const filepath = btn.dataset.filepath;
    const pdfId = btn.dataset.pdfId;

    if (isElectron && window.electronAPI && window.electronAPI.openFile) {
        try {
            const result = await window.electronAPI.openFile(filepath);
            if (!result.success) {
                showError(`Failed to open PDF: ${result.error}`);
            }
        } catch (error) {
            showError(`Error opening PDF: ${error.message}`);
        }
    } else {
        window.open(`/api/pdf/${pdfId}`, '_blank');
    }
}

// Setup PDF drop zone
function setupPdfDropZone() {
    const dropZone = document.getElementById('pdfDropZone');
    if (!dropZone) return;

    dropZone.addEventListener('click', () => {
        document.getElementById('pdfFileInput').click();
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');

        const files = Array.from(e.dataTransfer.files).filter(f =>
            f.name.match(/\.pdf$/i)
        );

        if (files.length > 0) {
            pendingPdfUploadFiles = files;
            showPdfFileList(files);
        }
    });
}

// Handle PDF file selection
function handlePdfFileSelect(e) {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
        pendingPdfUploadFiles = files;
        showPdfFileList(files);
    }
}

// Show selected PDF files
function showPdfFileList(files) {
    const listEl = document.getElementById('pdfFileList');
    const submitBtn = document.getElementById('uploadPdfSubmitBtn');

    listEl.innerHTML = files.map(f => `
        <div class="audio-file-item">
            <span class="audio-file-icon">📄</span>
            <span class="audio-file-name">${escapeHtml(f.name)}</span>
            <span class="audio-file-size">${formatFileSize(f.size)}</span>
        </div>
    `).join('');

    listEl.style.display = 'block';
    submitBtn.disabled = false;
}

// Handle PDF upload (Electron reference-mode add, same pattern as image upload)
async function handlePdfUpload(e) {
    e.preventDefault();

    if (!pendingPdfUploadFiles || pendingPdfUploadFiles.length === 0) {
        showError('No files selected');
        return;
    }

    if (pdfUploadInProgress) {
        showNotification('Upload already in progress...', 'info');
        return;
    }

    pdfUploadInProgress = true;
    const submitBtn = document.getElementById('uploadPdfSubmitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Uploading...';

    const imageType = document.getElementById('uploadPdfImageType').value;
    const tags = {};
    const source = document.getElementById('uploadPdfSource').value;
    const campaign = document.getElementById('uploadPdfCampaign').value;
    if (source) tags.Source = source;
    if (campaign) tags.Campaign = campaign;

    try {
        showNotification('Adding PDF references...', 'info');

        const filePaths = getFilePaths(pendingPdfUploadFiles);
        await addPdfReferencesDirectly(filePaths, imageType, tags);

        closeModals();
        resetPdfUploadModal();
        loadPdfFiles();
        loadPdfFilterOptions();
    } catch (error) {
        showError('Error uploading PDFs: ' + error.message);
    } finally {
        pdfUploadInProgress = false;
        submitBtn.disabled = false;
        submitBtn.textContent = 'Upload';
    }
}

// Add PDF file references by path (Reference Mode)
async function addPdfReferencesDirectly(filePaths, imageType, tags = {}) {
    const results = { added: 0, errors: 0, error_files: [] };

    for (const { file, path } of filePaths) {
        try {
            const response = await fetch('/api/pdfs/add-reference', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filepath: path,
                    image_type: imageType,
                    ...tags
                })
            });

            const data = await response.json();

            if (data.success) {
                results.added++;
            } else {
                results.errors++;
                results.error_files.push(file.name);
            }
        } catch (error) {
            results.errors++;
            results.error_files.push(file.name);
            console.error(`Error adding reference for ${file.name}:`, error);
        }
    }

    if (results.added > 0) {
        showSuccess(`Referenced ${results.added} PDF${results.added !== 1 ? 's' : ''} in place`);
    }
    if (results.errors > 0) {
        showError(`Failed to reference ${results.errors} PDF${results.errors !== 1 ? 's' : ''}: ${results.error_files.join(', ')}`);
    }
}

// Reset the PDF upload modal state
function resetPdfUploadModal() {
    pendingPdfUploadFiles = null;
    const listEl = document.getElementById('pdfFileList');
    const submitBtn = document.getElementById('uploadPdfSubmitBtn');
    if (listEl) listEl.style.display = 'none';
    if (submitBtn) submitBtn.disabled = true;
    const pdfFileInput = document.getElementById('pdfFileInput');
    if (pdfFileInput) pdfFileInput.value = '';
    document.getElementById('uploadPdfSource').value = '';
    document.getElementById('uploadPdfCampaign').value = '';
}

// Load PDF filter dropdown options (source/campaign)
async function loadPdfFilterOptions() {
    try {
        const sourceSelect = document.getElementById('pdfSourceFilter');
        const campaignSelect = document.getElementById('pdfCampaignFilter');

        const [sourceRes, campaignRes] = await Promise.all([
            fetch('/api/pdfs/tags/source'),
            fetch('/api/pdfs/tags/campaign')
        ]);
        const sourceData = await sourceRes.json();
        const campaignData = await campaignRes.json();

        if (sourceSelect && sourceData.success) {
            populatePdfFilterSelect(sourceSelect, sourceData.values || [], currentPdfFilters.source);
        }
        if (campaignSelect && campaignData.success) {
            populatePdfFilterSelect(campaignSelect, campaignData.values || [], currentPdfFilters.campaign);
        }
    } catch (error) {
        console.error('Error loading PDF filter options:', error);
    }
}

// Populate a simple single-select PDF filter dropdown, preserving its "All ..." first option
function populatePdfFilterSelect(select, values, currentValue) {
    const firstOption = select.options[0];
    select.innerHTML = '';
    select.appendChild(firstOption);
    values.forEach(value => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
    });
    select.value = currentValue || '';
}

// Handle PDF search input change
function handlePdfSearchChange(e) {
    currentPdfFilters.search = e.target.value;
    loadPdfFiles();
}

// Handle PDF image type filter change
function handlePdfTypeFilterChange(e) {
    currentPdfFilters.image_type = e.target.value;
    loadPdfFiles();
}

// Handle PDF source filter change
function handlePdfSourceFilterChange(e) {
    currentPdfFilters.source = e.target.value;
    loadPdfFiles();
}

// Handle PDF campaign filter change
function handlePdfCampaignFilterChange(e) {
    currentPdfFilters.campaign = e.target.value;
    loadPdfFiles();
}

// Handle PDF sort change
function handlePdfSortChange(e) {
    currentPdfFilters.sort_by = e.target.value;
    loadPdfFiles();
}

// Clear PDF filters
function clearPdfFilters() {
    currentPdfFilters = {
        search: '',
        image_type: '',
        source: '',
        campaign: '',
        sort_by: 'filename',
        sort_order: 'ASC'
    };

    document.getElementById('pdfSearchInput').value = '';
    document.getElementById('pdfTypeFilter').value = '';
    document.getElementById('pdfSourceFilter').value = '';
    document.getElementById('pdfCampaignFilter').value = '';
    document.getElementById('pdfSortBy').value = 'filename';

    loadPdfFiles();
}

// Update PDF tab count
function updatePdfTabCount() {
    const countEl = document.getElementById('pdfTabCount');
    if (countEl) {
        countEl.textContent = pdfFiles.length;
    }
}
