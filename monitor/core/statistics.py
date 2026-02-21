"""
Statistics Tracker
Track uptime and disconnections
"""

from datetime import datetime
from collections import deque


class Statistics:
    """Simple statistics tracker."""
    
    def __init__(self):
        """Initialize statistics."""
        self.history = deque(maxlen=288)  # 24 hours at 5min intervals
        self.total_checks = 0
        self.online_checks = 0
        self.today = datetime.now().date()
    
    def add_check(self, is_online: bool):
        """Add check result."""
        now = datetime.now()
        
        # Reset on new day
        if now.date() != self.today:
            self.total_checks = 0
            self.online_checks = 0
            self.today = now.date()
        
        self.total_checks += 1
        if is_online:
            self.online_checks += 1
        
        self.history.append({'time': now, 'online': is_online})
    
    def get_uptime_today(self) -> float:
        """Get uptime percentage for today."""
        if self.total_checks == 0:
            return 0.0
        return (self.online_checks / self.total_checks) * 100
    
    def get_disconnections_today(self) -> int:
        """Get number of disconnections today."""
        count = 0
        was_online = True
        
        for entry in self.history:
            if entry['time'].date() != self.today:
                continue
            
            if not entry['online'] and was_online:
                count += 1
            was_online = entry['online']
        
        return count
