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

from xobject import XMLObject

class Message(XMLObject): pass

class Request(Message):
    """Special class of Message which indicates we are requesting the intended
    target to do something"""
    def __init__(self):
        Message.__init__(self)
        self.key = str(id(self))
    def getKey(self):
        """Return a unique key that will be again provided in the response"""
        return self.key

class Response(Message):
    """Special class of Message which is a responding to a request object."""
    def __init__(self, key = None):
        Message.__init__(self)
        self.key = key
    def setRequestKey(self, key):
        self.key = key
    def getRequestKey(self):
        return self.key
