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

