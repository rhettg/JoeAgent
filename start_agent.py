#!/usr/bin/python
import logging
import agent, xobject
import sys, os
from utils import load_class
log = None

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

log = setup_logger("start_agent", "log/start_agent.log")

if len(sys.argv) < 4:
    print "Usage: start_agent.py <agent_name> <fac_server> <fac_port>"
    sys.exit(1)

agent_name = sys.argv[1]
server = sys.argv[2]
port = int(sys.argv[3])

config = agent.AgentConfig()
config.setName(agent_name)
config.setPort(port)
config.setBindAddress(server)

dir_config = None
if len(sys.argv) > 4:
    dir_config = agent.AgentConfig()
    dir_config.setName("Director")
    dir_config.setBindAddress(sys.argv[4])
    dir_config.setPort(int(sys.argv[5]))

pid = os.fork()
if pid == 0:
    try:
        os.close(1)
        os.close(2)
        os.close(3)

        log = setup_logger("", "log/%s.log" % config.name)

        log.debug("Instantiating agent")
        if dir_config is None:
            my_agent = load_class(agent_name)(config)
        else:
            my_agent = load_class(agent_name)(config, dir_config)

        log.debug("Starting Agent")
        my_agent.run()
    except Exception, e:
        log.exception("Exception thrown, caught in start_agent")
    log.debug("Agent exiting")
    sys._exit(0)
else:
    log.debug("Agent Daemon %s started. PID: %d" % (agent_name, pid))
    print "Done (%d)" % (pid)
    sys.exit(0)
