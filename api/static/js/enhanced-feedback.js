/**
 * Enhanced Feedback System
 * Consolidated feedback modal and rating components for better performance
 */

// ==========================================================================
// RATING COMPONENTS (Consolidated from rating-components.js)
// ==========================================================================

class StarRatingComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = {
      maxRating: 5,
      allowHalf: false,
      size: 'medium',
      showLabels: true,
      interactive: true,
      ...options
    };

    this.currentRating = 0;
    this.hoverRating = 0;
    this.onChange = options.onChange || (() => { });

    this.render();
    this.attachEventListeners();
  }

  render() {
    const sizeClass = `star-rating-${this.options.size}`;
    const interactiveClass = this.options.interactive ? 'interactive' : 'readonly';

    this.container.innerHTML = `
      <div class="star-rating-component ${sizeClass} ${interactiveClass}">
        <div class="stars-container" role="radiogroup" aria-label="Rating from 1 to ${this.options.maxRating} stars">
          ${this.renderStars()}
        </div>
        ${this.options.showLabels ? this.renderLabels() : ''}
        <div class="rating-value" aria-live="polite"></div>
      </div>
    `;

    this.starsContainer = this.container.querySelector('.stars-container');
    this.ratingValue = this.container.querySelector('.rating-value');
  }

  renderStars() {
    let starsHTML = '';
    for (let i = 1; i <= this.options.maxRating; i++) {
      starsHTML += `
        <button 
          class="star-button" 
          data-rating="${i}"
          role="radio"
          aria-checked="false"
          aria-label="${i} star${i !== 1 ? 's' : ''}"
          tabindex="${i === 1 ? '0' : '-1'}"
          ${!this.options.interactive ? 'disabled' : ''}
        >
          <i class="fas fa-star star-icon" aria-hidden="true"></i>
          <i class="far fa-star star-outline" aria-hidden="true"></i>
        </button>
      `;
    }
    return starsHTML;
  }

  renderLabels() {
    return `
      <div class="rating-labels">
        <span class="label-poor">Poor</span>
        <span class="label-excellent">Excellent</span>
      </div>
    `;
  }

  attachEventListeners() {
    if (!this.options.interactive) return;

    const stars = this.starsContainer.querySelectorAll('.star-button');

    stars.forEach((star, index) => {
      star.addEventListener('click', (e) => {
        e.preventDefault();
        const rating = parseInt(star.dataset.rating);
        this.setRating(rating);
      });

      star.addEventListener('mouseenter', () => {
        const rating = parseInt(star.dataset.rating);
        this.setHoverRating(rating);
      });

      star.addEventListener('mouseleave', () => {
        this.setHoverRating(0);
      });
    });

    this.starsContainer.addEventListener('mouseleave', () => {
      this.setHoverRating(0);
    });
  }

  setRating(rating) {
    this.currentRating = rating;
    this.updateVisualState();
    this.updateAriaStates();
    this.updateRatingValue();
    this.onChange(rating);
  }

  setHoverRating(rating) {
    this.hoverRating = rating;
    this.updateVisualState();
  }

  updateVisualState() {
    const stars = this.starsContainer.querySelectorAll('.star-button');
    const activeRating = this.hoverRating || this.currentRating;

    stars.forEach((star, index) => {
      const starRating = index + 1;
      const isActive = starRating <= activeRating;

      star.classList.toggle('active', isActive);
      star.classList.toggle('hovered', this.hoverRating > 0 && starRating <= this.hoverRating);
    });
  }

  updateAriaStates() {
    const stars = this.starsContainer.querySelectorAll('.star-button');
    stars.forEach((star, index) => {
      const starRating = index + 1;
      star.setAttribute('aria-checked', starRating === this.currentRating ? 'true' : 'false');
    });
  }

  updateRatingValue() {
    if (this.currentRating > 0) {
      const messages = {
        1: "Poor - This response didn't meet expectations",
        2: "Fair - This response had some issues",
        3: "Good - This response was adequate",
        4: "Very Good - This response was helpful",
        5: "Excellent - This response was perfect"
      };

      this.ratingValue.textContent = messages[this.currentRating] || `${this.currentRating} stars`;
      this.ratingValue.style.display = 'block';
    } else {
      this.ratingValue.style.display = 'none';
    }
  }

  getRating() {
    return this.currentRating;
  }

  reset() {
    this.currentRating = 0;
    this.hoverRating = 0;
    this.updateVisualState();
    this.updateAriaStates();
    this.updateRatingValue();
  }
}

// Export components to global scope
window.StarRatingComponent = StarRatingComponent;

// ==========================================================================
// ENHANCED FEEDBACK MODAL
// ==========================================================================

class EnhancedFeedbackModal {
  constructor() {
    this.currentStep = 1;
    this.maxSteps = 3;
    this.feedbackData = {};
    this.isVisible = false;

    // Bind methods
    this.show = this.show.bind(this);
    this.hide = this.hide.bind(this);
    this.nextStep = this.nextStep.bind(this);
    this.prevStep = this.prevStep.bind(this);
    this.submitFeedback = this.submitFeedback.bind(this);

    // Initialize keyboard event handlers
    this.handleKeydown = this.handleKeydown.bind(this);
  }

  /**
   * Show the feedback modal with progressive disclosure
   */
  show(queryText, responseText, sources) {
    this.feedbackData = {
      queryText,
      responseText,
      sources,
      timestamp: new Date().toISOString()
    };

    this.currentStep = 1;
    this.render();
    this.isVisible = true;

    // Add keyboard event listener
    document.addEventListener('keydown', this.handleKeydown);

    // Add resize event listener
    window.addEventListener('resize', this.handleResize.bind(this));

    // Focus management
    setTimeout(() => {
      const firstFocusable = this.modal.querySelector('[tabindex="0"], button, input, textarea, select');
      if (firstFocusable) {
        firstFocusable.focus();
      }
    }, 100);

    // Announce to screen readers
    this.announceToScreenReader('Feedback modal opened. Please rate your experience.');
  }

  /**
   * Hide the feedback modal
   */
  hide() {
    if (this.overlay) {
      // Smooth fade out animation
      this.overlay.style.opacity = '0';
      setTimeout(() => {
        if (this.overlay && this.overlay.parentNode) {
          this.overlay.parentNode.removeChild(this.overlay);
        }
      }, 200);
    }

    this.isVisible = false;
    document.removeEventListener('keydown', this.handleKeydown);
    window.removeEventListener('resize', this.handleResize.bind(this));

    // Return focus to the feedback trigger
    const feedbackTrigger = document.querySelector('.feedback-link');
    if (feedbackTrigger) {
      feedbackTrigger.focus();
    }
  }

  /**
   * Handle keyboard navigation
   */
  handleKeydown(event) {
    if (!this.isVisible) return;

    switch (event.key) {
      case 'Escape':
        event.preventDefault();
        this.hide();
        break;
      case 'Tab':
        this.handleTabNavigation(event);
        break;
      case 'Enter':
        if (event.target.classList.contains('feedback-next-btn')) {
          event.preventDefault();
          this.nextStep();
        } else if (event.target.classList.contains('feedback-submit-btn')) {
          event.preventDefault();
          this.submitFeedback();
        }
        break;
    }
  }

  /**
   * Handle tab navigation within modal
   */
  handleTabNavigation(event) {
    const focusableElements = this.modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    if (event.shiftKey) {
      if (document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      }
    } else {
      if (document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    }
  }

  /**
   * Move to next step in progressive disclosure
   */
  nextStep() {
    if (this.currentStep < this.maxSteps && this.validateCurrentStep()) {
      this.currentStep++;
      this.updateStepContent();
      this.announceToScreenReader(`Step ${this.currentStep} of ${this.maxSteps}`);
    }
  }

  /**
   * Move to previous step
   */
  prevStep() {
    if (this.currentStep > 1) {
      this.currentStep--;
      this.updateStepContent();
      this.announceToScreenReader(`Step ${this.currentStep} of ${this.maxSteps}`);
    }
  }

  /**
   * Validate current step before proceeding
   */
  validateCurrentStep() {
    switch (this.currentStep) {
      case 1:
        return this.feedbackData.overallRating !== undefined;
      case 2:
        return true; // Quick feedback is optional
      case 3:
        return true; // Detailed feedback is optional
      default:
        return true;
    }
  }

  /**
   * Render the complete modal structure
   */
  render() {
    const modalHTML = `
      <div class="enhanced-feedback-overlay" role="dialog" aria-modal="true" aria-labelledby="feedback-title">
        <div class="enhanced-feedback-modal">
          <div class="feedback-header">
            <h2 id="feedback-title" class="feedback-title">Share Your Feedback</h2>
            <div class="feedback-progress">
              <div class="progress-bar">
                <div class="progress-fill" style="width: ${(this.currentStep / this.maxSteps) * 100}%"></div>
              </div>
              <span class="progress-text" aria-live="polite">Step ${this.currentStep} of ${this.maxSteps}</span>
            </div>
            <button class="feedback-close-btn" aria-label="Close feedback modal" tabindex="0">
              <i class="fas fa-times" aria-hidden="true"></i>
            </button>
          </div>
          
          <div class="feedback-content">
            ${this.renderStepContent()}
          </div>
          
          <div class="feedback-actions">
            ${this.renderActionButtons()}
          </div>
        </div>
      </div>
    `;

    // Remove existing modal if present
    const existingModal = document.querySelector('.enhanced-feedback-overlay');
    if (existingModal) {
      existingModal.remove();
    }

    // Add new modal to DOM
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Store references
    this.overlay = document.querySelector('.enhanced-feedback-overlay');
    this.modal = document.querySelector('.enhanced-feedback-modal');

    // Add event listeners
    this.attachEventListeners();

    // Animate in with improved timing
    requestAnimationFrame(() => {
      this.overlay.style.opacity = '1';

      // Stagger the modal animation slightly for better UX
      setTimeout(() => {
        this.modal.style.transform = 'translate(-50%, -50%) scale(1)';
        this.adjustModalSize();

        // Add a subtle bounce effect
        this.modal.style.animation = 'modalBounceIn 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)';

        // Remove animation class after completion
        setTimeout(() => {
          this.modal.style.animation = '';
        }, 400);
      }, 50);
    });
  }

  /**
   * Adjust modal size for different screen sizes
   */
  adjustModalSize() {
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;

    // Remove any inline styles to let CSS handle responsiveness
    this.modal.style.width = '';
    this.modal.style.maxWidth = '';
    this.modal.style.maxHeight = '';

    // Add responsive classes based on viewport
    this.modal.classList.remove('mobile', 'tablet', 'landscape');

    if (viewportWidth <= 480) {
      this.modal.classList.add('mobile');
    } else if (viewportWidth <= 768) {
      this.modal.classList.add('tablet');
    }

    if (viewportHeight <= 600 && viewportWidth > viewportHeight) {
      this.modal.classList.add('landscape');
    }

    // Ensure proper positioning
    this.modal.style.position = 'fixed';
    this.modal.style.top = '50%';
    this.modal.style.left = '50%';
    this.modal.style.transform = 'translate(-50%, -50%)';

    // Smooth scroll to top of modal content if needed
    const content = this.modal.querySelector('.feedback-content');
    if (content) {
      content.scrollTop = 0;
    }
  }

  /**
   * Handle window resize
   */
  handleResize() {
    if (this.isVisible && this.modal) {
      this.adjustModalSize();
    }
  }

  /**
   * Render content for current step
   */
  renderStepContent() {
    switch (this.currentStep) {
      case 1:
        return this.renderStep1();
      case 2:
        return this.renderStep2();
      case 3:
        return this.renderStep3();
      default:
        return '';
    }
  }

  /**
   * Step 1: Overall Rating (Required)
   */
  renderStep1() {
    return `
      <div class="feedback-step" data-step="1">
        <div class="step-header">
          <h3 class="step-title">How would you rate this response?</h3>
          <p class="step-description">Your rating helps us understand response quality</p>
        </div>
        
        <div class="rating-container" id="starRatingContainer">
          <!-- Star rating component will be initialized here -->
        </div>
      </div>
    `;
  }

  /**
   * Step 2: Quick Feedback (Optional)
   */
  renderStep2() {
    return `
      <div class="feedback-step" data-step="2">
        <div class="step-header">
          <h3 class="step-title">Quick feedback</h3>
          <p class="step-description">Help us understand what worked well or needs improvement</p>
        </div>
        
        <div class="quick-feedback-container" id="quickFeedbackContainer">
          <div class="quick-feedback-grid">
            <div class="feedback-group">
              <h4 class="group-title">Was this response helpful?</h4>
              <div class="button-group">
                <button class="quick-btn" data-feedback="helpful" data-value="true">
                  <i class="fas fa-thumbs-up" aria-hidden="true"></i>
                  <span>Helpful</span>
                </button>
                <button class="quick-btn" data-feedback="helpful" data-value="false">
                  <i class="fas fa-thumbs-down" aria-hidden="true"></i>
                  <span>Not Helpful</span>
                </button>
              </div>
            </div>
            
            <div class="feedback-group">
              <h4 class="group-title">Was this response accurate?</h4>
              <div class="button-group">
                <button class="quick-btn" data-feedback="accurate" data-value="true">
                  <i class="fas fa-check-circle" aria-hidden="true"></i>
                  <span>Accurate</span>
                </button>
                <button class="quick-btn" data-feedback="accurate" data-value="false">
                  <i class="fas fa-times-circle" aria-hidden="true"></i>
                  <span>Inaccurate</span>
                </button>
              </div>
            </div>
          </div>
        </div>
        
        ${this.feedbackData.sources && this.feedbackData.sources.length > 0 ? `
          <div class="source-preferences-section">
            <h4 class="section-title">Source Preferences</h4>
            <p class="section-description">Rate the sources used in this response</p>
            <div class="source-ranking-container" id="sourceRankingContainer">
              <!-- Source preference ranking will be initialized here -->
            </div>
          </div>
        ` : ''}
        
        <div class="step-note">
          <i class="fas fa-info-circle" aria-hidden="true"></i>
          <span>This step is optional. You can skip to provide more detailed feedback.</span>
        </div>
      </div>
    `;
  }

  /**
   * Step 3: Detailed Feedback (Optional)
   */
  renderStep3() {
    return `
      <div class="feedback-step" data-step="3">
        <div class="step-header">
          <h3 class="step-title">Additional feedback</h3>
          <p class="step-description">Help us improve by sharing specific details</p>
        </div>
        
        <div class="detailed-feedback">
          <div class="expandable-section ${this.feedbackData.missingInfo ? 'expanded' : ''}">
            <button class="section-toggle" aria-expanded="${this.feedbackData.missingInfo ? 'true' : 'false'}" tabindex="0">
              <i class="fas fa-chevron-right toggle-icon" aria-hidden="true"></i>
              <span>What information was missing?</span>
            </button>
            <div class="section-content">
              <textarea 
                class="feedback-textarea" 
                placeholder="Describe any information that should have been included..."
                aria-label="Missing information feedback"
                rows="3"
                data-field="missingInfo"
              >${this.feedbackData.missingInfo || ''}</textarea>
            </div>
          </div>
          
          <div class="expandable-section ${this.feedbackData.incorrectInfo ? 'expanded' : ''}">
            <button class="section-toggle" aria-expanded="${this.feedbackData.incorrectInfo ? 'true' : 'false'}" tabindex="0">
              <i class="fas fa-chevron-right toggle-icon" aria-hidden="true"></i>
              <span>What information was incorrect?</span>
            </button>
            <div class="section-content">
              <textarea 
                class="feedback-textarea" 
                placeholder="Describe any incorrect or misleading information..."
                aria-label="Incorrect information feedback"
                rows="3"
                data-field="incorrectInfo"
              >${this.feedbackData.incorrectInfo || ''}</textarea>
            </div>
          </div>
          
          <div class="expandable-section ${this.feedbackData.generalComments ? 'expanded' : ''}">
            <button class="section-toggle" aria-expanded="${this.feedbackData.generalComments ? 'true' : 'false'}" tabindex="0">
              <i class="fas fa-chevron-right toggle-icon" aria-hidden="true"></i>
              <span>General comments or suggestions</span>
            </button>
            <div class="section-content">
              <textarea 
                class="feedback-textarea" 
                placeholder="Any other feedback or suggestions for improvement..."
                aria-label="General feedback comments"
                rows="3"
                data-field="generalComments"
              >${this.feedbackData.generalComments || ''}</textarea>
            </div>
          </div>
        </div>
        
        <div class="step-note">
          <i class="fas fa-heart" aria-hidden="true"></i>
          <span>Thank you for taking the time to help us improve!</span>
        </div>
      </div>
    `;
  }

  /**
   * Render action buttons based on current step
   */
  renderActionButtons() {
    const isFirstStep = this.currentStep === 1;
    const isLastStep = this.currentStep === this.maxSteps;
    const canProceed = this.validateCurrentStep();

    return `
      <div class="action-buttons">
        ${!isFirstStep ? `
          <button class="feedback-btn secondary feedback-prev-btn" tabindex="0">
            <i class="fas fa-chevron-left" aria-hidden="true"></i>
            <span>Previous</span>
          </button>
        ` : ''}
        
        <div class="primary-actions">
          ${!isLastStep ? `
            <button class="feedback-btn secondary feedback-skip-btn" tabindex="0">
              Skip to end
            </button>
            <button 
              class="feedback-btn primary feedback-next-btn ${!canProceed ? 'disabled' : ''}" 
              ${!canProceed ? 'disabled' : ''}
              tabindex="0"
            >
              <span>Next</span>
              <i class="fas fa-chevron-right" aria-hidden="true"></i>
            </button>
          ` : `
            <button class="feedback-btn secondary feedback-cancel-btn" tabindex="0">
              Cancel
            </button>
            <button class="feedback-btn primary feedback-submit-btn" tabindex="0">
              <i class="fas fa-paper-plane" aria-hidden="true"></i>
              <span>Submit Feedback</span>
            </button>
          `}
        </div>
      </div>
    `;
  }

  /**
   * Update step content with smooth transition
   */
  updateStepContent() {
    const contentContainer = this.modal.querySelector('.feedback-content');
    const actionsContainer = this.modal.querySelector('.feedback-actions');

    // Fade out
    contentContainer.style.opacity = '0';
    actionsContainer.style.opacity = '0';

    setTimeout(() => {
      // Update content
      contentContainer.innerHTML = this.renderStepContent();
      actionsContainer.innerHTML = this.renderActionButtons();

      // Update progress bar
      const progressFill = this.modal.querySelector('.progress-fill');
      const progressText = this.modal.querySelector('.progress-text');

      progressFill.style.width = `${(this.currentStep / this.maxSteps) * 100}%`;
      progressText.textContent = `Step ${this.currentStep} of ${this.maxSteps}`;

      // Re-attach event listeners for new content
      this.attachStepEventListeners();

      // Fade in
      contentContainer.style.opacity = '1';
      actionsContainer.style.opacity = '1';

      // Focus management
      const firstFocusable = contentContainer.querySelector('button, input, textarea, select');
      if (firstFocusable) {
        firstFocusable.focus();
      }
    }, 150);
  }

  /**
   * Attach event listeners to modal elements
   */
  attachEventListeners() {
    // Close button
    const closeBtn = this.modal.querySelector('.feedback-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', this.hide);
    }

    // Overlay click to close
    this.overlay.addEventListener('click', (e) => {
      if (e.target === this.overlay) {
        this.hide();
      }
    });

    // Attach step-specific listeners
    this.attachStepEventListeners();
  }

  /**
   * Attach event listeners for current step content
   */
  attachStepEventListeners() {
    // Action buttons
    const nextBtn = this.modal.querySelector('.feedback-next-btn');
    const prevBtn = this.modal.querySelector('.feedback-prev-btn');
    const skipBtn = this.modal.querySelector('.feedback-skip-btn');
    const submitBtn = this.modal.querySelector('.feedback-submit-btn');
    const cancelBtn = this.modal.querySelector('.feedback-cancel-btn');

    if (nextBtn) nextBtn.addEventListener('click', this.nextStep);
    if (prevBtn) prevBtn.addEventListener('click', this.prevStep);
    if (skipBtn) skipBtn.addEventListener('click', () => { this.currentStep = this.maxSteps; this.updateStepContent(); });
    if (submitBtn) submitBtn.addEventListener('click', this.submitFeedback);
    if (cancelBtn) cancelBtn.addEventListener('click', this.hide);

    // Step-specific listeners
    switch (this.currentStep) {
      case 1:
        this.attachStep1Listeners();
        break;
      case 2:
        this.attachStep2Listeners();
        break;
      case 3:
        this.attachStep3Listeners();
        break;
    }
  }

  /**
   * Attach listeners for step 1 (rating)
   */
  attachStep1Listeners() {
    const container = this.modal.querySelector('#starRatingContainer');
    if (container && window.StarRatingComponent) {
      this.starRating = new window.StarRatingComponent(container, {
        maxRating: 5,
        size: 'large',
        showLabels: true,
        interactive: true,
        onChange: (rating) => {
          this.feedbackData.overallRating = rating;

          // Update next button state
          const nextBtn = this.modal.querySelector('.feedback-next-btn');
          if (nextBtn) {
            nextBtn.classList.remove('disabled');
            nextBtn.disabled = false;
          }

          // Show rating feedback message
          this.updateRatingFeedback(rating);
        }
      });

      // Set existing rating if any
      if (this.feedbackData.overallRating) {
        this.starRating.setRating(this.feedbackData.overallRating);
      }
    } else {
      // Fallback: create simple star rating if component not available
      this.createFallbackStarRating(container);
    }
  }

  /**
   * Create fallback star rating if component not loaded
   */
  createFallbackStarRating(container) {
    if (!container) return;

    container.innerHTML = `
      <div class="fallback-star-rating">
        <div class="star-rating-title">Rate this response:</div>
        <div class="stars-container">
          ${Array.from({ length: 5 }, (_, i) => `
            <button class="star-btn" data-rating="${i + 1}" type="button">
              <i class="fas fa-star" aria-hidden="true"></i>
            </button>
          `).join('')}
        </div>
        <div class="rating-labels">
          <span>Poor</span>
          <span>Excellent</span>
        </div>
      </div>
    `;

    // Add event listeners
    const starBtns = container.querySelectorAll('.star-btn');
    starBtns.forEach((btn, index) => {
      btn.addEventListener('click', () => {
        const rating = parseInt(btn.dataset.rating);
        this.feedbackData.overallRating = rating;

        // Update visual state
        starBtns.forEach((star, i) => {
          star.classList.toggle('selected', i < rating);
        });

        // Update next button state
        const nextBtn = this.modal.querySelector('.feedback-next-btn');
        if (nextBtn) {
          nextBtn.classList.remove('disabled');
          nextBtn.disabled = false;
        }

        // Show rating feedback message
        this.updateRatingFeedback(rating);
      });

      // Hover effects
      btn.addEventListener('mouseenter', () => {
        const rating = parseInt(btn.dataset.rating);
        starBtns.forEach((star, i) => {
          star.classList.toggle('hovered', i < rating);
        });
      });

      btn.addEventListener('mouseleave', () => {
        starBtns.forEach(star => star.classList.remove('hovered'));
      });
    });
  }

  /**
   * Attach listeners for step 2 (quick feedback)
   */
  attachStep2Listeners() {
    // Handle quick feedback buttons
    const quickButtons = this.modal.querySelectorAll('.quick-btn');
    quickButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        const feedbackType = e.currentTarget.dataset.feedback;
        const value = e.currentTarget.dataset.value === 'true';

        // Remove active state from other buttons in the same group
        const group = e.currentTarget.closest('.feedback-group');
        const groupButtons = group.querySelectorAll('.quick-btn');
        groupButtons.forEach(btn => btn.classList.remove('selected'));

        // Add active state to clicked button
        e.currentTarget.classList.add('selected');

        // Store feedback data
        if (feedbackType === 'helpful') {
          this.feedbackData.isHelpful = value;
        } else if (feedbackType === 'accurate') {
          this.feedbackData.isAccurate = value;
        }

        // Visual feedback
        e.currentTarget.style.transform = 'scale(0.95)';
        setTimeout(() => {
          e.currentTarget.style.transform = '';
        }, 150);
      });
    });

    // Initialize source preference ranking if sources are available
    const sourceContainer = this.modal.querySelector('#sourceRankingContainer');
    if (sourceContainer && this.feedbackData.sources && this.feedbackData.sources.length > 0) {
      this.renderSourcePreferences(sourceContainer);
    }
  }

  /**
   * Render source preferences section
   */
  renderSourcePreferences(container) {
    if (!this.feedbackData.sources || this.feedbackData.sources.length === 0) {
      return;
    }

    const sourcesHtml = this.feedbackData.sources.map((source, index) => {
      const fileName = source.source_file ?
        source.source_file.split('/').pop().split('\\').pop() :
        `Source ${index + 1}`;

      return `
        <div class="source-item" data-source-index="${index}">
          <div class="source-info">
            <div class="source-name">${fileName}</div>
            ${source.score ? `<div class="source-score">Relevance: ${(source.score * 100).toFixed(0)}%</div>` : ''}
          </div>
          <div class="source-rating">
            <button class="source-btn" data-rating="good" data-source="${index}">
              <i class="fas fa-thumbs-up"></i>
              Good
            </button>
            <button class="source-btn" data-rating="poor" data-source="${index}">
              <i class="fas fa-thumbs-down"></i>
              Poor
            </button>
          </div>
        </div>
      `;
    }).join('');

    container.innerHTML = sourcesHtml;

    // Add event listeners for source rating
    const sourceButtons = container.querySelectorAll('.source-btn');
    sourceButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        const sourceIndex = e.currentTarget.dataset.source;
        const rating = e.currentTarget.dataset.rating;

        // Remove active state from other buttons for this source
        const sourceItem = e.currentTarget.closest('.source-item');
        const sourceItemButtons = sourceItem.querySelectorAll('.source-btn');
        sourceItemButtons.forEach(btn => btn.classList.remove('selected'));

        // Add active state to clicked button
        e.currentTarget.classList.add('selected');

        // Store preference
        if (!this.feedbackData.sourcePreferences) {
          this.feedbackData.sourcePreferences = {};
        }
        this.feedbackData.sourcePreferences[sourceIndex] = rating;
      });
    });
  }

  /**
   * Attach listeners for step 3 (detailed feedback)
   */
  attachStep3Listeners() {
    // Expandable sections
    const sectionToggles = this.modal.querySelectorAll('.section-toggle');
    sectionToggles.forEach(toggle => {
      toggle.addEventListener('click', (e) => {
        const section = e.currentTarget.closest('.expandable-section');
        const isExpanded = section.classList.contains('expanded');

        section.classList.toggle('expanded');
        toggle.setAttribute('aria-expanded', !isExpanded);

        if (!isExpanded) {
          const textarea = section.querySelector('textarea');
          if (textarea) {
            setTimeout(() => textarea.focus(), 200);
          }
        }
      });
    });

    // Textarea inputs
    const textareas = this.modal.querySelectorAll('.feedback-textarea');
    textareas.forEach(textarea => {
      textarea.addEventListener('input', (e) => {
        const field = e.target.dataset.field;
        this.feedbackData[field] = e.target.value;

        // Auto-expand section if user starts typing
        const section = e.target.closest('.expandable-section');
        if (!section.classList.contains('expanded') && e.target.value.trim()) {
          section.classList.add('expanded');
          const toggle = section.querySelector('.section-toggle');
          if (toggle) {
            toggle.setAttribute('aria-expanded', 'true');
          }
        }
      });
    });
  }

  /**
   * Update rating feedback message
   */
  updateRatingFeedback(rating) {
    const existingFeedback = this.modal.querySelector('.rating-feedback');
    if (existingFeedback) {
      existingFeedback.remove();
    }

    const ratingContainer = this.modal.querySelector('.rating-container');
    const feedbackHTML = `
      <div class="rating-feedback" aria-live="polite">
        <p class="rating-message">${this.getRatingMessage(rating)}</p>
      </div>
    `;

    ratingContainer.insertAdjacentHTML('beforeend', feedbackHTML);
  }

  /**
   * Get contextual message for rating
   */
  getRatingMessage(rating) {
    const messages = {
      1: "We're sorry this response didn't meet your expectations. Your feedback helps us improve.",
      2: "Thank you for the feedback. We'll work on making our responses better.",
      3: "Thanks for rating! We appreciate any additional feedback you can provide.",
      4: "Great! We're glad this response was helpful. Any suggestions for improvement?",
      5: "Excellent! We're thrilled this response met your needs perfectly."
    };
    return messages[rating] || "Thank you for your rating!";
  }

  /**
   * Submit feedback to the server
   */
  async submitFeedback() {
    const submitBtn = this.modal.querySelector('.feedback-submit-btn');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<div class="loading-spinner"></div><span>Submitting...</span>';
    }

    try {
      const feedbackPayload = {
        query_text: this.feedbackData.queryText,
        response_text: this.feedbackData.responseText,
        sources_used: this.feedbackData.sources,
        rating: this.feedbackData.overallRating,
        is_accurate: this.feedbackData.isAccurate,
        is_helpful: this.feedbackData.isHelpful,
        missing_info: this.feedbackData.missingInfo,
        incorrect_info: this.feedbackData.incorrectInfo,
        comments: this.feedbackData.generalComments,
        user_session: this.getUserSession()
      };

      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(feedbackPayload)
      });

      const result = await response.json();

      if (result.success) {
        this.showSuccessMessage(result);
        setTimeout(() => this.hide(), 3000);
      } else {
        throw new Error(result.error || 'Failed to submit feedback');
      }
    } catch (error) {
      console.error('Feedback submission failed:', error);
      this.showErrorMessage(error.message);

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i><span>Submit Feedback</span>';
      }
    }
  }

  /**
   * Show success message with personalized acknowledgment
   */
  showSuccessMessage(result) {
    const contentContainer = this.modal.querySelector('.feedback-content');

    // Get user session for personalized message
    const userSession = this.getUserSession();
    const feedbackCount = this.getFeedbackCount();

    let personalizedMessage = "Your input helps us improve our responses and provide better assistance.";
    let impactMessage = "";

    // Add personalized acknowledgment based on feedback count
    if (feedbackCount > 1) {
      personalizedMessage = `This is your ${this.getOrdinal(feedbackCount)} piece of feedback - thank you for being an active contributor!`;
    }

    // Add impact information if available
    if (result.feedback_id) {
      impactMessage = `
        <div class="feedback-impact">
          <i class="fas fa-chart-line"></i>
          <span>Your feedback contributes to our continuous improvement efforts.</span>
        </div>
      `;
    }

    contentContainer.innerHTML = `
      <div class="feedback-success">
        <div class="success-icon">
          <i class="fas fa-check-circle"></i>
        </div>
        <h3>Thank you for your feedback!</h3>
        <p>${personalizedMessage}</p>
        ${impactMessage}
      </div>
    `;

    const actionsContainer = this.modal.querySelector('.feedback-actions');
    actionsContainer.style.display = 'none';

    // Update feedback count
    this.incrementFeedbackCount();

    this.announceToScreenReader('Feedback submitted successfully. Thank you for contributing to system improvements!');
  }

  /**
   * Get or create user session ID
   */
  getUserSession() {
    let sessionId = localStorage.getItem('feedback_session_id');
    if (!sessionId) {
      sessionId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('feedback_session_id', sessionId);
    }
    return sessionId;
  }

  /**
   * Get user's feedback count
   */
  getFeedbackCount() {
    return parseInt(localStorage.getItem('user_feedback_count') || '0');
  }

  /**
   * Increment user's feedback count
   */
  incrementFeedbackCount() {
    const count = this.getFeedbackCount() + 1;
    localStorage.setItem('user_feedback_count', count.toString());
  }

  /**
   * Get ordinal number (1st, 2nd, 3rd, etc.)
   */
  getOrdinal(num) {
    const suffixes = ["th", "st", "nd", "rd"];
    const v = num % 100;
    return num + (suffixes[(v - 20) % 10] || suffixes[v] || suffixes[0]);
  }

  /**
   * Show error message
   */
  showErrorMessage(message) {
    const existingError = this.modal.querySelector('.feedback-error');
    if (existingError) {
      existingError.remove();
    }

    const contentContainer = this.modal.querySelector('.feedback-content');
    const errorHTML = `
      <div class="feedback-error" role="alert">
        <i class="fas fa-exclamation-triangle"></i>
        <span>Failed to submit feedback: ${message}</span>
      </div>
    `;

    contentContainer.insertAdjacentHTML('afterbegin', errorHTML);
    this.announceToScreenReader(`Error: ${message}`);
  }

  /**
   * Announce message to screen readers
   */
  announceToScreenReader(message) {
    const announcement = document.createElement('div');
    announcement.setAttribute('aria-live', 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.className = 'sr-only';
    announcement.textContent = message;

    document.body.appendChild(announcement);

    setTimeout(() => {
      document.body.removeChild(announcement);
    }, 1000);
  }
}

// Create global instance
window.enhancedFeedbackModal = new EnhancedFeedbackModal();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = EnhancedFeedbackModal;
}