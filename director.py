import socket
import agent, simple, job, event, timer, utils, message
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
                if c.getConfig() is not None and \
                   not isinstance(c, agent.ServerConnection):
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
    def __init__(self, agnt):
        job.Job.__init__(self, agnt)
        self.agnt_conns = {}
        for conn in agnt.getConnections():
            if conn.getConfig() is not None:
                self.agnt_conns[conn] = None

    def run(self):
        for agnt in self.agnt_conns.keys():
            log.debug("Sending shutdown request to agent %s" 
                      % agnt.getConfig().getName())
            msg = agent.ShutdownRequest()
            self.agnt_conns[agnt] = msg.getKey()
            evt = agent.MessageSendEvent(self, msg, agnt)
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

                del self.agnt_conns[source]

        elif isinstance(evt, PingTimeoutEvent):
            if self.agnt_conns.has_key(evt.getSource()):
                log.info("Connection %s disconnected without responding" 
                          % evt.getSource().getConfig().getName())
                del self.agnt_conns[evt.getSource()]

        if len(self.agnt_conns) == 0 and self.getAgent().isRunning():
            # All agents have responded, we can shutdown
            self.getAgent().setState(agent.STOPPING)

class AgentSet(XMLObject):
    def addAgent(self, agnt):
        self.addObject(agnt)
    def getAgents(self):
        return self.getObjects(agent.AgentConfig)

class DirectorStatusResponse(simple.StatusResponse):
    def setAgentSet(self, set):
        old_set = self.getAgentSet()
        if old_set is not None:
            self.removeObject(old_set)
        self.addObject(set)
    def getAgentSet(self):
        return utils.get_single(self.getObjects(AgentSet))

class Director(simple.SimpleAgent):
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
        set = AgentSet()
        for c in self.getConnections():
            config = c.getConfig()
            if config is not None:
                set.addAgent(config)
        resp.setAgentSet(set)
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
