class Event:
    def __init__(self, source = None):
        self.source = source
    def getSource(self):
        return self.source

class EventSource:
    def __init__(self):
        self.event_listeners = []

    def notifyListeners(self, event):
        for l in self.event_listeners:
            l.notify(event)

    def addListener(self, listener):
        self.event_listeners.append(listener)
    
    def dropListener(self, listener):
        self.event_listeners.remove(listener)

class EventListener:
    def __init__(self):
        pass

    def notify(self, event): pass

class EventQueue:
    def __init__(self):
        self._events = []
    def push(self, event):
        self._events.append(event)
    def pop(self):
        return self._events.pop(0)
    def hasEvents(self):
        return len(self._events) > 0
    def __len__(self):
        return len(self._events)
