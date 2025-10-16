"""
Background monitoring service for automated feedback alerting.
Runs periodic monitoring cycles to detect issues and generate alerts.
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from .config import get_settings
from .logging_config import get_logger
from .alerting_system import get_feedback_monitor, get_alert_dao
from .improvement_tracker import get_improvement_tracker

logger = get_logger(__name__)


class MonitoringService:
    """Background service for automated feedback monitoring."""
    
    def __init__(self, check_interval_minutes: int = 60):
        self.check_interval_minutes = check_interval_minutes
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_check: Optional[datetime] = None
        
    def start(self):
        """Start the monitoring service."""
        if self.running:
            logger.warning("Monitoring service is already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.thread.start()
        logger.info(f"Monitoring service started with {self.check_interval_minutes} minute intervals")
    
    def stop(self):
        """Stop the monitoring service."""
        if not self.running:
            return
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Monitoring service stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._run_monitoring_cycle()
                self.last_check = datetime.now()
                
                # Sleep for the specified interval
                time.sleep(self.check_interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                # Sleep for a shorter time on error to retry sooner
                time.sleep(300)  # 5 minutes
    
    def _run_monitoring_cycle(self):
        """Run a single monitoring cycle."""
        try:
            logger.info("Starting monitoring cycle")
            
            # Run feedback monitoring
            monitor = get_feedback_monitor()
            alerts = monitor.run_monitoring_cycle()
            
            if alerts:
                logger.info(f"Generated {len(alerts)} alerts")
                for alert in alerts:
                    logger.info(f"Alert: {alert.severity.value} - {alert.title}")
            else:
                logger.info("No alerts generated")
            
            # Auto-measure recent improvements
            try:
                tracker = get_improvement_tracker()
                measurement_results = tracker.auto_measure_recent_improvements(days_back=7)
                
                if measurement_results:
                    measured_count = len([r for r in measurement_results if r.get('status') == 'measured'])
                    logger.info(f"Auto-measured impact for {measured_count} improvements")
            except Exception as e:
                logger.error(f"Error in auto-measuring improvements: {e}")
            
            logger.info("Monitoring cycle completed")
            
        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}")
    
    def get_status(self) -> dict:
        """Get monitoring service status."""
        return {
            'running': self.running,
            'check_interval_minutes': self.check_interval_minutes,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'next_check': (self.last_check + timedelta(minutes=self.check_interval_minutes)).isoformat() 
                         if self.last_check else None
        }


class AlertNotificationService:
    """Service for sending alert notifications."""
    
    def __init__(self):
        self.alert_dao = get_alert_dao()
    
    def check_critical_alerts(self) -> list:
        """Check for critical alerts that need immediate attention."""
        try:
            alerts = self.alert_dao.get_active_alerts(limit=10)
            critical_alerts = [alert for alert in alerts if alert['severity'] == 'critical']
            
            if critical_alerts:
                logger.warning(f"Found {len(critical_alerts)} critical alerts requiring attention")
                for alert in critical_alerts:
                    logger.warning(f"CRITICAL ALERT: {alert['title']} - {alert['description']}")
            
            return critical_alerts
            
        except Exception as e:
            logger.error(f"Error checking critical alerts: {e}")
            return []
    
    def send_alert_digest(self, recipient: str = "admin") -> bool:
        """Send a digest of recent alerts (placeholder for email/notification integration)."""
        try:
            # Get recent alerts
            alerts = self.alert_dao.get_active_alerts(limit=20)
            summary = self.alert_dao.get_alert_summary(days=1)
            
            # In a real implementation, this would send an email or push notification
            logger.info(f"Alert digest for {recipient}:")
            logger.info(f"Active alerts: {summary['active_alerts']}")
            logger.info(f"Critical alerts: {summary['critical_alerts']}")
            logger.info(f"High priority alerts: {summary['high_alerts']}")
            
            # Log recent critical/high alerts
            for alert in alerts:
                if alert['severity'] in ['critical', 'high']:
                    logger.info(f"- {alert['severity'].upper()}: {alert['title']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending alert digest: {e}")
            return False


# Global monitoring service instance
_monitoring_service: Optional[MonitoringService] = None
_notification_service: Optional[AlertNotificationService] = None


def get_monitoring_service() -> MonitoringService:
    """Get or create the monitoring service instance."""
    global _monitoring_service
    if _monitoring_service is None:
        # Default to 60-minute intervals, can be configured
        settings = get_settings()
        interval = getattr(settings, 'monitoring_interval_minutes', 60)
        _monitoring_service = MonitoringService(check_interval_minutes=interval)
    return _monitoring_service


def get_notification_service() -> AlertNotificationService:
    """Get or create the notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = AlertNotificationService()
    return _notification_service


def start_monitoring():
    """Start the background monitoring service."""
    try:
        service = get_monitoring_service()
        service.start()
    except Exception as e:
        logger.error(f"Failed to start monitoring service: {e}")


def stop_monitoring():
    """Stop the background monitoring service."""
    try:
        service = get_monitoring_service()
        service.stop()
    except Exception as e:
        logger.error(f"Failed to stop monitoring service: {e}")


# Utility functions for manual monitoring operations

def run_immediate_check() -> dict:
    """Run an immediate monitoring check and return results."""
    try:
        monitor = get_feedback_monitor()
        alerts = monitor.run_monitoring_cycle()
        
        # Check for critical alerts
        notification_service = get_notification_service()
        critical_alerts = notification_service.check_critical_alerts()
        
        return {
            'success': True,
            'alerts_generated': len(alerts),
            'critical_alerts': len(critical_alerts),
            'timestamp': datetime.now().isoformat(),
            'alerts': [
                {
                    'type': alert.alert_type.value,
                    'severity': alert.severity.value,
                    'title': alert.title,
                    'description': alert.description
                }
                for alert in alerts
            ]
        }
        
    except Exception as e:
        logger.error(f"Error in immediate monitoring check: {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def get_monitoring_health() -> dict:
    """Get the health status of the monitoring system."""
    try:
        service = get_monitoring_service()
        alert_dao = get_alert_dao()
        
        # Get recent alert activity
        alert_summary = alert_dao.get_alert_summary(days=1)
        
        # Check if monitoring is working (has run recently)
        monitoring_healthy = True
        if service.last_check:
            time_since_check = datetime.now() - service.last_check
            # Consider unhealthy if no check in 2x the interval
            max_interval = timedelta(minutes=service.check_interval_minutes * 2)
            monitoring_healthy = time_since_check < max_interval
        
        return {
            'monitoring_service': {
                'running': service.running,
                'healthy': monitoring_healthy,
                'last_check': service.last_check.isoformat() if service.last_check else None,
                'check_interval_minutes': service.check_interval_minutes
            },
            'recent_activity': alert_summary,
            'system_status': 'healthy' if monitoring_healthy and service.running else 'degraded'
        }
        
    except Exception as e:
        logger.error(f"Error getting monitoring health: {e}")
        return {
            'system_status': 'error',
            'error': str(e)
        }