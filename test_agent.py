#!/usr/bin/python

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

import unittest
from test import test_support
from agent import *
import StringIO

class InstantiateTestCase(unittest.TestCase):
    # Only use setUp() and tearDown() if necessary

    def shortDescription(self):
        return "Just instanstiate and call simple methods to ensure sanity"

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_feature_one(self):
        obj = AgentInfo()
        obj.getHost()
        obj.getPort()
        obj.getName()

        obj = AgentConfig()
        obj.getBindAddress()
        obj.getPort()
        obj.getName()

        obj = ShutdownRequest()
        obj = PingRequest()
        obj = OkResponse()
        obj = DeniedResponse()
        obj = PingResponse()

        obj = ConnectEvent(self, None)
        obj = MessageEvent(self, None)
        obj = MessageReceivedEvent(self, None)
        obj = MessageSendEvent(self, None, None)

        obj = StateChangeEvent(self, RUNNING, STOPPED)
        assert obj.getOldState() == RUNNING
        assert obj.getNewState() == STOPPED

        obj = Connection()
        obj = AgentConnection()
        obj = ServerConnection()
        obj = Agent(AgentConfig())

def test_main():
    test_support.run_unittest(InstantiateTestCase)

if __name__ == '__main__':
    test_main()
