#!/usr/bin/python

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
