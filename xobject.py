from xml.sax import saxutils, handler, make_parser, xmlreader
from xml.sax.handler import feature_namespaces
from xml.sax.expatreader import ExpatParser
from utils import get_class
import string, types

class EndOfObjectException(Exception):
    """Exception used for interrupting a parser when a single XMLObject 
    has been successfully parsed. This exception will contain the object
    that was parsed off the line. This is especially useful for reading
    off of a socket which is not expected to close."""
    
    def __init__(self, object):
        self.obj = object
        Exception.__init__(self)

    def getObject(self):
        return self.obj

class SocketExpatParser(ExpatParser):
    """Special version of a parser which can be used with a socket"""
    def parse(self, source):
        from xml.sax.expatreader import ExpatLocator
        #self._source = source
        self.reset()
        self._cont_handler.setDocumentLocator(ExpatLocator(self))

        #self.prepareParser(source)
        buffer = source.recv(self._bufsize)
        while buffer != "":
            self.feed(buffer)
            buffer = source.recv(self._bufsize)
        self.close()

# We will need a mapping from python types to tags for generating XML.
# The convert_value function will look up the tag it is supposed to use
# by checking the type of the primitive python value.
TYPE_TAG_MAP = {
    types.StringType: 'str',
    types.NoneType: 'none',
    types.IntType: 'int',
    types.FloatType: 'float',
    types.BooleanType: 'boolean',
    types.ListType: 'list',
    types.DictType: 'dict',
    types.TupleType: 'tuple'
}


def create_xml_list(value):
    """Convert a list of python values into an xml representation
    of a list."""

    # Convert every element in the list (note this could be recursive)
    values = map(convert_value, value)
    # Join all the values together so each one takes a line
    return string.join(values, '\n')

def create_xml_dict(value):
    """Convert a dictionary to its xml representation return """
    values = []
    for k in value.keys():
        values.append("<pair><%s>%s</%s> <%s>%s</%s></pair>" % 
                          ("key", convert_value(k), "key",
                           "value", convert_value(value[k]), "value"))
    return string.join(values, '\n')

def convert_value(value):
    """Convert a primitive python value into its XML representaion"""

    # Most types are represented simply by a identifying tag and the value
    # converted to a string. Some are more complicated like lists and dicts
    # and are handled in another function.

    if isinstance(value, XMLObject):
        return str(value)

    tag = TYPE_TAG_MAP[type(value)]

    if type(value) == types.NoneType:
        return "<%s/>" % (tag)
    elif type(value) == types.ListType or \
         type(value) == types.TupleType:
        value = create_xml_list(value)
    elif type(value) == types.DictType:
        value = create_xml_dict(value)
    elif type(value) == types.StringType:
        value = saxutils.escape(value)
    
    return "<%s>%s</%s>" % (tag, str(value), tag)
    
class XMLObject:
    """Base class for all objects which require the ability to be represented
    as XML data. Any object which has this base class can be converted to a
    string (which will be XML) and be put back together again using a 
    XMLObjectHandler and Expat parser."""
    def __init__(self):
        pass

    def __str__(self):
        """Convert Object to XML"""
        output = ""
        for property in self.__dict__.keys():
            if property[0] != "_":
                output += "  <%s>%s</%s>\n" % (property, 
                                        convert_value(self.__dict__[property]), 
                                               property)

        output = "<XMLObject class=\"%s\">\n%s</XMLObject>\n" % \
                                              (str(self.__class__), output)
                                                               
        return output

def create_object(full_class_name = None):
    """Instantiate an object by just by a string representation of its class.
    The object must not have required arguments to the __init__ function.
    Makes use of the get_class function of the utils module.
    
    If full_class_name is not specified (None) then a base class XMLObject
    will be provided"""

    if full_class_name != None:
        class_obj = get_class(full_class_name)
        try:
            return class_obj()
        except TypeError, e:
            raise Exception("Failed to instantiate %s: %s" % (str(class_obj),
                                                              str(e)))
    else:
        return XMLObject()


# The following StackElement classes are used by the XMLObjectHandler.
# The handler is centered around an element stack, made up element objects
# which coorespond to XML elements currently being parsed. Since XML
# can have elements nested within elements, the stack is an ideal data
# structure. Each python type has a cooresponding StackElement class, and
# knows how to construct itself when getValue() is called.

class StackElement(object):
    TAG = 'NOT SPECIFIED'
    def __init__(self, attrs):
        self._attrs = attrs

    def getTag(cls):
        """Return the tag that this element is represented as. This
        method is both a object and class method, meaning it can be called with
        either StackElement.getTag() or elementInstance.getTag()"""
        return cls.TAG
    getTag = classmethod(getTag)

    def addElement(self, elem):
        """Add a element to this parent element"""
        assert isinstance(elem, StackElement)
        pass
    def getValue(self):
        """Return the python object representation"""
        return None

class TypedElement(StackElement):
    """Typed Elements are the simple python types such as Integer and String.
    They consist only the text (or attrs) between the tags, there are no
    sub-elements"""
    ELEMENT_TYPE = None
    def __init__(self, attrs):
        StackElement.__init__(self, attrs)
        self.value = None
    def addElement(self, elem):
        raise 'TypedElements do not support sub elements'
    def addContent(self, content):
        self.value = content
    def getValue(self):
        return self.value

class StringElement(TypedElement):
    ELEMENT_TYPE = types.StringType
    TAG = TYPE_TAG_MAP[ELEMENT_TYPE]
    def getValue(self):
        return saxutils.unescape(str(self.value))

class IntegerElement(TypedElement):
    ELEMENT_TYPE = types.IntType
    TAG = TYPE_TAG_MAP[ELEMENT_TYPE]
    def getValue(self):
        return int(self.value)

class FloatElement(TypedElement):
    ELEMENT_TYPE = types.FloatType
    TAG = TYPE_TAG_MAP[ELEMENT_TYPE]
    def getValue(self):
        return float(self.value)

class BooleanElement(TypedElement):
    ELEMENT_TYPE = types.BooleanType
    TAG = TYPE_TAG_MAP[ELEMENT_TYPE]
    def getValue(self):
        self.value = string.strip(self.value)
        if self.value == "True":
            return True
        elif self.value == "False":
            return False
        else:
            assert 0, "Invalid for boolean: %s" % str(self.value)

class NoneElement(TypedElement):
    ELEMENT_TYPE = types.NoneType
    TAG = TYPE_TAG_MAP[ELEMENT_TYPE]
    def getValue(self):
        return None

class MemberElement(StackElement):
    """MemberElements coorespond to member variables of an XMLObject.
    They are special because the tag value indicates the name of the member,
    not the type of StackElement."""
    def __init__(self, attrs, name):
        StackElement.__init__(self, attrs)
        self.name = name
        self.value = None
    def addElement(self, elem):
        self.value = elem
    def getName(self):
        return self.name
    def getValue(self):
        return self.value.getValue()

class ObjectElement(StackElement):
    TAG = "XMLObject"
    def __init__(self, attrs):
        StackElement.__init__(self, attrs)
        self.dict = {}

    def addElement(self, elem):
        assert isinstance(elem, MemberElement)
        self.dict[elem.getName()] = elem.getValue()
    def getValue(self):
        obj = create_object(self._attrs['class'])
        obj.__dict__.update(self.dict)
        return obj

class ListElement(StackElement):
    TAG = "list"
    def __init__(self, attrs):
        StackElement.__init__(self, attrs)
        self.list = []
    def addElement(self, elem):
        self.list.append(elem)
    def getValue(self):
        val_list = []
        for elem in self.list:
            val_list.append(elem.getValue())
        return val_list

class TupleElement(ListElement):
    TAG = "tuple"
    def getValue(self):
        return tuple(ListElement.getValue(self))

class PairKeyElement(StackElement):
    TAG = "key"
    def __init__(self, attrs):
        StackElement.__init__(self, attrs)
        self.value = None
    def addElement(self, elem):
        self.value = elem.getValue()
    def getValue(self):
        return self.value

class PairValueElement(StackElement):
    TAG = "value"
    def __init__(self, attrs):
        StackElement.__init__(self, attrs)
        self.value = None
    def addElement(self, elem):
        self.value = elem.getValue()
    def getValue(self):
        return self.value

class PairElement(StackElement):
    TAG = "pair"
    def __init__(self, attrs):
        StackElement.__init__(self, attrs)
        self.key = None
        self.value = None
    def addElement(self, elem):
        if isinstance(elem, PairKeyElement):
            self.key = elem.getValue()
        elif isinstance(elem, PairValueElement):
            self.value = elem.getValue()
        else:
            assert 0, "Invalid type of element"
    def getKey(self):
        return self.key
    def getValue(self):
        return self.value

class DictionaryElement(StackElement):
    TAG = "dict"
    def __init__(self, attrs):
        StackElement.__init__(self, attrs)
        self.dict = {}
    def addElement(self, elem):
        assert isinstance(elem, PairElement)
        self.dict[elem.getKey()] = elem.getValue()
    def getValue(self):
        return self.dict

ELEMENT_LIST = {}
# We need a mapping from tags to StackElements for parsing
for elem in [StringElement, 
             NoneElement,
             IntegerElement,
             FloatElement,
             BooleanElement,
             ListElement,
             TupleElement,
             DictionaryElement,
             PairElement,
             PairValueElement,
             PairKeyElement,
             ObjectElement
            ]:
    ELEMENT_LIST[elem.getTag()] = elem

class XMLObjectHandler(handler.ContentHandler):
    """This is the expat handler for parsing XMLObject streams. When done
    parsing, the method getInstances() will return a list of objects found
    in the stream. This can also be used on streams that only contain 
    primitive python types (none-XMLObjects)"""
    def __init__(self):
        handler.ContentHandler.__init__(self)

        self.content = []

        # As we encounter elements, we will push them on the stack. As the
        # elements complete, we will pop them off and add them to the element
        # above them in the stack, or to the list of instances if they have
        # no parent
        self.stack = []
        self.instances = []

    def reset(self):
        """Reset the handler for use on another stream. Should be called if
        the parser is going to be reused."""
        self.content = []
        self.stack = []
        self.instances = []

    def getInstances(self):
        """Return a list of python values or XMLObjects found in the stream"""
        return self.instances
    def characters(self, ch):
        #print "adding content: '%s'" % ch
        self.content.append(ch)

    def startElement(self, name, attrs):
        #print "Starting %s" % name
        self.content = []
        parentElement = None
        if len(self.stack) > 0:
            parentElement = self.stack[-1]
        
        if isinstance(parentElement, ObjectElement):
            # This is a special case for when we are parsing objects.
            # The elements we encounter will be the names of our member
            # variables, not a tag we can match to determine the type.
            # Any element we encouter will be a MemberElement
            elem = MemberElement(attrs, name)
        else:
            # Any tag we encouter should match the tag specified in our 
            # element classes
            elem = ELEMENT_LIST[name](attrs)

        self.stack.append(elem)

    def endElement(self, name):
        #print "Ending %s" % name
        assert len(self.stack) > 0
        elem = self.stack.pop()
        assert isinstance(elem, StackElement), \
               "Not a StackElement?: %s : " % (`elem`)
        assert isinstance(elem, MemberElement) or elem.getTag() == name, \
               "Ending a %s instead of a %s" % (name, elem.getTag())


        if isinstance(elem, TypedElement):
            # If the element supports character data, lets put it in
            # and reset our character array
            elem.addContent(string.join(self.content, ''))

        # Our element (top of stack) is done processing.
        # We have two options, either we pass the element on up to its
        # parent element, or we add it to our own list of instances
        if len(self.stack) > 0:
            self.stack[-1].addElement(elem)
        else:
            self.instances.append(elem.getValue())

class SingleXMLObjectHandler(XMLObjectHandler):
    """Child class of XMLObjectHandler which will jump out when it finds
    a single XMLObject instance. Useful for reading objects out of a 
    socket stream which may not close when the object is complete."""
    def endElement(self, name):
        XMLObjectHandler.endElement(self, name)
        if len(self.getInstances()) == 1:
            raise EndOfObjectException(self.instances[0])


def print_instance(instance, indent = ""):
    print "%sInstance of: %s" % (indent, str(instance.__class__))
    for var in instance.__dict__.keys():
        if var != "_objects":
            print "%sProperty %s: %s" % (indent, var, 
                                                 instance.__dict__[var])
    
    for inst in instance.getObjects():
        print_instance(inst, "%s    " % indent)
        print

def load_object_from_socket(sock):
    """Load a single object from a socket"""
    parser = SocketExpatParser()
    # Tell the parser we are not interested in XML namespaces
    parser.setFeature(feature_namespaces, 0)

    # Create the handler
    obj_par = SingleXMLObjectHandler()

    # Tell the parser to use our handler
    parser.setContentHandler(obj_par)

    # Parse the input
    try:
        parser.parse(sock)
    except EndOfObjectException, e:
        return e.getObject()

    return None

def load_objects_from_file(file):
    """Load a list of objects from a file"""
    # Create a parser
    parser = make_parser()

    # Tell the parser we are not interested in XML namespaces
    parser.setFeature(feature_namespaces, 0)

    # Create the handler
    obj_par = XMLObjectHandler()

    # Tell the parser to use our handler
    parser.setContentHandler(obj_par)

    # Parse the input
    parser.parse(file)

    return obj_par.getInstances()

def load_object_from_file(file):
    """Load a single object from a file"""
    # Note: If there are more than one object in the file, it will try to 
    # parse the objects. The file must come to an end at some point, not
    # for use with just keeping an open stream like the from_socket sister
    # function.

    objs = load_objects_from_file(file)
    assert len(objs) == 1, "More than one object in file"
    return objs[0]
