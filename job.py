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

import logging
log = logging.getLogger("agent.job")

import event
class Job(event.EventListener):
    """Abstraction that represents something the agent is trying to do.
    A job will attempt to do some work. This may require sending a request
    and receiving an appropriate response"""
    def __init__(self, agent):
        event.EventListener.__init__(self)
        self.agent = agent
    def notify(self, evt):
        # The RunJobEvent is a built in special event. If we receive one of
        # these events and the events job is set to us, we know we are 
        # supposed to execute our run method.
        if isinstance(evt, RunJobEvent) and evt.getJob() == self:
            self.run()

    def run(self):
        """Method called when the job is started. Probably executed when we
        receive a RunJobEvent"""
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
