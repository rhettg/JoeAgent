import agent, simple, job, event, timer, message
from xobject import XMLObject
import logging

log = logging.getLogger("agent.director")

PING_INTERVAL = 3.0
PING_TIMEOUT = 1.0

class PingJob(job.Job):
    """Job to handling pinging all the connected nodes a specified interval"""
    def notify(self, evt):
        job.Job.notify(self, evt)
        if isinstance(evt, PingEvent):
            log.debug("Pinging all connections")
            agnt = self.getAgent()
            for c in agnt.getConnections():
                if isinstance(c, agent.AgentConnection) and \
                        c.getAgentInfo() is not None:
                    evnt = agent.MessageSendEvent(self, agent.PingRequest(), c)
                    agnt.addEvent(evnt)
                    ptimer = PingTimeoutTimer(c)
                    self.outgoing[evnt.getMessage().getKey()] = ptimer
                    agnt.addTimer(ptimer)

            evt.getSource().addTimer(PingTimer(evt.getSource()))

        elif isinstance(evt, PingTimeoutEvent):
            log.debug("Ping timeout!")
            # A timer popped somewhere
            conn = evt.getSource()
            # This connection did not respond to the ping, drop it
            self.getAgent().dropConnection(evt.getSource())

        elif isinstance(evt, agent.MessageReceivedEvent) and \
             isinstance(evt.getMessage(), agent.PingResponse):
            log.debug("Ping Response recieved")
            # Our ping request finally responded
            key = evt.getMessage().getRequestKey()
            if self.outgoing.has_key(key):
                ptimer = self.outgoing[key]
                ptimer.stop()
                del self.outgoing[key]
                if evt.getSource().IsSelfConnected():
                    evt.getSource().disconnect()
            else:
                log.debug("Ping Response key did not match")

class PingEvent(event.Event):
    """Event to indicate its time to do another round of pinging"""
    pass

class PingTimeoutEvent(event.Event):
    """Event to indicate the ping timer has timedout, the connection
       failed to respond"""
    pass

class PingTimer(timer.Timer):
    def __init__(self, source = None):
        event = PingEvent(source)
        timer.Timer.__init__(self, PING_INTERVAL, event)

class PingTimeoutTimer(timer.Timer):
    def __init__(self, source):
        event = PingTimeoutEvent(source)
        timer.Timer.__init__(self, PING_TIMEOUT, event)

class ShutdownJob(job.Job):
    """The shutdown job is executed when a shutdown request is received.

    The job will send shutdown requests to all registered agents.

    When the job is complete, the director agent status will be set to STOPPING.
    This only happens once all the agents have responded to the request or 
    failed to respond to a Ping (indicating the agent is already unavailable).
    """
    def __init__(self, agnt):
        job.Job.__init__(self, agnt)
        self.agnt_conns = {}
        # We will be creating a hash which will associate each connection with
        # a message key. This way we can have multiple requests in play at once
        # and recognize who the reply is from.
        for conn in agnt.getConnections():
            if isinstance(conn, agent.AgentConnection) and \
               conn.getAgentInfo() is not None:
                self.agnt_conns[conn] = None

    def run(self):
        # Run will create ShutdownRequest messages for each agent connection
        for conn in self.agnt_conns.keys():
            log.debug("Sending shutdown request to agent %s" 
                      % conn.getAgentInfo().getName())
            msg = agent.ShutdownRequest()
            self.agnt_conns[conn] = msg.getKey()
            evt = agent.MessageSendEvent(self, msg, conn)
            self.getAgent().addEvent(evt)

    def notify(self, evt):
        job.Job.notify(self, evt)

        if isinstance(evt, agent.MessageReceivedEvent) and \
           isinstance(evt.getMessage(), message.Response):
            source = evt.getSource()
            if self.agnt_conns.has_key(source) and \
                self.agnt_conns[source] == evt.getMessage().getRequestKey():
                # this message is for us
                if isinstance(evt.getMessage(), agent.OkResponse):
                    log.info("Agent %s stopping" % source.getConfig().getName())

                else:
                    log.warning("Agent %s responded to shutdown with: %s" 
                                % (evt.getSource().getConfig().getName(), str(evt.getMessage())))

                # We delete the entry in the hash so that we know our shutdown
                # job for this agent is complete
                del self.agnt_conns[source]
                # Note, the director will continue pinging this connection even
                # after we know it is shutting down.


        elif isinstance(evt, PingTimeoutEvent):
            if self.agnt_conns.has_key(evt.getSource()):
                log.info("Connection %s disconnected without responding" 
                          % evt.getSource().getAgentInfo().getName())
                del self.agnt_conns[evt.getSource()]

        if len(self.agnt_conns) == 0 and self.getAgent().isRunning():
            # All agents have responded, we can shutdown
            self.getAgent().setState(agent.STOPPING)

class DirectorStatusResponse(simple.StatusResponse):
    """The response to a status request will contain in addition to basic
    status information the list of all the AgentInfo objects which were 
    registered with the Director"""
    def __init__(self, key = None):
        simple.StatusResponse.__init__(self, key)
        self.config = None
        self.agents = []

    def setConfig(self, config):
        self.config = config
    def getConfig(self):
        return self.config

    def addAgentInfo(self, agnt):
        assert isinstance(agnt, agent.AgentInfo)
        self.agents.append(agnt)

    def clearAgentInfoList(self):
        self.agents = []

    def getAgentInfoList(self):
        return self.agents

class Director(simple.SimpleAgent):
    """The director is a simple agent which sole purpose is to provide a small
    amount of central control for the application. All sub-agents will register
    themsevles with the director.

    Anytime another agent wishes to know what other agents exist, the director
    is the source for that information.

    For example, an agent which is responsible for checking the status of all
    the agents will need an up to date list of what agents are available and
    then will directly poll each agent to find out their respective statuses.

    The director will also do a heartbeat (Ping) to each registered agent to
    ensure they are still up and running.

    Shutting down the director is also special. If the director is shutdown,
    all the agents registered will also receive shutdown requests. When
    a shutdown is requested of the director, effectivly the request is
    broadcasted to all agents.
    """
    def getInitJobs(self):
        return simple.SimpleAgent.getInitJobs(self) + \
           [PingJob(self)]
    def getInitTimers(self):
        return simple.SimpleAgent.getInitTimers(self) + \
           [PingTimer(self)]

    def getStatusResponse(self, key):
        resp = DirectorStatusResponse(key)
        resp.setState(self.getState())
        resp.setConfig(self.getConfig())

        # The director status response consists of a list of all the agents
        # we are connected to. We need to extract all their AgentInfo
        # objects and add them to our response
        for c in self.getConnections():
            if isinstance(c, agent.AgentConnection):
                info = c.getAgentInfo()
                if info is not None:
                    resp.addAgentInfo(info)
        return resp

    def shutdown(self):
        # Director shutdown is special.
        # In addition to stopping ourselves, we will attempt to shutdown
        # all of the agents we are directing. All this is done in the 
        # Shutdown job
        log.debug("Starting shutdown")
        shutdown_job = ShutdownJob(self)
        self.addListener(shutdown_job)
        shutdown_job.run()
