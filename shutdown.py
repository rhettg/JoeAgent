#!/usr/bin/python
import socket, sys, logging
import simple, agent
from event import Event
from job import Job, RunJobEvent

log = logging.getLogger("agent.shutdown")

class ShutdownJob(Job):
    def __init__(self, agent_obj):
        Job.__init__(self, agent_obj)
        self.conn = None
        self.key = None

    def run(self):
        log.debug("Running Shutdown job") 
        # Send Shutdown Request
        msg = agent.ShutdownRequest()
        self.key = msg.getKey()
        assert self.conn != None, "Connection should not be None"
        evt = agent.MessageSendEvent(self, msg, self.conn)
        self.getAgent().addEvent(evt)

    def notify(self, evt):
        Job.notify(self, evt)
        log.debug("Notified of event: %s" % str(evt.__class__))
        if isinstance(evt, simple.ConnectCompleteEvent):
            self.conn = evt.getConnection()
            self.run()
        elif isinstance(evt, agent.MessageReceivedEvent):
            log.debug("Its a message recevied: %s vs. %s" % (self.key, evt.getMessage().getRequestKey()))
            if isinstance(evt.getMessage(), agent.OkResponse) and \
               self.key == evt.getMessage().getRequestKey():
                print "Shutdown Acknowledged"
                self.getAgent().setState(agent.STOPPING)
            if isinstance(evt.getMessage(), agent.DeniedResponse) and \
               self.key == evt.getMessage().getRequestKey():
                print "Shutdown Denied"
                self.getAgent().setState(agent.STOPPING)
        

def setup_logger(logname, filename):
    if logname != "":
        log = logging.getLogger(logname)
    else:
        log = logging.getLogger()
    hdler = logging.FileHandler(filename)
    fmt = logging.Formatter(logging.BASIC_FORMAT)
    hdler.setFormatter(fmt)
    log.addHandler(hdler)
    log.setLevel(logging.DEBUG)
    return log

if __name__ == "__main__":
    log = setup_logger("", "log/shutdown.log")
    if len(sys.argv) < 3:
        print "Usage: %s <addr> <port>" % (sys.argv[0])
        sys.exit(1)
    bind_addr = sys.argv[1]
    port = sys.argv[2]

    # Our simple configuration.
    # Note we are not setting address or port because we do not want to be a
    # server.
    config = agent.AgentConfig()
    config.setName("Shutdown Command")

    # Configuration for the remote agent
    remote_info = agent.AgentInfo()
    remote_info.setHost(bind_addr)
    remote_info.setPort(int(port))
    remote_info.setName("Remote Agent")

    # Create the agent
    command_agent = agent.Agent(config)

    # Create the jobs
    shutdown_job = ShutdownJob(command_agent)
    connect_job = simple.ConnectJob(command_agent, remote_info)

    # Create an event that will start the job we want at run-time
    run_evt = RunJobEvent(command_agent, connect_job)
    command_agent.addEvent(run_evt)

    # Don't forget to add the jobs as listeners
    command_agent.addListener(shutdown_job)
    command_agent.addListener(connect_job)
    command_agent.addListener(simple.HandlePingJob(command_agent))

    print "Running shutdown"
    command_agent.run()

