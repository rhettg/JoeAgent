import socket, logging
import xml.sax.expatreader
import timer, event, xobject
from xobject import XMLObject, EndOfObjectException
from event import Event, EventSource, EventListener
from select import select
from message import Message, Request, Response

# These should be classes
class AgentState(XMLObject): 
    def __equal__(self, object):
        if object is None:
            return False
        return object.__class__ == self.__class__
    def getName(self):
        return "Unknown State"

class StoppedState(AgentState):
    def getName(self):
        return "Stopped State"

class StartingState(AgentState):
    def getName(self):
        return "Starting State"

class RunningState(AgentState):
    def getName(self):
        return "Running State"

class StoppingState(AgentState):
    def getName(self):
        return "Stopping State"

STOPPED     = StoppedState()
STARTING    = StartingState()
RUNNING     = RunningState()
STOPPING    = StoppingState()

BUFF_SIZE = 1024

# Seconds we give a new socket to request a connection
CONFIG_TIMEOUT = 2.0

log = logging.getLogger("agent")

class AgentInfo(XMLObject):
    """Basic information about an agent."""
    def __init__(self, config = None):
        self.host = None
        self.port = None
        self.name = ""
        self.class_name = ""

        if config is not None:
            self.setHost(config.getBindAddress())
            self.setPort(config.getPort())
            self.setName(config.getName())
            self.setClassName(str(config.getAgentClass()))

        XMLObject.__init__(self)

    def getHost(self):
        return self.host
    def setHost(self, addr):
        self.host = addr

    def getPort(self):
        return self.port
    def setPort(self, port):
        self.port = port

    def getName(self):
        return self.name
    def setName(self, name):
        self.name = name

    def getClassName(self):
        return self.class_name
    def setClassName(self, name):
        self.class_name = name
    
    def __eq__(self, info):
        return info != None and self.__class__ == info.__class__ and \
               self.getName() == info.getName() and \
               self.getClassName() == info.getClassName() and \
               self.getHost() == info.getHost() and \
               self.getPort() == info.getPort()

class AgentConfig(XMLObject):
    """This is the basic configuration class for an agent. An agent config 
       consists of a address and port to bind to, as well as a name to 
       uniquely identify itself. Derived agents will have extra configuration
       information as well.
    """
    def __init__(self):
        self.bind_addr = None
        self.port = None
        self.name = "Unnamed"
        self.logging_path = ""

    def getBindAddress(self):
        return self.bind_addr
    def setBindAddress(self, addr):
        self.bind_addr = addr

    def getPort(self):
        return self.port
    def setPort(self, port):
        self.port = port

    def getName(self):
        return self.name
    def setName(self, name):
        self.name = name

    def getLoggingPath(self):
        return self.logging_path
    def setLoggingPath(self, path):
        self.logging_path = path

    def getAgentClass(self):
        return Agent

# Special Messages for generic agents
class ShutdownRequest(Request): 
    """Tell an agent to shutdown"""
    pass
class PingRequest(Request): 
    """A request for an agent to reply with a PingResponse"""
    pass

class OkResponse(Response): pass
class DeniedResponse(Response): pass
class PingResponse(Response): pass

class UnsupportedResponse(Response): pass

# Special Events for generic agents
class ConnectionEvent(Event): pass

class ConnectEvent(ConnectionEvent):
    """Event generated when a connection is made"""
    def __init__(self, source, conn):
        self.conn = conn
        Event.__init__(self, source)
    def getNewConnection(self):
        return self.conn

class ConnectionReadEvent(ConnectionEvent):
    """Event that will cause the source Connection to be read from"""
    pass

class ConnectionWriteEvent(ConnectionEvent):
    """Event that will cause the source Connection to be written to"""
    pass

class ConnectionExceptionEvent(ConnectionEvent):
    """Event that indicates the source Connection has encountered a network
    problem. Probably a disconnect."""
    pass

class MessageEvent(Event):
    """Generic event base class for any incomming or outgoing message"""
    def __init__(self, source, msg):
        self.message = msg
        Event.__init__(self, source)
    def getMessage(self):
        return self.message
    def setMessage(self, obj):
        self.message = msg

class MessageReceivedEvent(MessageEvent): 
    """Event that indicates we have received a message. The event's source
    will be connection that received the message"""
    pass

class MessageSendEvent(MessageEvent):
    """Event that indicates we should be sending this event to the selected
    destination"""
    def __init__(self, source, message, target):
        MessageEvent.__init__(self, source, message)
        self._target = target
    def getTarget(self):
        return self._target

class StateChangeEvent(Event):
    """Event to indicate that the agent has changed states"""
    def __init__(self, source, old_state, new_state):
        Event.__init__(self, source)
        self.old_state = old_state
        self.new_state = new_state
    
    def getOldState(self):
        return self.old_state
    def getNewState(self):
        return self.new_state

class ConnectException(Exception): pass

class Connection:
    def __init__(self, sock = None):
        self.sock = sock

    def setSocket(self, sock):
        self.sock = sock
    def getSocket(self):
        return self.sock
    
    def getName(self):
        return "Unnamed"

    def fileno(self):
        return self.sock.fileno()
    
    def isConnected(self):
        return self.sock is not None
    
    def disconnect(self):
        log.debug("Disconnecting connection to %s" % self.getName())

        if self.sock is not None:
            self.sock.close()
        self.sock = None

    def connect(self):
        raise Exception("Not supported")
    
    def read(self):
        return self.sock.recv(BUFF_SIZE)
    def write(self, msg):
        try:
            sent = self.sock.send(msg)
        except socket.error, e:
            log.exception("Exception during send")
            self.disconnect()
        return sent
    def isReadPending(self):
        log.debug("Base class Connection polled for ReadPending")
        return False
    def isWritePending(self):
        return False

class AgentConnection(Connection):
    def __init__(self, conn_info = None, sock = None):
        Connection.__init__(self, sock)
        self.conn_info = conn_info
        self.out_buffer = ""
        self.in_buffer = ""
        self.conn_timer = None
        self.self_connect = False
        self.parser = xml.sax.expatreader.ExpatParser()
        self.parser.setFeature(xml.sax.expatreader.feature_namespaces, 0)
        self.parser_hndlr = xobject.SingleXMLObjectHandler()
        self.parser.setContentHandler(self.parser_hndlr)

        self.parser.reset()
        self.parser._cont_handler.setDocumentLocator(
                                 xml.sax.expatreader.ExpatLocator(self.parser))
    
    def getAgentInfo(self):
        return self.conn_info
    def setAgentInfo(self, info):
        self.conn_info = info
    
    def getName(self):
        if self.getAgentInfo() is not None:
            return self.getAgentInfo().getName()
        else:
            return "Unnamed"

    def isAuthorized(self, request):
        """Is this connection authorized for the specific request. For now
        we just require that the connection request was made. In the future
        we can require a shutdown to come from a proper x509 certificate or
        something."""
        return self.getAgentInfo() is not None

    def isSelfConnected(self):
        """Is the open connection opened by us, or by the remote side"""
        return self.self_connect

    def disconnect(self):
        Connection.disconnect(self)
        self.out_buffer = ""
        self.self_connect = False

    def connect(self):
        if self.isConnected():
            raise Exception("Connection already established")

        if self.getAgentInfo() is None or \
           self.getAgentInfo().getHost() is None:
            raise ConnectException("Do not know who to connect to")

        self.self_connect = True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.getAgentInfo().getHost(), 
                               int(self.getAgentInfo().getPort())))
        except socket.error, e:
            log.error("Error connecting to agent %s: %s" % \
                      (str(self.getAgentInfo().getName()), str(e)))
            self.sock = None
        
    def read(self):
        """This method should only be called when we know there is data
        waiting (by using select, for example). Data read is fed into the
        XML parser. When an XMLObject is completely read, it will be wrapped
        in a MessageReceivedEvent and handed back to the caller."""

        log.debug("Connection read")
        obj = None
        try:
            self.in_buffer = Connection.read(self)
            if self.in_buffer == "":
                log.debug("Read 0, disconnect")
                self.disconnect()
                return None
            while self.in_buffer != "":
                self.parser.feed(self.in_buffer)
                self.in_buffer = Connection.read(self)
        except EndOfObjectException, e:
            obj = e.getObject()
            self.parser.reset()
            self.parser_hndlr.reset()
        except socket.error, e:
            log.exception("Exception from socket")
            self.disconnect()

        if isinstance(obj, Message):
            obj = MessageReceivedEvent(self, obj)
        else:
            log.debug("Unknown obj %s" % str(obj))
            obj = None

        return obj

    def write(self, buffer = ""):
        log.debug("Connection Write")
        if not self.isConnected():
            try:
                self.connect()
            except ConnectException, e:
                log.debug("Failed to (re)connect to agent. Not writing")
            return

        sent = 0
        self.out_buffer += str(buffer)
        try:
            sent = Connection.write(self, self.out_buffer)
        except socket.error, e:
            log.exception("Exception during send")
            self.disconnect()
        self.out_buffer = self.out_buffer[sent:]
        log.debug("%d chars sent" % sent)

    def isReadPending(self):
        """If the socket is open, we will always say we are ready for read.
        This assumes the caller is only inspecting this socket when there
        is data ready. We do not want to check for data here because we do 
        not want to block."""
        return self.isConnected()

    def isWritePending(self):
        """We only want to write data if we are connected and have data
        waiting in the out_buffer"""
        return self.isConnected() and len(self.out_buffer) > 0

class ServerConnection(Connection):
    """Subclass of Connection which represents a socket which is listening 
    for incoming connections"""
    def __init__(self, sock = None):
        Connection.__init__(self, sock)

    def read(self):
        log.debug("Accepting new connection")
        new_sock, new_addr = self.sock.accept()
        log.debug("%s connected" % str(new_addr))
        return ConnectEvent(self, AgentConnection(None, new_sock))

    def isReadPending(self):
        return True

def create_server_socket(address, port):
    """Utility for creating a server socket"""
    srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv_sock.bind((address, port))
    srv_sock.listen(5)
    return srv_sock

class Agent(EventSource, EventListener):
    def __init__(self, config):
        from timer import TimerCollection
        from event import EventQueue
        self.state = STOPPED
        self.config = config
        self._info = None
        self.connections = []
        self.event_queue = EventQueue()
        self.timers = TimerCollection()
        EventSource.__init__(self)
        EventListener.__init__(self)

        # Yes we are a listener to ourselves
        self.addListener(self)

        self.setState(STARTING)
        if self.config.getBindAddress() != None and \
           self.config.getPort() != None:
            log.debug("Initializing server on %s:%d" % 
                    (self.config.getBindAddress(), self.config.getPort()))
            srv_sock = create_server_socket(self.config.getBindAddress(),
                                            self.config.getPort())
            self.addConnection(ServerConnection(srv_sock))
            log.debug("Server initialized")

        else:
            log.debug("Initialized non-server agent")

    def getConnections(self):
        return self.connections
    def getConnection(self, name):
        for c in self.connections:
            if c.getName() == name:
                return c
        return None
    def getConnectionByInfo(self, info):
        for c in self.connections:
            if isinstance(c, AgentConnection):
                if c.getAgentInfo() == info:
                    return c
        return None
    def addConnection(self, conn):
        self.connections.append(conn)
        log.debug("Connection Added (%d)" % (len(self.connections)))
    def dropConnection(self, conn):
        self.connections.remove(conn)
        log.debug("Connection Dropped (%d)" % (len(self.connections)))
    
    def addEvent(self, event):
        self.event_queue.push(event)
        log.debug("Event Added (%d)" % (len(self.event_queue)))
    def addTimer(self, timer):
        self.timers.add(timer)
        log.debug("Timer Added (%d)" % (len(self.timers)))
    def dropTimer(self, timer):
        self.timers.remove(timer)
        log.debug("Timer Removed (%d)" % (len(self.timers)))

    def getConfig(self):
        return self.config

    def getInfo(self):
        if self._info is None:
            self._info = AgentInfo(self.getConfig())
        return self._info

    def getState(self):
        return self.state
    def setState(self, state):
        self.addEvent(StateChangeEvent(self, self.state, state))
        if self.state != state:
            self.state = state
    def isRunning(self):
        return self.state == RUNNING

    # Event Handlers
    def handleConnectionReadEvent(self, event):
        log.debug("Handling Read Event")
        obj = event.getSource().read()
        if obj != None:
            self.addEvent(obj)

    def handleConnectionWriteEvent(self, event):
        log.debug("Handling Write Event")
        event.getSource().write()

    def handleConnectionExceptionEvent(self, event):
        log.debug("Handling Connection Exception Event")
        event.getSource().disconnect()
        self.dropConnection(event.getSource())

    def handleConnectEvent(self, event):
        log.debug("Handling connect event")
        self.addConnection(event.getNewConnection())

    def handleMessageRecievedEvent(self, event):
        # All we will do a receive event is log it.
        # Its up to one of our listeners to care about it.
        log.debug("Received a message of type %s" 
                   % str(event.getMessage().__class__))
        if isinstance(event.getMessage(), Request):
            log.debug("Request: %s" % str(event.getMessage()))
        if isinstance(event.getMessage(), Response):
            log.debug("Response: %s" % str(event.getMessage()))

    def handleMessageSendEvent(self, event):
        log.debug("Sending a message of type %s" 
                   % str(event.getMessage().__class__))
        if isinstance(event.getMessage(), Request):
            log.debug("Request: %s" % event.getMessage().getKey())
        if isinstance(event.getMessage(), Response):
            log.debug("Response: %s" % str(event.getMessage()))

        if isinstance(event.getTarget(), AgentInfo):
            job = ConnectJob()
        event.getTarget().write(str(event.getMessage()))


    _handlers = {
                 ConnectionReadEvent:       handleConnectionReadEvent,
                 ConnectionWriteEvent:      handleConnectionWriteEvent,
                 ConnectionExceptionEvent:  handleConnectionExceptionEvent,
                 MessageSendEvent:          handleMessageSendEvent,
                 MessageReceivedEvent:      handleMessageRecievedEvent,
                 ConnectEvent:              handleConnectEvent
               }

    def getHandlers(self):
        return Agent._handlers

    def notify(self, evt):
        found = 0
        hndlrs = self.getHandlers()
        for h in hndlrs.keys():
            if isinstance(evt, h):
                hndlrs[h](self, evt)
                found = 1

    def processEvent(self):
        """Process a single event from the event_queue"""
        log.debug("Going to handle an event")
        event = self.event_queue.pop()
        if event != None:
            log.debug("Handling event %s" % str(event))
            self.notifyListeners(event)

    def shutdown(self):
        log.debug('Shutting down agent')
        self.setState(STOPPING)

    def run(self):
        self.setState(RUNNING)
        while self.isRunning() or self.event_queue.hasEvents():
            should_handle_events = 1
            write_pending = []
            read_pending = []
            excep_pending = []
            for c in self.connections:
                if c.isWritePending():
                    write_pending.append(c)
                if c.isReadPending():
                    read_pending.append(c)
                if c.isConnected():
                    excep_pending.append(c)

            if self.event_queue.hasEvents():
                timeout = 0.0
            else:
                log.debug("Event Queue is empty")
                timeout = self.timers.nextTimeoutValue()
                should_handle_events = 0

            log.debug("Going into select (R:%d W:%d, X:%d for %s sec)" %
                              (len(read_pending), len(write_pending), 
                               len(excep_pending), str(timeout)))
            reads, writes, exceps = select(
                        read_pending, write_pending, excep_pending, timeout)

            for event in self.timers.checkTimers():
                self.addEvent(event)

            for e in exceps:
                log.debug("Handling exception for %s" % str(e))
                self.notifyListeners(ConnectionExceptionEvent(e))
                should_handle_events = 0
            
            for w in writes:
                log.debug("%s requests a write" % str(w))
                self.notifyListeners(ConnectionWriteEvent(w))
                should_handle_events = 0

            for r in reads:
                log.debug("%s requests a read" % str(r))
                self.notifyListeners(ConnectionReadEvent(r))
                should_handle_events = 0

            if should_handle_events:
                self.processEvent()
        
        log.debug("Cleaning up event queue")
        while self.event_queue.hasEvents():
            self.processEvent()
        log.debug("Event queue empty, all events processed. Ok to shutdown")
