import logging
log = logging.getLogger("agent.simple")

import agent, job, utils, event, message, timer

CONNECT_RETRY = 3.0

class ConnectRequest(agent.Request): 
    def __init__(self, config = None):
        agent.Request.__init__(self)
        if config != None:
            self.addObject(config)
    def getConfig(self):
        return utils.get_single(self.getObjects(agent.AgentConfig))

class HandleConnectJob(job.Job):
    """When an agent connects to us, it will request connect and provide us
    with its config object. This allows us to know what kind of agent it is
    and connect to its server port if it has one"""
    def notify(self, evt):
        job.Job.notify(self, evt)
        if isinstance(evt, agent.MessageReceivedEvent) and \
           isinstance(evt.getMessage(), ConnectRequest):
               evt.getSource().setConfig(evt.getMessage().getConfig())
               
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
            self.getAgent().addEvent(agent.MessageSendEvent(self, resp, conn))

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

class ConnectRetryEvent(event.Event): pass

class ConnectRetryTimer(timer.Timer):
    def __init__(self, source = None):
        evt = ConnectRetryEvent(source)
        timer.Timer.__init__(self, CONNECT_RETRY, evt)

class ConnectJob(job.Job):
    def __init__(self, agent_obj, agent_config, max_retries = 0):
        job.Job.__init__(self, agent_obj)
        self.key = None
        self._max_retries = max_retries
        self._retries = 0
        self._connection = None

        # The agent we are going to connect to
        self.config = agent_config

    def run(self):
        log.debug("Running ConnectJob") 
        self._connect()

    def notify(self, evt):
        log.debug("Connect Job Notified") 
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
                self.getAgent().shutdown()

        elif isinstance(evt, ConnectRetryEvent) and evt.getSource() == self:
            log.info("Attempting to connect to director")
            self._retries += 1
            self._connect()

        elif isinstance(evt, ConnectCompleteEvent) and evt.getSource() == self:
            # This job is complete
            self.getAgent().dropListener(self)

    def getConnection(self):
        return self._connection
    
    def _set_retry_timer(self):
        self._timer = ConnectRetryTimer(self)
        self.getAgent().addTimer(self._timer)

    def _connect(self):
        # Create connection to remote agent
        if self._max_retries == -1 or self._max_retries >= self._retries:
            connection = agent.Connection(self.config)
            connection.connect()

            self.getAgent().addConnection(connection)
            self._connection = connection

            # Send Connect Request
            msg = ConnectRequest(self.getAgent().getConfig())
            self.key = msg.getKey()
            evt = agent.MessageSendEvent(self, msg, connection)
            self.getAgent().addEvent(evt)
            self._set_retry_timer()
        else:
            # This job is complete
            self.getAgent().dropListener(self)

            
class StatusRequest(message.Request): pass

class StatusResponse(message.Response):
    def __init__(self, key = None):
        message.Response.__init__(self, key)
        self.status_details = ""

    def getStatusDetails(self):
        return self.status_details
    def setStatusDetails(self, details):
        self.status_details = details

    def getState(self):
        return utils.get_single(self.getObjects(agent.AgentState))
    def setState(self, new_state):
        cur_state = self.getState()
        if cur_state is not None:
            self.removeObject(cur_state)
        self.addObject(new_state)
    
    def getConfig(self):
        return utils.get_single(self.getObjects(agent.AgentConfig))
    def setConfig(self, new_config):
        cur_config = self.getConfig()
        if cur_config is not None:
            self.removeObject(cur_config)
        self.addObject(new_config)


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
        resp.setConfig(self.getConfig())
        return resp

class SubAgentConfig(agent.AgentConfig):
    """SubAgents have the special need of connecting to a director agent.
       The subagent will need the configuration information for the 
       director so that it may connect to it."""
    def getDirectorConfig(self):
        return utils.get_single(self.getObjects(agent.AgentConfig))
    def setDirectorConfig(self, new_config):
        cur_config = self.getDirectorConfig()
        if cur_config is not None:
            self.removeObject(cur_config)
        self.addObject(new_config)

class SubAgent(SimpleAgent):
    def __init__(self, config):
        self._dir_connect_job = None
        SimpleAgent.__init__(self, config)

    def getInitJobs(self):
        # We need a job to connect to our director agent.
        self._dir_connect_job = ConnectJob(self, 
                                  self.getConfig().getDirectorConfig(), -1)
        return SimpleAgent.getInitJobs(self) + [self._dir_connect_job]

    def getInitEvents(self):
        # We want to connect to our director agent as soon as this agent starts
        # up so we add a RunJobEvent so that it will run the ConnectJob as
        # soon as it gets processed
        assert self._dir_connect_job is not None, "Connect job not yet defined"
        return SimpleAgent.getInitEvents(self) + \
               [job.RunJobEvent(self, self._dir_connect_job)]
