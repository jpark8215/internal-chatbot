/**
 * Enhanced Analytics and Visualization Components
 * Comprehensive analytics dashboard with advanced charts and insights
 */

class EnhancedAnalytics extends FeedbackAnalytics {
  constructor() {
    super();
    this.performanceData = null;

    this.engagementMetrics = null;
    this.fullscreenChart = null;
  }

  async initialize() {
    await super.initialize();
    await this.loadAdditionalData();
    this.renderAdditionalCharts();
    this.renderInsights();
    this.renderAnalyticsTable();
    this.renderPerformanceMetrics();
    this.setupEnhancedEventListeners();
  }

  setupEnhancedEventListeners() {
    // Global time range selector
    document.getElementById('global-time-range')?.addEventListener('change', (e) => {
      this.timeRange = parseInt(e.target.value);
      this.refreshAllAnalytics();
    });

    // Close fullscreen modal on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.fullscreenChart) {
        this.closeChartFullscreen();
      }
    });
  }

  async loadAdditionalData() {
    try {
      // Load performance metrics
      const performanceResponse = await fetch(`/api/metrics?time_window=${this.timeRange * 24 * 60}`);
      const performanceData = await performanceResponse.json();
      this.performanceData = performanceData.metrics || {};



      // Generate engagement metrics (would come from user tracking in real implementation)
      this.engagementMetrics = this.generateEngagementMetrics();

    } catch (error) {
      console.error('Failed to load additional analytics data:', error);
    }
  }

  async refreshAllAnalytics() {
    try {
      this.showAllChartsLoading();
      await this.loadAnalyticsData();
      await this.loadAdditionalData();
      this.renderAllCharts();
      this.renderAdditionalCharts();
      this.renderInsights();
      this.renderAnalyticsTable();
      this.renderPerformanceMetrics();
      this.updateSummaryCards();
    } catch (error) {
      console.error('Failed to refresh analytics:', error);
      this.showError('Failed to refresh analytics data');
    }
  }

  renderAdditionalCharts() {
    this.renderEngagementMetricsChart();
  }



  renderEngagementMetricsChart() {
    const ctx = document.getElementById('engagement-metrics-chart');
    if (!ctx) return;

    // Destroy existing chart
    if (this.charts.engagementMetrics) {
      this.charts.engagementMetrics.destroy();
    }

    const engagement = this.engagementMetrics;

    this.charts.engagementMetrics = new Chart(ctx, {
      type: 'radar',
      data: {
        labels: [
          'Query Frequency',
          'Feedback Rate',
          'Session Duration',
          'Return Rate',
          'Feature Usage',
          'Satisfaction'
        ],
        datasets: [{
          label: 'Current Period',
          data: engagement.current,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.2)',
          pointBackgroundColor: '#3b82f6',
          pointBorderColor: '#ffffff',
          pointHoverBackgroundColor: '#ffffff',
          pointHoverBorderColor: '#3b82f6'
        }, {
          label: 'Previous Period',
          data: engagement.previous,
          borderColor: '#94a3b8',
          backgroundColor: 'rgba(148, 163, 184, 0.1)',
          pointBackgroundColor: '#94a3b8',
          pointBorderColor: '#ffffff',
          pointHoverBackgroundColor: '#ffffff',
          pointHoverBorderColor: '#94a3b8'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            beginAtZero: true,
            max: 100,
            ticks: {
              stepSize: 20
            }
          }
        },
        plugins: {
          title: {
            display: true,
            text: 'User Engagement Comparison'
          }
        }
      }
    });
  }

  renderInsights() {
    const insightsList = document.getElementById('insights-list');
    if (!insightsList) return;

    const insights = this.generateInsights();

    if (insights.length === 0) {
      insightsList.innerHTML = `
        <div class="insight-item">
          <div class="insight-icon">
            <i class="fas fa-info-circle"></i>
          </div>
          <div class="insight-content">
            <div class="insight-message">No significant insights detected at this time.</div>
            <div class="insight-details">All metrics appear to be within normal ranges.</div>
          </div>
        </div>
      `;
      return;
    }

    insightsList.innerHTML = insights.map(insight => `
      <div class="insight-item ${insight.type}">
        <div class="insight-icon">
          <i class="fas ${insight.icon}"></i>
        </div>
        <div class="insight-content">
          <div class="insight-message">${insight.message}</div>
          <div class="insight-details">${insight.details}</div>
          ${insight.action ? `
            <div class="insight-action">
              <button class="insight-action-btn" onclick="${insight.action.handler}">
                ${insight.action.text}
              </button>
            </div>
          ` : ''}
        </div>
      </div>
    `).join('');
  }

  generateInsights() {
    const insights = [];
    const stats = this.analyticsData?.basic_stats;
    const performance = this.performanceData;

    if (!stats) return insights;

    // Rating insights
    if (stats.avg_rating < 3.5) {
      insights.push({
        type: 'error',
        icon: 'fa-exclamation-triangle',
        message: 'Low Average Rating Detected',
        details: `Current average rating is ${stats.avg_rating.toFixed(1)}/5. Consider reviewing recent responses for quality issues.`,
        action: {
          text: 'View Low-Rated Feedback',
          handler: 'viewLowRatedFeedback()'
        }
      });
    } else if (stats.avg_rating >= 4.5) {
      insights.push({
        type: 'success',
        icon: 'fa-star',
        message: 'Excellent User Satisfaction',
        details: `Average rating of ${stats.avg_rating.toFixed(1)}/5 indicates high user satisfaction. Keep up the good work!`
      });
    }

    // Accuracy insights
    if (stats.accuracy_rate < 70) {
      insights.push({
        type: 'error',
        icon: 'fa-times-circle',
        message: 'Accuracy Rate Below Target',
        details: `Current accuracy rate is ${stats.accuracy_rate.toFixed(1)}%. Review search strategies and document quality.`,
        action: {
          text: 'Analyze Accuracy Issues',
          handler: 'analyzeAccuracyIssues()'
        }
      });
    }

    // Volume insights
    if (stats.total_feedback > 0) {
      const pendingCount = (stats.new_count || 0) + (stats.reviewed_count || 0);
      if (pendingCount > stats.total_feedback * 0.3) {
        insights.push({
          type: 'warning',
          icon: 'fa-clock',
          message: 'High Volume of Pending Feedback',
          details: `${pendingCount} feedback items are pending review (${((pendingCount / stats.total_feedback) * 100).toFixed(1)}% of total).`,
          action: {
            text: 'Review Pending Items',
            handler: 'reviewPendingFeedback()'
          }
        });
      }
    }

    // Performance insights
    if (performance?.performance?.avg_total_time_ms > 3000) {
      insights.push({
        type: 'warning',
        icon: 'fa-clock',
        message: 'Response Time Above Optimal',
        details: `Average response time is ${performance.performance.avg_total_time_ms.toFixed(0)}ms. Consider optimizing search or caching strategies.`,
        action: {
          text: 'View Performance Metrics',
          handler: 'viewPerformanceMetrics()'
        }
      });
    }

    // Positive insights
    if (stats.addressed_count > stats.new_count + stats.reviewed_count) {
      insights.push({
        type: 'success',
        icon: 'fa-check-circle',
        message: 'Efficient Issue Resolution',
        details: `More issues have been resolved (${stats.addressed_count}) than are currently pending (${stats.new_count + stats.reviewed_count}).`
      });
    }

    return insights;
  }

  renderAnalyticsTable() {
    const tableBody = document.getElementById('analytics-table-body');
    if (!tableBody) return;

    const stats = this.analyticsData?.basic_stats;
    const performance = this.performanceData?.performance;

    if (!stats) {
      tableBody.innerHTML = '<tr><td colspan="5">No data available</td></tr>';
      return;
    }

    const metrics = [
      {
        name: 'Total Feedback',
        current: stats.total_feedback || 0,
        previous: Math.floor((stats.total_feedback || 0) * 0.85), // Simulated previous period
        format: 'number'
      },
      {
        name: 'Average Rating',
        current: stats.avg_rating || 0,
        previous: (stats.avg_rating || 0) - 0.1,
        format: 'decimal'
      },
      {
        name: 'Accuracy Rate',
        current: stats.accuracy_rate || 0,
        previous: (stats.accuracy_rate || 0) - 2,
        format: 'percentage'
      },
      {
        name: 'Response Time',
        current: performance?.avg_total_time_ms || 0,
        previous: (performance?.avg_total_time_ms || 0) + 200,
        format: 'milliseconds'
      },
      {
        name: 'Resolution Rate',
        current: stats.total_feedback > 0 ? (stats.addressed_count / stats.total_feedback * 100) : 0,
        previous: stats.total_feedback > 0 ? ((stats.addressed_count - 5) / stats.total_feedback * 100) : 0,
        format: 'percentage'
      }
    ];

    tableBody.innerHTML = metrics.map(metric => {
      const change = metric.current - metric.previous;
      const changePercent = metric.previous > 0 ? (change / metric.previous * 100) : 0;
      const isPositive = change > 0;
      const trendIcon = isPositive ? 'fa-arrow-up' : change < 0 ? 'fa-arrow-down' : 'fa-minus';
      const trendClass = isPositive ? 'positive' : change < 0 ? 'negative' : 'neutral';

      return `
        <tr>
          <td><strong>${metric.name}</strong></td>
          <td>${this.formatMetricValue(metric.current, metric.format)}</td>
          <td>${this.formatMetricValue(metric.previous, metric.format)}</td>
          <td class="${trendClass}">
            ${change > 0 ? '+' : ''}${this.formatMetricValue(change, metric.format)}
            ${changePercent !== 0 ? `(${changePercent > 0 ? '+' : ''}${changePercent.toFixed(1)}%)` : ''}
          </td>
          <td class="${trendClass}">
            <i class="fas ${trendIcon}"></i>
          </td>
        </tr>
      `;
    }).join('');
  }

  formatMetricValue(value, format) {
    switch (format) {
      case 'number':
        return Math.round(value).toLocaleString();
      case 'decimal':
        return value.toFixed(1);
      case 'percentage':
        return value.toFixed(1) + '%';
      case 'milliseconds':
        return Math.round(value) + 'ms';
      default:
        return value.toString();
    }
  }

  renderPerformanceMetrics() {
    const performance = this.performanceData?.performance;
    if (!performance) return;


    this.updateElement('cache-hit-rate', ((performance.cache_hit_rate || 0) * 100).toFixed(1));
    this.updateElement('error-rate', ((performance.error_rate || 0) * 100).toFixed(2));
    this.updateElement('throughput', (performance.queries_per_minute || 0).toFixed(1));
  }

  updateSummaryCards() {
    const stats = this.analyticsData?.basic_stats;
    const performance = this.performanceData?.performance;

    if (!stats) return;

    this.updateElement('summary-total-feedback', stats.total_feedback || 0);
    this.updateElement('summary-avg-rating', (stats.avg_rating || 0).toFixed(1));
    this.updateElement('summary-accuracy', (stats.accuracy_rate || 0).toFixed(1) + '%');
    this.updateElement('summary-response-time', Math.round(performance?.avg_total_time_ms || 0) + 'ms');
    this.updateElement('summary-resolved', stats.addressed_count || 0);
    
    // Calculate satisfaction score (composite metric)
    const satisfactionScore = this.calculateSatisfactionScore(stats, performance);
    this.updateElement('summary-satisfaction', satisfactionScore.toFixed(1));
  }

  calculateSatisfactionScore(stats, performance) {
    // Composite satisfaction score based on multiple factors
    let score = 0;
    
    // Rating component (40% weight)
    if (stats.avg_rating) {
      score += (stats.avg_rating / 5) * 40;
    }
    
    // Accuracy component (30% weight)
    if (stats.accuracy_rate) {
      score += (stats.accuracy_rate / 100) * 30;
    }
    
    // Performance component (20% weight)
    if (performance?.avg_total_time_ms) {
      const perfScore = Math.max(0, 1 - (performance.avg_total_time_ms / 5000)); // 5s = 0 score
      score += perfScore * 20;
    }
    
    // Resolution rate component (10% weight)
    if (stats.total_feedback > 0) {
      const resolutionRate = stats.addressed_count / stats.total_feedback;
      score += resolutionRate * 10;
    }
    
    return Math.min(100, Math.max(0, score));
  }

  updateElement(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  }



  generateEngagementMetrics() {
    // Use real engagement metrics from analytics data
    return this.analyticsData?.engagement_metrics || {
      current: [0, 0, 0, 0, 0, 0],
      previous: [0, 0, 0, 0, 0, 0]
    };
  }

  showAllChartsLoading() {
    const chartIds = [
      'feedback-trends-chart',
      'rating-distribution-chart',
      'accuracy-trends-chart',
      'source-preferences-chart',
      'response-time-chart',
      'status-distribution-chart',

      'engagement-metrics-chart'
    ];

    chartIds.forEach(id => {
      const container = document.getElementById(id);
      if (container) {
        container.innerHTML = '<div class="chart-loading">Loading...</div>';
      }
    });
  }

  // Chart interaction methods
  toggleChartFullscreen(chartId) {
    const canvas = document.getElementById(chartId);
    const modal = document.getElementById('chart-fullscreen-modal');
    const modalTitle = document.getElementById('chart-modal-title');
    const fullscreenCanvas = document.getElementById('fullscreen-chart');

    if (!canvas || !modal || !this.charts[chartId.replace('-chart', '')]) return;

    // Set modal title
    const chartTitles = {
      'feedback-trends-chart': 'Feedback Trends Over Time',
      'rating-distribution-chart': 'Rating Distribution',
      'accuracy-trends-chart': 'Accuracy Trends',
      'source-preferences-chart': 'Source Preferences',
      'response-time-chart': 'Response Time vs Satisfaction',
      'status-distribution-chart': 'Status Distribution',

      'engagement-metrics-chart': 'User Engagement Metrics'
    };

    modalTitle.textContent = chartTitles[chartId] || 'Chart';

    // Clone chart configuration and create fullscreen version
    const originalChart = this.charts[chartId.replace('-chart', '')];
    const config = JSON.parse(JSON.stringify(originalChart.config));
    
    // Adjust for fullscreen
    config.options.maintainAspectRatio = false;
    config.options.responsive = true;

    this.fullscreenChart = new Chart(fullscreenCanvas, config);
    modal.style.display = 'flex';
  }

  closeChartFullscreen() {
    const modal = document.getElementById('chart-fullscreen-modal');
    if (modal) {
      modal.style.display = 'none';
    }
    
    if (this.fullscreenChart) {
      this.fullscreenChart.destroy();
      this.fullscreenChart = null;
    }
  }

  downloadChart(chartId) {
    const canvas = document.getElementById(chartId);
    if (!canvas) return;

    const link = document.createElement('a');
    link.download = `${chartId}-${new Date().toISOString().split('T')[0]}.png`;
    link.href = canvas.toDataURL();
    link.click();
  }

  async exportAnalyticsReport() {
    try {
      const reportData = {
        timestamp: new Date().toISOString(),
        timeRange: this.timeRange,
        summary: this.analyticsData?.basic_stats,
        performance: this.performanceData?.performance,
        insights: this.generateInsights(),
        charts: Object.keys(this.charts)
      };

      const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analytics-report-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

    } catch (error) {
      console.error('Failed to export analytics report:', error);
    }
  }

  exportTableData() {
    const table = document.getElementById('detailed-analytics-table');
    if (!table) return;

    let csv = '';
    const rows = table.querySelectorAll('tr');
    
    rows.forEach(row => {
      const cols = row.querySelectorAll('th, td');
      const rowData = Array.from(cols).map(col => `"${col.textContent.trim()}"`);
      csv += rowData.join(',') + '\n';
    });

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analytics-table-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  showError(message) {
    console.error('Analytics error:', message);
    // Could implement a toast notification system here
  }
}

// Global functions for UI interactions
function refreshAllAnalytics() {
  if (window.enhancedAnalytics) {
    window.enhancedAnalytics.refreshAllAnalytics();
  }
}

function refreshInsights() {
  if (window.enhancedAnalytics) {
    window.enhancedAnalytics.renderInsights();
  }
}

function downloadChart(chartId) {
  if (window.enhancedAnalytics) {
    window.enhancedAnalytics.downloadChart(chartId);
  }
}

function toggleChartFullscreen(chartId) {
  if (window.enhancedAnalytics) {
    window.enhancedAnalytics.toggleChartFullscreen(chartId);
  }
}

function closeChartFullscreen() {
  if (window.enhancedAnalytics) {
    window.enhancedAnalytics.closeChartFullscreen();
  }
}

function exportAnalyticsReport() {
  if (window.enhancedAnalytics) {
    window.enhancedAnalytics.exportAnalyticsReport();
  }
}

function exportTableData() {
  if (window.enhancedAnalytics) {
    window.enhancedAnalytics.exportTableData();
  }
}

// Insight action handlers
function viewLowRatedFeedback() {
  window.location.href = '/feedback-management?rating=low';
}

function analyzeAccuracyIssues() {
  window.location.href = '/feedback-management?accuracy=inaccurate';
}

function reviewPendingFeedback() {
  window.location.href = '/feedback-management?status=new';
}

function viewPerformanceMetrics() {
  window.location.href = '/system-stats';
}

// Initialize enhanced analytics
document.addEventListener('DOMContentLoaded', function() {
  window.enhancedAnalytics = new EnhancedAnalytics();
  window.enhancedAnalytics.initialize();
});