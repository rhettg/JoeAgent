import logging
log = logging.getLogger("agent.simple")

import agent, job, utils, event, message, timer

CONNECT_RETRY = 3.0

class ConnectRequest(agent.Request): 
    def __init__(self, info = None):
        agent.Request.__init__(self)
        self.info = info
    def getInfo(self):
        return self.info

class ConnectionRequestTimeoutEvent(agent.ConnectionEvent):
    """This event is generated when a connection has not returned
    a connection request in time"""
    pass

class ConnectionRequestTimer(timer.Timer):
    """Timer for connection to deliver a connection request in time"""
    def __init__(self, source = None):
        event = ConnectionConfTimeoutEvent(source)
        timer.Timer.__init__(self, CONFIG_TIMEOUT, event)

class HandleConnectJob(job.Job):
    """When an agent connects to us, it will request connect and provide us
    with its info object. This allows us to know what kind of agent it is
    and connect to its server port if it has one"""
    def notify(self, evt):
        job.Job.notify(self, evt)
        if isinstance(evt, agent.MessageReceivedEvent) and \
           isinstance(evt.getMessage(), ConnectRequest):
               evt.getSource().setAgentInfo(evt.getMessage().getInfo())
               
               out_msg = agent.OkResponse(evt.getMessage().getKey())
               assert out_msg.getRequestKey() != None, "Key is None"
               e = agent.MessageSendEvent(self, out_msg, evt.getSource())
               self.getAgent().addEvent(e)

class HandlePingJob(job.Job):
    """Respond to a Ping Request"""
    def notify(self, evt):
        job.Job.notify(self, evt)
        if isinstance(evt, agent.MessageReceivedEvent) and \
           isinstance(evt.getMessage(), agent.PingRequest):
            log.debug("Replying to ping to %s" % evt.getSource().getName())
            msg = evt.getMessage()
            key = msg.getKey()
            conn = evt.getSource()
            resp = agent.PingResponse(key)
            self.getAgent().addEvent(
                               agent.MessageSendEvent(self, resp, conn))

class HandleShutdownJob(job.Job):
    def notify(self, evt):
        job.Job.notify(self, evt)
        if isinstance(evt, agent.MessageReceivedEvent) and \
           isinstance(evt.getMessage(), agent.ShutdownRequest):
            log.debug("Handling shutdown")
            agnt = self.getAgent()
            in_msg = evt.getMessage()
            key = in_msg.getKey()
            if evt.getSource().isAuthorized(in_msg):
                log.debug("Shutting down")
                # Stop the agent
                agnt.shutdown()
                # Respond 'Ok'
                out_msg = agent.OkResponse(key)
            else:
                log.debug("Not authorized for shutdown")
                # Respond 'Denied'
                out_msg = agent.DeniedResponse(key)

            agnt.addEvent(agent.MessageSendEvent(
                                         self, out_msg, evt.getSource()))

class ConnectCompleteEvent(event.Event):
    def __init__(self, source, connection):
        event.Event.__init__(self, source)
        self.connection = connection
    def getConnection(self):
        return self.connection

class ConnectFailedEvent(event.Event): pass

class ConnectRetryEvent(event.Event): pass

class ConnectRetryTimer(timer.Timer):
    def __init__(self, source = None):
        evt = ConnectRetryEvent(source)
        timer.Timer.__init__(self, CONNECT_RETRY, evt)

class ConnectJob(job.Job):
    """The ConnectJob will attempt to open a connection to a remote agent.
    Upon opening the socket, it will deliver our own info object in a 
    ConnectionRequest object. We will attempt to connect for max_retries
    number of times. Eventually, if a OkResponse is received, we will
    create a ConnectCompleteEvent to notify anyone who cares that the
    connection was successful"""
    def __init__(self, agent_obj, agent_info, max_retries = -1, 
                 send_msg = None):
        job.Job.__init__(self, agent_obj)
        self.key = None
        self._max_retries = max_retries
        self._retries = 0
        self._connection = None
        self._send_msg = send_msg

        # The agent we are going to connect to
        self.info = agent_info

    def run(self):
        log.debug("Running ConnectJob") 
        self._connect()

    def notify(self, evt):
        job.Job.notify(self, evt)
        if isinstance(evt, agent.MessageReceivedEvent):
            if isinstance(evt.getMessage(), agent.OkResponse) and \
               self.key == evt.getMessage().getRequestKey():
                evt = ConnectCompleteEvent(self, evt.getSource())
                self.getAgent().addEvent(evt)

                # we have successfully connect, stop retrying
                self._timer.stop()
                self._timer = None
            elif isinstance(evt.getMessage(), agent.DeniedResponse) and \
               self.key == evt.getMessage().getRequestKey():
                log.warning("Connect to %s failed, request denied" 
                            % self.info.getName())

        elif isinstance(evt, ConnectRetryEvent) and evt.getSource() == self:
            log.info("Attempting to reconnect to remote agent")
            self._retries += 1
            self._connect()

        elif isinstance(evt, ConnectCompleteEvent) and evt.getSource() == self:
            # This job is complete
            self.getAgent().dropListener(self)
            if isinstance(self._send_msg, agent.MessageSendEvent):
                self.getAgent().addEvent(agent.MessageSendEvent)

    def getConnection(self):
        return self._connection
    
    def _set_retry_timer(self):
        self._timer = ConnectRetryTimer(self)
        self.getAgent().addTimer(self._timer)

    def _connect(self):
        # Create connection to remote agent
        if self._max_retries == -1 or self._max_retries >= self._retries:
            connection = agent.AgentConnection(self.info)
            connection.connect()
            if connection.isConnected():
                self.getAgent().addConnection(connection)
                self._connection = connection

                # Send Connect Request
                msg = ConnectRequest(self.getAgent().getInfo())
                self.key = msg.getKey()
                evt = agent.MessageSendEvent(self, msg, connection)
                self.getAgent().addEvent(evt)

            self._set_retry_timer()
        else:
            # This job is complete
            self.getAgent().dropListener(self)
            self.getAgent().addEvent(ConnectFailedEvent(self))

            
class StatusRequest(message.Request): pass

class StatusResponse(message.Response):
    def __init__(self, key = None):
        message.Response.__init__(self, key)
        self.status_details = ""
        self.state = None

    def getStatusDetails(self):
        return self.status_details
    def setStatusDetails(self, details):
        self.status_details = details

    def getState(self):
        return self.state
    def setState(self, new_state):
        self.state = new_state

class HandleStatusJob(job.Job):
    def notify(self, evt):
        job.Job.notify(self, evt)
        if isinstance(evt, agent.MessageReceivedEvent):
            if isinstance(evt.getMessage(), StatusRequest):
                key = evt.getMessage().getKey()
                if evt.getSource().isAuthorized(evt.getMessage()):
                    resp = self.getAgent().getStatusResponse(key)
                else:
                    resp = agent.DeniedResponse(key)

                msg = agent.MessageSendEvent(self, resp, evt.getSource())
                self.getAgent().addEvent(msg)


class SimpleAgentConfig(agent.AgentConfig):
    def getAgentClass(self):
        return SimpleAgent

class SimpleAgent(agent.Agent):
    def __init__(self, config):
        agent.Agent.__init__(self, config)

        # Add all our inital jobs
        for j in self.getInitJobs():
            self.addListener(j)

        # Add all our initial events
        for e in self.getInitEvents():
            self.addEvent(e)

        # Add all our initial timers
        for t in self.getInitTimers():
            self.addTimer(t)

    def getInitJobs(self):
        """Return list of jobs that this agent should have at 
           initialize time."""
        return [
            HandleConnectJob(self),
            HandlePingJob(self),
            HandleShutdownJob(self),
            HandleStatusJob(self)
        ]

    def getInitEvents(self):
        """Return a list of events that should be in the event queue as soon
           as the agent is started. For example, a job.RunJobEvent for running
           one of the jobs at start time."""
        return []

    def getInitTimers(self):
        """Return a list of timers to start at run time"""
        return []

    def getStatusResponse(self, key):
        """Return status response object for this agent. May be rededfined
        by sub-classes for custom responses"""
        resp = StatusResponse(key)
        resp.setState(self.getState())
        return resp
    
    def handleMessageSendEvent(self, event):
        agent.Agent.handleMessageSendEvent(self, event)

        # We are extending handleMessageSendEvent to handle the case where
        # the target is defined by a AgentInfo object. If this is the case,
        # we will need to find a proper connection object (or create one)
        if isinstance(event.getTarget(), agent.AgentInfo):
            conn = self.getConnectionByInfo(event.getTarget())
            if conn is None:
                log.debug(
                  "Connection to %s does not yet exist, creating ConnectJob" 
                   % event.getTarget().getName())

                jb = ConnectJob(self, event.getTarget(), 1, event)
                self.addListener(jb)
                self.addEvent(job.RunJobEvent(self, jb))
            else:
                conn.write(str(event.getMessage()))

    def getHandlers(self):
        handlers = agent.Agent.getHandlers(self)
        handlers[agent.MessageSendEvent] = SimpleAgent.handleMessageSendEvent
        return handlers

class SubAgentConfig(agent.AgentConfig):
    """SubAgents have the special need of connecting to a director agent.
       The subagent will need the configuration information for the 
       director so that it may connect to it."""
    def __init__(self):
        agent.AgentConfig.__init__(self)
        self.director_info = None

    def getDirectorInfo(self):
        return self.director_info
    def setDirectorInfo(self, info):
        self.director_info = info

    def getAgentClass(self):
        return SubAgent

class SubAgent(SimpleAgent):
    def __init__(self, config):
        self._dir_connect_job = None
        SimpleAgent.__init__(self, config)

    def getInitJobs(self):
        # We need a job to connect to our director agent.
        self._dir_connect_job = ConnectJob(self, 
                                  self.getConfig().getDirectorInfo(), -1)
        return SimpleAgent.getInitJobs(self) + [self._dir_connect_job]

    def getInitEvents(self):
        # We want to connect to our director agent as soon as this agent starts
        # up so we add a RunJobEvent so that it will run the ConnectJob as
        # soon as it gets processed
        assert self._dir_connect_job is not None, "Connect job not yet defined"
        return SimpleAgent.getInitEvents(self) + \
               [job.RunJobEvent(self, self._dir_connect_job)]
