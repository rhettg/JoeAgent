import logging
log = logging.getLogger("agent.timer")


import time
STOPPED = 0
RUNNING = 1

class Timer:
    def __init__(self, interval, event):
        self.state = STOPPED
        self.interval = interval
        self.event = event
        self.create_time = 0
        self.stop_time = 0

    def getEvent(self):
        return self.event

    def getStartTime(self):
        return self.start_time
    def getStopTime(self):
        return self.stop_time

    def isRunning(self):
        return self.state == RUNNING
    def isPopped(self):
        return self.isRunning() and \
           self.create_time + self.interval < time.time()

    def getTimeLeft(self):
        log.debug("C: %f  I: %f   N: %f" % (self.create_time, self.interval, time.time()))
        time_left = (self.create_time + self.interval) - time.time()
        if time_left < 0:
            time_left = 0
        return time_left
    
    def start(self):
        self.state = RUNNING
        self.create_time = time.time()
        self.stop_time = 0

    def stop(self):
        self.state = STOPPED
        self.stop_time = time.time()

class TimerCollection:
    """A timer collection is held by and agent. Each agent has just one.

    The TimerCollection provides storage for timers and methods for
    checking if a timer as expired or when the next timeout is."""
    def __init__(self):
        self.timers = []

    def add(self, timer):
        """Add a timer to the collection"""
        timer.start()
        self.timers.append(timer)

    def nextTimeoutValue(self):
        """Return how many seconds (float) before the next timer will
        expire"""
        min = None
        for t in self.timers:
            if min is None or t.getTimeLeft() < min:
                min = t.getTimeLeft()
        return min

    def remove(self, timer):
        """Remove the timer from the collection"""
        assert isinstance(timer, Timer), "Not a timer: %s" % str(timer)
        # checkTimers will clear out stopped timers
        timer.stop()

    def checkTimers(self):
        """Check timers to see if anyone has expired.  Also takes care
        of cleaning up previously timers we should keep around any
        longer (expired or stopped) """
        popped = []
        for t in self.timers:
            if t.isPopped():
                t.stop()
                popped.append(t.getEvent())
                self.timers.remove(t)
            elif not t.isRunning():
                self.timers.remove(t)
        
        return popped
    
    def __len__(self):
        return len(self.timers)
