import logging
log = logging.getLogger("agent.job")

import event
class Job(event.EventSource, event.EventListener):
    """Abstraction that represents something the agent is trying to do.
    A job will attempt to do some work. This may require sending a request
    and receiving an appropriate response"""
    def __init__(self, agent):
        self.agent = agent
        self.outgoing = {}
    def notify(self, evt):
        if isinstance(evt, RunJobEvent) and evt.getJob() == self:
            self.run()

    def run(self):
        raise Exception("Not Implemented")

    def getAgent(self):
        return self.agent


class RunJobEvent(event.Event):
    """Event which should run a given job"""
    def __init__(self, source, job):
        event.Event.__init__(self, source)
        self.job = job
    def getJob(self):
        return self.job
