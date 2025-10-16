/**
 * Feedback Management Interface
 * Handles the feedback list, filtering, sorting, and detailed feedback view
 */

class FeedbackManager {
    constructor() {
        this.currentPage = 0;
        this.pageSize = 20;
        this.filters = {
            status: null,
            rating: null,
            search: ''
        };
        this.sortBy = 'created_at';
        this.sortOrder = 'desc';
        this.feedbackList = [];
        this.selectedFeedback = null;
    }

    async initialize() {
        this.setupEventListeners();
        await this.loadFeedbackList();
    }

    setupEventListeners() {
        // Filter controls
        document.getElementById('status-filter')?.addEventListener('change', (e) => {
            this.filters.status = e.target.value || null;
            this.currentPage = 0;
            this.loadFeedbackList();
        });

        document.getElementById('rating-filter')?.addEventListener('change', (e) => {
            this.filters.rating = e.target.value || null;
            this.currentPage = 0;
            this.loadFeedbackList();
        });

        document.getElementById('search-input')?.addEventListener('input', (e) => {
            this.filters.search = e.target.value;
            this.currentPage = 0;
            this.debounceSearch();
        });

        // Pagination
        document.getElementById('prev-page')?.addEventListener('click', () => {
            if (this.currentPage > 0) {
                this.currentPage--;
                this.loadFeedbackList();
            }
        });

        document.getElementById('next-page')?.addEventListener('click', () => {
            this.currentPage++;
            this.loadFeedbackList();
        });

        // Bulk actions
        document.getElementById('bulk-action-btn')?.addEventListener('click', () => {
            this.handleBulkAction();
        });

        // Modal close
        document.getElementById('close-modal')?.addEventListener('click', () => {
            this.closeFeedbackModal();
        });

        document.getElementById('feedback-modal')?.addEventListener('click', (e) => {
            if (e.target.id === 'feedback-modal') {
                this.closeFeedbackModal();
            }
        });
    }

    debounceSearch() {
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.loadFeedbackList();
        }, 300);
    }

    async loadFeedbackList() {
        try {
            this.showLoading();
            
            const params = new URLSearchParams({
                limit: this.pageSize.toString(),
                offset: (this.currentPage * this.pageSize).toString()
            });

            if (this.filters.status) params.append('status', this.filters.status);
            if (this.filters.rating) params.append('rating_filter', this.filters.rating);
            if (this.filters.search) params.append('search', this.filters.search);

            const response = await fetch(`/api/admin/feedback?${params}`);
            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            this.feedbackList = data.feedback;
            this.renderFeedbackList();
            this.updatePaginationControls(data.pagination);

        } catch (error) {
            console.error('Failed to load feedback list:', error);
            this.showError('Failed to load feedback list');
        }
    }

    showLoading() {
        const container = document.getElementById('feedback-list');
        if (container) {
            container.innerHTML = `
                <div class="loading-state">
                    <div class="spinner"></div>
                    <span>Loading feedback...</span>
                </div>
            `;
        }
    }

    renderFeedbackList() {
        const container = document.getElementById('feedback-list');
        if (!container) return;

        if (this.feedbackList.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <h3>No feedback found</h3>
                    <p>No feedback matches your current filters.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.feedbackList.map(feedback => `
            <div class="feedback-item" data-id="${feedback.id}">
                <div class="feedback-header">
                    <div class="feedback-meta">
                        <input type="checkbox" class="feedback-checkbox" value="${feedback.id}">
                        <span class="feedback-id">#${feedback.id}</span>
                        <span class="feedback-date">${this.formatDate(feedback.created_at)}</span>
                    </div>
                    <div class="feedback-status">
                        <span class="status-badge status-${feedback.status || 'new'}">${feedback.status || 'new'}</span>
                        ${this.renderRating(feedback.rating)}
                    </div>
                </div>
                
                <div class="feedback-content">
                    <div class="feedback-query">
                        <strong>Query:</strong> ${this.truncateText(feedback.query_text, 100)}
                    </div>
                    
                    <div class="feedback-indicators">
                        ${feedback.is_accurate !== null ? `
                            <span class="indicator ${feedback.is_accurate ? 'accurate' : 'inaccurate'}">
                                <i class="fas ${feedback.is_accurate ? 'fa-check' : 'fa-times'}"></i>
                                ${feedback.is_accurate ? 'Accurate' : 'Inaccurate'}
                            </span>
                        ` : ''}
                        
                        ${feedback.is_helpful !== null ? `
                            <span class="indicator ${feedback.is_helpful ? 'helpful' : 'not-helpful'}">
                                <i class="fas ${feedback.is_helpful ? 'fa-thumbs-up' : 'fa-thumbs-down'}"></i>
                                ${feedback.is_helpful ? 'Helpful' : 'Not Helpful'}
                            </span>
                        ` : ''}
                    </div>
                    
                    ${feedback.admin_notes ? `
                        <div class="admin-notes">
                            <i class="fas fa-sticky-note"></i>
                            <span>${this.truncateText(feedback.admin_notes, 80)}</span>
                        </div>
                    ` : ''}
                </div>
                
                <div class="feedback-actions">
                    <button class="action-btn view-btn" onclick="feedbackManager.viewFeedback(${feedback.id})">
                        <i class="fas fa-eye"></i>
                        View Details
                    </button>
                    <button class="action-btn edit-btn" onclick="feedbackManager.editFeedback(${feedback.id})">
                        <i class="fas fa-edit"></i>
                        Edit
                    </button>
                </div>
            </div>
        `).join('');
    }

    renderRating(rating) {
        if (!rating) return '<span class="no-rating">No rating</span>';
        
        const stars = Array.from({length: 5}, (_, i) => {
            const filled = i < rating;
            return `<i class="fas fa-star ${filled ? 'filled' : 'empty'}"></i>`;
        }).join('');
        
        return `<div class="rating-display">${stars}</div>`;
    }

    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }

    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    updatePaginationControls(pagination) {
        const prevBtn = document.getElementById('prev-page');
        const nextBtn = document.getElementById('next-page');
        const pageInfo = document.getElementById('page-info');

        if (prevBtn) prevBtn.disabled = this.currentPage === 0;
        if (nextBtn) nextBtn.disabled = !pagination.has_more;
        
        if (pageInfo) {
            const start = this.currentPage * this.pageSize + 1;
            const end = start + this.feedbackList.length - 1;
            pageInfo.textContent = `Showing ${start}-${end}`;
        }
    }

    async viewFeedback(feedbackId) {
        try {
            const response = await fetch(`/api/admin/feedback/${feedbackId}`);
            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            this.selectedFeedback = data.feedback;
            this.showFeedbackModal(false); // View mode
        } catch (error) {
            console.error('Failed to load feedback details:', error);
            this.showError('Failed to load feedback details');
        }
    }

    async editFeedback(feedbackId) {
        try {
            const response = await fetch(`/api/admin/feedback/${feedbackId}`);
            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            this.selectedFeedback = data.feedback;
            this.showFeedbackModal(true); // Edit mode
        } catch (error) {
            console.error('Failed to load feedback details:', error);
            this.showError('Failed to load feedback details');
        }
    }

    showFeedbackModal(editMode = false) {
        const modal = document.getElementById('feedback-modal');
        const content = document.getElementById('modal-content');
        
        if (!modal || !content || !this.selectedFeedback) return;

        content.innerHTML = this.renderFeedbackDetail(editMode);
        modal.style.display = 'flex';
        
        if (editMode) {
            this.setupModalEventListeners();
        }
    }

    renderFeedbackDetail(editMode) {
        const feedback = this.selectedFeedback;
        
        return `
            <div class="modal-header">
                <h2>Feedback Details #${feedback.id}</h2>
                <button id="close-modal" class="close-btn">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div class="modal-body">
                <div class="feedback-detail-grid">
                    <div class="detail-section">
                        <h3>User Query</h3>
                        <div class="detail-content">
                            <p>${feedback.query_text}</p>
                        </div>
                    </div>
                    
                    <div class="detail-section">
                        <h3>System Response</h3>
                        <div class="detail-content">
                            <p>${feedback.response_text || 'No response recorded'}</p>
                        </div>
                    </div>
                    
                    <div class="detail-section">
                        <h3>User Feedback</h3>
                        <div class="detail-content">
                            <div class="feedback-metrics">
                                <div class="metric">
                                    <label>Rating:</label>
                                    <span>${this.renderRating(feedback.rating)}</span>
                                </div>
                                <div class="metric">
                                    <label>Accurate:</label>
                                    <span class="${feedback.is_accurate ? 'positive' : 'negative'}">
                                        ${feedback.is_accurate !== null ? (feedback.is_accurate ? 'Yes' : 'No') : 'Not specified'}
                                    </span>
                                </div>
                                <div class="metric">
                                    <label>Helpful:</label>
                                    <span class="${feedback.is_helpful ? 'positive' : 'negative'}">
                                        ${feedback.is_helpful !== null ? (feedback.is_helpful ? 'Yes' : 'No') : 'Not specified'}
                                    </span>
                                </div>
                            </div>
                            
                            ${feedback.missing_info ? `
                                <div class="feedback-text">
                                    <label>Missing Information:</label>
                                    <p>${feedback.missing_info}</p>
                                </div>
                            ` : ''}
                            
                            ${feedback.incorrect_info ? `
                                <div class="feedback-text">
                                    <label>Incorrect Information:</label>
                                    <p>${feedback.incorrect_info}</p>
                                </div>
                            ` : ''}
                            
                            ${feedback.comments ? `
                                <div class="feedback-text">
                                    <label>Comments:</label>
                                    <p>${feedback.comments}</p>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    
                    <div class="detail-section">
                        <h3>Admin Management</h3>
                        <div class="detail-content">
                            ${editMode ? `
                                <div class="form-group">
                                    <label for="status-select">Status:</label>
                                    <select id="status-select" class="form-control">
                                        <option value="new" ${feedback.status === 'new' ? 'selected' : ''}>New</option>
                                        <option value="reviewed" ${feedback.status === 'reviewed' ? 'selected' : ''}>Reviewed</option>
                                        <option value="addressed" ${feedback.status === 'addressed' ? 'selected' : ''}>Addressed</option>
                                    </select>
                                </div>
                                
                                <div class="form-group">
                                    <label for="admin-notes">Admin Notes:</label>
                                    <textarea id="admin-notes" class="form-control" rows="4" 
                                              placeholder="Add notes about this feedback...">${feedback.admin_notes || ''}</textarea>
                                </div>
                                
                                <div class="form-group">
                                    <label for="resolution-notes">Resolution Notes:</label>
                                    <textarea id="resolution-notes" class="form-control" rows="3" 
                                              placeholder="Describe how this issue was resolved...">${feedback.resolution_notes || ''}</textarea>
                                </div>
                            ` : `
                                <div class="readonly-field">
                                    <label>Status:</label>
                                    <span class="status-badge status-${feedback.status || 'new'}">${feedback.status || 'new'}</span>
                                </div>
                                
                                ${feedback.admin_notes ? `
                                    <div class="readonly-field">
                                        <label>Admin Notes:</label>
                                        <p>${feedback.admin_notes}</p>
                                    </div>
                                ` : ''}
                                
                                ${feedback.resolution_notes ? `
                                    <div class="readonly-field">
                                        <label>Resolution Notes:</label>
                                        <p>${feedback.resolution_notes}</p>
                                    </div>
                                ` : ''}
                            `}
                        </div>
                    </div>
                    
                    ${feedback.sources_used && feedback.sources_used.length > 0 ? `
                        <div class="detail-section">
                            <h3>Sources Used</h3>
                            <div class="detail-content">
                                <div class="sources-list">
                                    ${feedback.sources_used.map(source => `
                                        <div class="source-item">
                                            <i class="fas fa-file-alt"></i>
                                            <span>${source.source_file || source.title || 'Unknown source'}</span>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
            
            <div class="modal-footer">
                ${editMode ? `
                    <button class="btn btn-primary" onclick="feedbackManager.saveFeedback()">
                        <i class="fas fa-save"></i>
                        Save Changes
                    </button>
                    <button class="btn btn-secondary" onclick="feedbackManager.closeFeedbackModal()">
                        Cancel
                    </button>
                ` : `
                    <button class="btn btn-primary" onclick="feedbackManager.editFeedback(${feedback.id})">
                        <i class="fas fa-edit"></i>
                        Edit Feedback
                    </button>
                    <button class="btn btn-secondary" onclick="feedbackManager.closeFeedbackModal()">
                        Close
                    </button>
                `}
            </div>
        `;
    }

    setupModalEventListeners() {
        // Add any specific event listeners for the modal form
        document.getElementById('close-modal')?.addEventListener('click', () => {
            this.closeFeedbackModal();
        });
    }

    async saveFeedback() {
        try {
            const status = document.getElementById('status-select')?.value;
            const adminNotes = document.getElementById('admin-notes')?.value;
            const resolutionNotes = document.getElementById('resolution-notes')?.value;

            const updateData = {
                status,
                admin_notes: adminNotes,
                resolution_notes: resolutionNotes
            };

            const response = await fetch(`/api/admin/feedback/${this.selectedFeedback.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
            });

            const result = await response.json();

            if (result.error) {
                throw new Error(result.error);
            }

            this.closeFeedbackModal();
            await this.loadFeedbackList(); // Refresh the list
            this.showSuccess('Feedback updated successfully');

        } catch (error) {
            console.error('Failed to save feedback:', error);
            this.showError('Failed to save feedback changes');
        }
    }

    closeFeedbackModal() {
        const modal = document.getElementById('feedback-modal');
        if (modal) {
            modal.style.display = 'none';
        }
        this.selectedFeedback = null;
    }

    handleBulkAction() {
        const selectedIds = Array.from(document.querySelectorAll('.feedback-checkbox:checked'))
            .map(cb => cb.value);

        if (selectedIds.length === 0) {
            this.showError('Please select feedback items to perform bulk actions');
            return;
        }

        // For now, just show selected count
        this.showSuccess(`Selected ${selectedIds.length} feedback items`);
    }

    showError(message) {
        // Simple error notification - could be enhanced with a proper notification system
        console.error(message);
        alert('Error: ' + message);
    }

    showSuccess(message) {
        // Simple success notification - could be enhanced with a proper notification system
        console.log(message);
        // You could implement a toast notification here
    }
}

// Global instance
let feedbackManager;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    feedbackManager = new FeedbackManager();
});