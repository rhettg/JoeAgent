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

# Seconds we give a connection to deliver a config object
CONFIG_TIMEOUT = 2.0

log = logging.getLogger("agent")

class AgentConfig(XMLObject):
    """This is the basic configuration class for an agent. An agent config 
       consists of a address and port to bind to, as well as a name to 
       uniquely identify itself.

       This configuration will be sent to the Director agent to register
       this agent.
    """
    def __init__(self):
        self.bind_addr = None
        self.port = None
        self.name = "Unnamed"
        XMLObject.__init__(self)

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

# Special Messages for generic agents
class ConfigRequest(Request):
    """Tell an incoming agent that you require a config object"""
    pass
class ShutdownRequest(Request): 
    """Tell an agent to shutdown"""
    pass
class PingRequest(Request): 
    """A request for an agent to reply with a PingResponse"""
    pass

class OkResponse(Response): pass
class DeniedResponse(Response): pass
class PingResponse(Response): pass
class ConfigResponse(Response):
    """Response to a ConfigRequest which contains a AgentConfig for the 
    connection"""
    def getConfig(self):
        return self.getObjects(AgentConfig)

class UnsupportedResponse(Response): pass

# Special Events for generic agents
class ConnectionEvent(Event): pass

class ConnectEvent(ConnectionEvent):
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


class ConnectionConfTimeoutEvent(ConnectionEvent): 
    """This event is generated when a connection has not returned
    a config response in time"""
    pass

class ConnectionConfigTimer(timer.Timer):
    def __init__(self, source = None):
        event = ConnectionConfTimeoutEvent(source)
        timer.Timer.__init__(self, CONFIG_TIMEOUT, event)

class Connection:
    def __init__(self, config = None, sock = None):
        self.config = config
        self.sock = sock
        self.out_buffer = ""
        self.in_buffer = ""
        self.conn_timer = None
        self.self_connect = False
        self.parser = xml.sax.expatreader.ExpatParser()
        self.parser.setFeature(xml.sax.expatreader.feature_namespaces, 0)
        self.parser_hndlr = xobject.ObjectHandler()
        self.parser.setContentHandler(self.parser_hndlr)

        self.parser.reset()
        self.parser._cont_handler.setDocumentLocator(
                                 xml.sax.expatreader.ExpatLocator(self.parser))
    
    def setSocket(self, sock):
        self.sock = sock
    def getSocket(self):
        return self.sock
    
    def getConfig(self):
        return self.config
    def setConfig(self, config):
        self.config = config
    
    def getName(self):
        if self.getConfig() is not None:
            return self.getConfig().getName()
        else:
            return "Unnamed"

    def fileno(self):
        return self.sock.fileno()
    
    def isConnected(self):
        return self.sock != None
    
    def isAuthorized(self, request):
        return self.config != None

    def IsSelfConnected(self):
        """Is the open connection opened by us, or by the remote side"""
        return self.self_connect

    def disconnect(self):
        log.debug("Disconnecting connection to %s" % self.getName())

        self.out_buffer = ""
        self.sock.close()
        self.sock = None
        self.self_connect = False

    def connect(self):
        if self.isConnected():
            raise Exception("Connection already established")
        if self.config == None:
            raise Exception("Configuration not set")
        self.self_connect = True
        if self.config.getBindAddress() is None or \
           self.config.getBindAddress() == 'None':
            log.info("Connection %s has not call back information" 
                      % str(self))
            return
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.config.getBindAddress(), int(self.config.getPort())))
        except socket.error, e:
            log.error("Error connecting to agent %s: %s" % \
                      (str(self.getName()), str(e)))
            self.sock = None
        
    def read(self):
        log.debug("Connection read")
        obj = None
        try:
            self.in_buffer = self.sock.recv(BUFF_SIZE)
            if self.in_buffer == "":
                log.debug("Read 0, disconnect")
                self.disconnect()
                return None
            while self.in_buffer != "":
                self.parser.feed(self.in_buffer)
                self.in_buffer = self.sock.recv(BUFF_SIZE)
        except EndOfObjectException, e:
            obj = e.getObject()
            self.parser.reset()
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
            self.connect()
            return
        sent = 0
        self.out_buffer += buffer
        try:
            sent = self.sock.send(self.out_buffer)
        except socket.error, e:
            log.exception("Exception during send")
            self.disconnect()
        self.out_buffer = self.out_buffer[sent:]
        log.debug("%d chars sent" % sent)

    def isReadPending(self):
        return self.isConnected()

    def isWritePending(self):
        return self.isConnected() and len(self.out_buffer) > 0

class ServerConnection(Connection):
    """Subclass of Connection which represents a socket which is listening 
    for incoming connections"""
    def __init__(self, sock = None):
        Connection.__init__(self, None, sock)

    def read(self):
        log.debug("Accepting new connection")
        new_sock, new_addr = self.sock.accept()
        log.debug("%s connected" % str(new_addr))
        return ConnectEvent(self, Connection(None, new_sock))
    def write(self, msg):
        raise Exception("Not supported for ServerConnections")

def create_server_socket(address, port):
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