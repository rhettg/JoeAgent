# JoeAgent - A Multi-Agent Distributed Application Framework
# Copyright (C) 2004 Rhett Garber

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
