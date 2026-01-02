def _calculate_next_fire_time(self):
        """Estimate when the boiler will next fire based on schedule and learning."""
        # If currently heating, return "Now" (or None)
        if self._is_active_heating:
            return dt_util.now().isoformat()
            
        # Get next schedule block
        next_sched = self._get_next_schedule_start()
        if not next_sched:
            return None
            
        # If preheat disabled, it's just the schedule time
        if not self._enable_preheat:
            return next_sched.isoformat()
            
        # Calculate time needed
        comfort_target = 20.0 # Standard comfort
        current = self._current_temp if self._current_temp else 20.0
        
        diff = comfort_target - current
        if diff <= 0:
            # Already warm enough, fire AT schedule time
            return next_sched.isoformat()
            
        minutes_needed = diff / self._heat_up_rate
        # Clamp to max allowed preheat
        minutes_needed = min(minutes_needed, self._max_preheat_time)
        
        fire_time = next_sched - timedelta(minutes=minutes_needed)
        
        # If fire time is in the past (we are late!), return now
        now = dt_util.now()
        if fire_time < now:
            return now.isoformat()
            
        return fire_time.isoformat()
