"""
This module should provide everything that is needed to include a HTTP server
within an agent.

The agent should add a HTTPServerConnection which will listen on the specified
port for incoming HTTP clients.

When a client connects, a HTTPConnection is created just as a normal agent
connection to us would generate a Connection.

Incoming traffic to that HTTPConnection will result in the creation of a 
HTTPRequestEvent or a HTTPRequestErrorEvent.

These events will pass back into the agent event queue and can be handled by
an HTTPJob.

It is expected that any agent using HTTPConnection will provide a handler for:
    HTTPRequestEvent
        Handle request and create an HTTPResponseEvent with request.source
        as the target
    HTTPRequestErrorEvent
        Handle error by creating a appropriate error response
    HTTPResponseEvent
        Handle response by writing response to the target connection.
"""

import re, string, socket
import simple, event, message, agent

import logging
log = logging.getLogger("http")

class ParseException(Exception): pass

class Header:
    REG = re.compile("^([\S]+)\:[\s]+(.*)\r$")
    def __init__(self, name = "", value = ""):
        self.name = name
        self.value = value
    def getName(self):
        return self.name
    def getValue(self):
        return self.value
    def parse(self, header_line):
        mtch = self.REG.search(header_line)
        if mtch is None:
            raise ParseException("Does not match header format: '%s'" 
                                 % header_line)
        else:
            self.name = mtch.group(1).strip()
            self.value = mtch.group(2).strip()
        
    def __repr__(self):
        return "%s: %s" % (self.getName(), self.getValue())
    def __str__(self):
        return "%s\r\n" % (`self`)

class HTTPRequest:
    """Represents a request from an HTTP client. Notice that it is not related
    to our own XMLObject based requests"""
    REQ_REG = re.compile("([\S]+) ([\S]+)[\s]?([\S]+)?\r")
    def __init__(self, command = "", path = "", version = "", headers = []):
        self.command = command
        self.path = path
        self.version = version
        self.headers = headers
        return

    def getCommand(self):
        return self.command
    def getPath(self):
        return self.path
    def getVersion(self):
        return self.version

    def addHeader(self, header):
        self.headers.append(header)
    def getHeaders(self):
        return self.headers
    def getHeaderValue(self, name):
        for h in self.headers:
            if h.getName() == name:
                return h
        return None

    def parse(self, request_content):
        lines = string.split(request_content, '\n')

        # Go line by line until we find a  valid request line
        ndx = 0
        mtch = None
        while mtch is None and ndx < len(lines):
            mtch = self.REQ_REG.search(lines[ndx])
            ndx += 1
        if mtch is None:
            raise ParseException("Failed to find a request line: '%s'" 
                                 % request_content)

        self.command, self.path, self.version = mtch.groups("")

        # Now parse the rest of the lines as headers
        for l in lines[ndx:]:
            try:
                hdr = Header()
                hdr.parse(l)
                self.addHeader(hdr)
            except ParseException, e:
                log.debug("Failed parsing header: '%s'" % str(l))

    def __repr__(self):
        return "%s %s %s" % (self.getCommand(), self.getPath(), 
                             self.getVersion())

class HTTPResponse:
    VERSION = "HTTP/0.9"
    MESSAGES = {
        100: 'Continue',
        101: 'Switching Protocols',
        200: 'OK',
        201: 'Created',
        202: 'Accepted',
        203: 'Non-Authoritative Information',
        204: 'No response',
        205: 'Reset Content',
        206: 'Partial Content',
        300: 'Multiple Choices',
        301: 'Moved Permanently',
        302: 'Found',
        303: 'See Other',
        304: 'Not modified',
        305: 'Use Proxy',
        307: 'Temporary Redirect',
        400: 'Bad request',
        401: 'Unauthorized',
        402: 'Payment required',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        406: 'Not Acceptable',
        407: 'Proxy Authentication Required',
        408: 'Request Time-out',
        409: 'Conflict',
        410: 'Gone',
        411: 'Length Required',
        412: 'Precondition Failed',
        413: 'Request Entity Too Large',
        414: 'Request-URI Too Long',
        415: 'Unsupported Media Type',
        416: 'Requested Range Not Satisfiable',
        417: 'Expectation Failed',
        500: 'Internal error',
        501: 'Not Implemented',
        502: 'Bad Gateway',
        503: 'Service temporarily overloaded',
        504: 'Gateway timeout',
        505: 'HTTP Version not supported'
    }

    def __init__(self, code, headers, content = ""):
        self.code = code
        self.headers = headers
        self.content = content
    def getCode(self):
        return self.code
    def getHeaders(self):
        return self.headers
    def getContent(self):
        return self.content
    def getMessage(self):
        return self.MESSAGES[self.getCode()]
    def __str__(self):
        response = "%s %d %s\r\n" % (self.VERSION, self.getCode(), 
                                     self.getMessage())
        hdrs = []
        for h in self.getHeaders():
            hdrs.append(str(h))
        return response + string.join(hdrs, '') + "\r\n" + self.getContent()

    def __repr__(self):
        return "Response: %s" % (str(self.code))

class HTTPRequestEvent(event.Event):
    def __init__(self, source, request):
        event.Event.__init__(self, source)
        self.request = request
        return
    def getRequest(self):
        return self.request

class HTTPResponseEvent(agent.MessageSendEvent): pass

class HTTPRequestErrorEvent(event.Event):
    def __init__(self, source, code, request_line):
        event.Event.__init__(self, source)
        self.code = code
        self.request_line = request_line
        return
    def getCode(self):
        return self.code
    def getRequestLine(self):
        return self.request

class HTTPConnection(agent.Connection):
    """This connection provides facilities for connecting to a HTTP client.
    This is based on BaseHTTPRequestHandler class of the python standard
    library. It was not possible to use that library directly because it 
    blocks.  """
    def __init__(self, config = None, sock = None):
        agent.Connection.__init__(self, config, sock)
        self.raw_request = ""

    def read(self):
        log.debug("Connection read")
        try:
            self.in_buffer = self.sock.recv(agent.BUFF_SIZE)
            if self.in_buffer == "":
                log.debug("Read 0, disconnect")
                self.disconnect()
                return None
            self.raw_request += self.in_buffer
        except socket.error, e:
            log.exception("Exception from socket")
            self.disconnect()
            return

        end_of_request = self.raw_request[-3:]
        if end_of_request.find("\n\n") or \
           end_of_request.find("\n\r\n"):
            # end of line, we have a complete requestline
            request = HTTPRequest()
            request.parse(self.raw_request)
            evt = HTTPRequestEvent(self, request)
            return evt

    def write(self, buffer = ""):
        if not self.isConnected():
            log.error("Connection was dropped")
            return

        agent.Connection.write(self, buffer)
        if not self.isWritePending():
            self.disconnect()

class HTTPConnectEvent(agent.ConnectEvent): pass

class HTTPServerConnection(agent.ServerConnection):
    def read(self):
        log.debug("Accepting a new HTTP connection")
        new_sock, new_addr = self.sock.accept()
        log.debug("%s connected" % str(new_addr))
        return HTTPConnectEvent(self, HTTPConnection(None, new_sock))

if __name__ == "__main__":
    sample_headers = ["Connection: keep-alive\r\n",
                      "Connection:  \tkeep-alive\t\r\r\n"]

    sample_request = """
\n\r\n
GET /index.html HTTP/1.0\r
Connection: keep-alive\r
Content-type: text\html\r
\r\n
"""

    print "Testing HTTP header parsing"
    for h in sample_headers:
        hdr = Header()
        hdr.parse(h)
        print "Header (%s)" % str(hdr)
    print "Done"

    print "Testing HTTP Request parsing"
    request = HTTPRequest()
    request.parse(sample_request)
    print "Parsed Request:"
    print "\tCommand: %s" % request.getCommand()
    print "\tPath: %s" % request.getPath()
    print "\tVersion: %s" % request.getVersion()
    for h in request.getHeaders():
        print "\t\tHeader (%s)" % `h`
    print "Done"

    print "Generate Response"
    hdrs = [Header('Connection', 'Keep-alive'),
            Header('Content-type', 'text\html'),
            Header('Hoopla', 'true')
           ]
    response = HTTPResponse(100, hdrs, "This is content")
    print `response`
    print
    print str(response)
