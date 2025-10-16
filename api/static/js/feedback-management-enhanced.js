/**
 * Enhanced Feedback Management Interface
 * Extends the basic feedback management with advanced features
 */

class EnhancedFeedbackManager extends FeedbackManager {
  constructor() {
    super();
    this.selectedItems = new Set();
    this.summaryData = {};
    this.currentSort = 'created_at_desc';
    this.admins = ['admin1', 'admin2', 'admin3']; // This would come from API
  }

  async initialize() {
    await super.initialize();
    this.setupEnhancedEventListeners();
    await this.loadSummaryData();
  }

  setupEnhancedEventListeners() {
    // Select all checkbox
    document.getElementById('select-all-checkbox')?.addEventListener('change', (e) => {
      this.toggleSelectAll(e.target.checked);
    });

    // Sort controls
    document.getElementById('sort-select')?.addEventListener('change', (e) => {
      this.currentSort = e.target.value;
      this.currentPage = 0;
      this.loadFeedbackList();
    });

    // Accuracy filter
    document.getElementById('accuracy-filter')?.addEventListener('change', (e) => {
      this.filters.accuracy = e.target.value || null;
      this.currentPage = 0;
      this.loadFeedbackList();
    });

    // Bulk action button
    document.getElementById('bulk-action-btn')?.addEventListener('click', () => {
      this.toggleBulkDropdown();
    });

    // Modal close handlers
    document.getElementById('close-bulk-modal')?.addEventListener('click', () => {
      this.closeBulkActionModal();
    });

    document.getElementById('close-assignment-modal')?.addEventListener('click', () => {
      this.closeAssignmentModal();
    });

    // Click outside to close dropdowns
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.bulk-actions')) {
        this.closeBulkDropdown();
      }
    });
  }

  async loadSummaryData() {
    try {
      const response = await fetch('/api/admin/feedback/analytics?days=30');
      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      this.summaryData = data.analytics;
      this.updateSummaryCards();
    } catch (error) {
      console.error('Failed to load summary data:', error);
    }
  }

  updateSummaryCards() {
    const { basic_stats } = this.summaryData;
    if (!basic_stats) return;

    // Update metric cards
    this.updateMetricCard('total-feedback-count', basic_stats.total_feedback || 0);
    this.updateMetricCard('pending-feedback-count', 
      (basic_stats.new_count || 0) + (basic_stats.reviewed_count || 0));
    this.updateMetricCard('avg-rating-display', (basic_stats.avg_rating || 0).toFixed(1));
    this.updateMetricCard('resolved-feedback-count', basic_stats.addressed_count || 0);
  }

  updateMetricCard(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
      element.textContent = value;
    }
  }

  async loadFeedbackList() {
    try {
      this.showLoading();
      
      const params = new URLSearchParams({
        limit: this.pageSize.toString(),
        offset: (this.currentPage * this.pageSize).toString()
      });

      // Add filters
      if (this.filters.status) params.append('status', this.filters.status);
      if (this.filters.rating) params.append('rating_filter', this.filters.rating);
      if (this.filters.accuracy) params.append('accuracy_filter', this.filters.accuracy);
      if (this.filters.search) params.append('search', this.filters.search);

      // Add sorting
      const [sortField, sortOrder] = this.currentSort.split('_');
      params.append('sort_by', sortField);
      params.append('sort_order', sortOrder);

      const response = await fetch(`/api/admin/feedback?${params}`);
      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      this.feedbackList = data.feedback;
      this.renderEnhancedFeedbackList();
      this.updateEnhancedPaginationControls(data.pagination);
      this.updateBulkActionButton();

    } catch (error) {
      console.error('Failed to load feedback list:', error);
      this.showError('Failed to load feedback list');
    }
  }

  renderEnhancedFeedbackList() {
    const container = document.getElementById('feedback-list');
    if (!container) return;

    if (this.feedbackList.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-inbox"></i>
          <h3>No feedback found</h3>
          <p>No feedback matches your current filters. Try adjusting your search criteria.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = this.feedbackList.map(feedback => `
      <div class="feedback-item ${this.selectedItems.has(feedback.id) ? 'selected' : ''}" data-id="${feedback.id}">
        <div class="feedback-header">
          <div class="feedback-meta">
            <input type="checkbox" class="feedback-checkbox" value="${feedback.id}" 
                   ${this.selectedItems.has(feedback.id) ? 'checked' : ''}>
            <span class="feedback-id">#${feedback.id}</span>
            <span class="feedback-date">${this.formatDate(feedback.created_at)}</span>
            ${feedback.assigned_to ? `
              <span class="assigned-indicator">
                <i class="fas fa-user"></i>
                ${feedback.assigned_to}
              </span>
            ` : ''}
          </div>
          <div class="feedback-status">
            <span class="status-badge status-${feedback.status || 'new'}">${feedback.status || 'new'}</span>
            ${this.renderRating(feedback.rating)}
            ${this.renderPriorityIndicator(feedback)}
          </div>
        </div>
        
        <div class="feedback-content">
          <div class="feedback-query">
            <strong>Query:</strong> ${this.truncateText(feedback.query_text, 120)}
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

            ${feedback.missing_info ? `
              <span class="indicator warning">
                <i class="fas fa-exclamation-triangle"></i>
                Missing Info
              </span>
            ` : ''}

            ${feedback.incorrect_info ? `
              <span class="indicator error">
                <i class="fas fa-times-circle"></i>
                Incorrect Info
              </span>
            ` : ''}
          </div>
          
          ${feedback.admin_notes ? `
            <div class="admin-notes">
              <i class="fas fa-sticky-note"></i>
              <span>${this.truncateText(feedback.admin_notes, 100)}</span>
            </div>
          ` : ''}
        </div>
        
        <div class="feedback-actions">
          <button class="action-btn view-btn" onclick="enhancedFeedbackManager.viewFeedback(${feedback.id})">
            <i class="fas fa-eye"></i>
            View Details
          </button>
          <button class="action-btn edit-btn" onclick="enhancedFeedbackManager.editFeedback(${feedback.id})">
            <i class="fas fa-edit"></i>
            Edit
          </button>
          <button class="action-btn assign-btn" onclick="enhancedFeedbackManager.showAssignmentModal([${feedback.id}])">
            <i class="fas fa-user-plus"></i>
            Assign
          </button>
          ${feedback.status !== 'addressed' ? `
            <button class="action-btn resolve-btn" onclick="enhancedFeedbackManager.quickResolve(${feedback.id})">
              <i class="fas fa-check"></i>
              Resolve
            </button>
          ` : ''}
        </div>
      </div>
    `).join('');

    // Add event listeners for checkboxes
    container.querySelectorAll('.feedback-checkbox').forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        this.toggleItemSelection(parseInt(e.target.value), e.target.checked);
      });
    });
  }

  renderPriorityIndicator(feedback) {
    let priority = 'normal';
    let icon = 'fa-circle';
    let color = 'var(--text-muted)';

    // Determine priority based on feedback characteristics
    if (feedback.rating && feedback.rating <= 2) {
      priority = 'high';
      icon = 'fa-exclamation-circle';
      color = 'var(--error)';
    } else if (feedback.is_accurate === false || feedback.incorrect_info) {
      priority = 'high';
      icon = 'fa-exclamation-triangle';
      color = 'var(--warning)';
    } else if (feedback.missing_info) {
      priority = 'medium';
      icon = 'fa-info-circle';
      color = 'var(--info)';
    }

    return `
      <span class="priority-indicator priority-${priority}" title="Priority: ${priority}">
        <i class="fas ${icon}" style="color: ${color}"></i>
      </span>
    `;
  }

  updateEnhancedPaginationControls(pagination) {
    super.updatePaginationControls(pagination);
    
    // Add page numbers
    const pageNumbers = document.getElementById('page-numbers');
    if (pageNumbers) {
      const totalPages = Math.ceil(pagination.total / this.pageSize) || 1;
      const currentPage = this.currentPage + 1;
      
      let pageNumbersHtml = '';
      const maxVisiblePages = 5;
      let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
      let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
      
      if (endPage - startPage < maxVisiblePages - 1) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
      }

      for (let i = startPage; i <= endPage; i++) {
        pageNumbersHtml += `
          <button class="page-number-btn ${i === currentPage ? 'active' : ''}" 
                  onclick="enhancedFeedbackManager.goToPage(${i - 1})">
            ${i}
          </button>
        `;
      }
      
      pageNumbers.innerHTML = pageNumbersHtml;
    }
  }

  goToPage(pageNumber) {
    this.currentPage = pageNumber;
    this.loadFeedbackList();
  }

  toggleSelectAll(checked) {
    if (checked) {
      this.feedbackList.forEach(feedback => {
        this.selectedItems.add(feedback.id);
      });
    } else {
      this.selectedItems.clear();
    }
    
    // Update checkboxes
    document.querySelectorAll('.feedback-checkbox').forEach(checkbox => {
      checkbox.checked = checked;
    });
    
    this.updateBulkActionButton();
    this.updateSelectedItemsDisplay();
  }

  toggleItemSelection(itemId, selected) {
    if (selected) {
      this.selectedItems.add(itemId);
    } else {
      this.selectedItems.delete(itemId);
    }
    
    // Update select all checkbox
    const selectAllCheckbox = document.getElementById('select-all-checkbox');
    if (selectAllCheckbox) {
      selectAllCheckbox.checked = this.selectedItems.size === this.feedbackList.length;
      selectAllCheckbox.indeterminate = this.selectedItems.size > 0 && this.selectedItems.size < this.feedbackList.length;
    }
    
    this.updateBulkActionButton();
    this.updateSelectedItemsDisplay();
  }

  updateBulkActionButton() {
    const bulkActionBtn = document.getElementById('bulk-action-btn');
    if (bulkActionBtn) {
      bulkActionBtn.disabled = this.selectedItems.size === 0;
      bulkActionBtn.innerHTML = `
        <i class="fas fa-tasks"></i>
        <span>Bulk Actions (${this.selectedItems.size})</span>
      `;
    }
  }

  updateSelectedItemsDisplay() {
    // Update any UI elements that show selected items count
    document.querySelectorAll('.feedback-item').forEach(item => {
      const itemId = parseInt(item.dataset.id);
      item.classList.toggle('selected', this.selectedItems.has(itemId));
    });
  }

  toggleBulkDropdown() {
    const dropdown = document.getElementById('bulk-dropdown');
    if (dropdown) {
      dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
    }
  }

  closeBulkDropdown() {
    const dropdown = document.getElementById('bulk-dropdown');
    if (dropdown) {
      dropdown.style.display = 'none';
    }
  }

  async quickResolve(feedbackId) {
    try {
      const updateData = {
        status: 'addressed',
        admin_notes: 'Resolved via quick action',
        resolution_notes: 'Issue resolved'
      };

      const response = await fetch(`/api/admin/feedback/${feedbackId}`, {
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

      await this.loadFeedbackList();
      await this.loadSummaryData();
      this.showSuccess('Feedback resolved successfully');

    } catch (error) {
      console.error('Failed to resolve feedback:', error);
      this.showError('Failed to resolve feedback');
    }
  }

  showAssignmentModal(feedbackIds) {
    const modal = document.getElementById('assignment-modal');
    if (modal) {
      modal.style.display = 'flex';
      
      // Store the feedback IDs for assignment
      this.assignmentFeedbackIds = feedbackIds;
    }
  }

  closeAssignmentModal() {
    const modal = document.getElementById('assignment-modal');
    if (modal) {
      modal.style.display = 'none';
    }
    this.assignmentFeedbackIds = null;
  }

  async confirmAssignment() {
    try {
      const assignTo = document.getElementById('assign-to-select')?.value;
      const notes = document.getElementById('assignment-notes')?.value;

      if (!assignTo) {
        this.showError('Please select an admin to assign to');
        return;
      }

      const updateData = {
        assigned_to: assignTo,
        admin_notes: notes || `Assigned to ${assignTo}`,
        status: 'reviewed'
      };

      // Update all selected feedback items
      const promises = this.assignmentFeedbackIds.map(id =>
        fetch(`/api/admin/feedback/${id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(updateData)
        })
      );

      await Promise.all(promises);

      this.closeAssignmentModal();
      await this.loadFeedbackList();
      await this.loadSummaryData();
      this.showSuccess(`Assigned ${this.assignmentFeedbackIds.length} feedback items to ${assignTo}`);

    } catch (error) {
      console.error('Failed to assign feedback:', error);
      this.showError('Failed to assign feedback');
    }
  }

  showBulkActionModal(action, selectedIds) {
    const modal = document.getElementById('bulk-action-modal');
    const content = document.getElementById('bulk-action-content');
    
    if (!modal || !content) return;

    let modalContent = '';
    
    switch (action) {
      case 'status':
        modalContent = `
          <div class="form-group">
            <label for="bulk-status-select">New Status:</label>
            <select id="bulk-status-select" class="form-control">
              <option value="reviewed">Reviewed</option>
              <option value="addressed">Addressed</option>
            </select>
          </div>
          <div class="form-group">
            <label for="bulk-notes">Notes:</label>
            <textarea id="bulk-notes" class="form-control" rows="3" 
                      placeholder="Add notes for this bulk action..."></textarea>
          </div>
          <p>This will update ${selectedIds.length} feedback items.</p>
        `;
        break;
      
      case 'assign':
        modalContent = `
          <div class="form-group">
            <label for="bulk-assign-select">Assign to:</label>
            <select id="bulk-assign-select" class="form-control">
              ${this.admins.map(admin => `<option value="${admin}">${admin}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label for="bulk-assign-notes">Assignment Notes:</label>
            <textarea id="bulk-assign-notes" class="form-control" rows="3" 
                      placeholder="Add notes for this assignment..."></textarea>
          </div>
          <p>This will assign ${selectedIds.length} feedback items.</p>
        `;
        break;
    }
    
    content.innerHTML = modalContent;
    modal.style.display = 'flex';
    
    // Store action and IDs for confirmation
    this.bulkAction = { action, selectedIds };
  }

  closeBulkActionModal() {
    const modal = document.getElementById('bulk-action-modal');
    if (modal) {
      modal.style.display = 'none';
    }
    this.bulkAction = null;
  }

  // Filter helper functions
  filterByStatus(status) {
    document.getElementById('status-filter').value = status;
    this.filters.status = status;
    this.currentPage = 0;
    this.loadFeedbackList();
  }

  filterByRating(rating) {
    document.getElementById('rating-filter').value = rating;
    this.filters.rating = rating;
    this.currentPage = 0;
    this.loadFeedbackList();
  }

  filterByAccuracy(accuracy) {
    document.getElementById('accuracy-filter').value = accuracy;
    this.filters.accuracy = accuracy;
    this.currentPage = 0;
    this.loadFeedbackList();
  }

  showFeedbackAnalytics() {
    // Navigate to enhanced analytics page
    window.location.href = '/analytics-enhanced';
  }

  async exportFeedbackData() {
    try {
      const params = new URLSearchParams();
      if (this.filters.status) params.append('status', this.filters.status);
      if (this.filters.rating) params.append('rating_filter', this.filters.rating);
      if (this.filters.accuracy) params.append('accuracy_filter', this.filters.accuracy);
      if (this.filters.search) params.append('search', this.filters.search);
      
      // Add export format
      params.append('format', 'csv');
      params.append('limit', '1000'); // Export more items

      const response = await fetch(`/api/admin/feedback/export?${params}`);
      
      if (!response.ok) {
        throw new Error('Export failed');
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `feedback-export-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      this.showSuccess('Feedback data exported successfully');

    } catch (error) {
      console.error('Failed to export feedback data:', error);
      this.showError('Failed to export feedback data');
    }
  }
}

// Global functions for bulk actions
function bulkUpdateStatus(status) {
  if (enhancedFeedbackManager && enhancedFeedbackManager.selectedItems.size > 0) {
    enhancedFeedbackManager.showBulkActionModal('status', Array.from(enhancedFeedbackManager.selectedItems));
  }
}

function bulkAssign() {
  if (enhancedFeedbackManager && enhancedFeedbackManager.selectedItems.size > 0) {
    enhancedFeedbackManager.showAssignmentModal(Array.from(enhancedFeedbackManager.selectedItems));
  }
}

function bulkExport() {
  if (enhancedFeedbackManager && enhancedFeedbackManager.selectedItems.size > 0) {
    enhancedFeedbackManager.exportSelectedFeedback();
  }
}

function refreshFeedbackData() {
  if (enhancedFeedbackManager) {
    enhancedFeedbackManager.loadFeedbackList();
    enhancedFeedbackManager.loadSummaryData();
  }
}

function exportFeedbackData() {
  if (enhancedFeedbackManager) {
    enhancedFeedbackManager.exportFeedbackData();
  }
}

// Quick filter functions
function filterByStatus(status) {
  if (enhancedFeedbackManager) {
    enhancedFeedbackManager.filterByStatus(status);
  }
}

function filterByRating(rating) {
  if (enhancedFeedbackManager) {
    enhancedFeedbackManager.filterByRating(rating);
  }
}

function filterByAccuracy(accuracy) {
  if (enhancedFeedbackManager) {
    enhancedFeedbackManager.filterByAccuracy(accuracy);
  }
}

function showFeedbackAnalytics() {
  if (enhancedFeedbackManager) {
    enhancedFeedbackManager.showFeedbackAnalytics();
  }
}

function confirmAssignment() {
  if (enhancedFeedbackManager) {
    enhancedFeedbackManager.confirmAssignment();
  }
}

function closeAssignmentModal() {
  if (enhancedFeedbackManager) {
    enhancedFeedbackManager.closeAssignmentModal();
  }
}

function closeBulkActionModal() {
  if (enhancedFeedbackManager) {
    enhancedFeedbackManager.closeBulkActionModal();
  }
}

// Global instance
let enhancedFeedbackManager;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  enhancedFeedbackManager = new EnhancedFeedbackManager();
  enhancedFeedbackManager.initialize();
});