#!/usr/bin/python
from xml.sax import saxutils, handler, make_parser, xmlreader
from xml.sax.handler import feature_namespaces
from xml.sax.expatreader import ExpatParser
from utils import get_class
import string, types

class EndOfObjectException(Exception):
    def __init__(self, object):
        self.obj = object
        Exception.__init__(self)

    def getObject(self):
        return self.obj

class SocketExpatParser(ExpatParser):
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

# We will need a mapping from python types to tags for generating XML
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
    """Convert a dictionary to its xml representation
    return """
    values = []
    for k in value.keys():
        values.append("<pair><%s>%s</%s> <%s>%s</%s></pair>" % 
                          ("key", convert_value(k), "key",
                           "value", convert_value(value[k]), "value"))
    return string.join(values, '\n')

def convert_value(value):

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
    if full_class_name != None:
        class_obj = get_class(full_class_name)
        try:
            return class_obj()
        except TypeError, e:
            raise Exception("Failed to instantiate %s: %s" % (str(class_obj),
                                                              str(e)))
    else:
        return XMLObject()


class StackElement(object):
    def __init__(self):
        pass
    def getTag(self):
        """Return the tag that this element is represented as"""
        raise 'Not Implemented'
    def addElement(self, elem):
        """Add a element to this parent element"""
        assert isinstance(elem, StackElement)
        pass
    def getValue(self):
        """Return the python object representation"""
        return None

class TypedElement(StackElement):
    ELEMENT_TYPE = None
    def __init__(self):
        StackElement.__init__(self)
        self.value = None
    def addElement(self, elem):
        raise 'TypedElements do not support sub elements'
    def addContent(self, content):
        self.value = content
    def getTag(self):
        return TYPE_TAG_MAP[self.__class__.ELEMENT_TYPE]
    def getValue(self):
        return self.value

class StringElement(TypedElement):
    ELEMENT_TYPE = types.StringType
    def getValue(self):
        return saxutils.unescape(str(self.value))

class IntegerElement(TypedElement):
    ELEMENT_TYPE = types.IntType
    def getValue(self):
        return int(self.value)

class FloatElement(TypedElement):
    ELEMENT_TYPE = types.FloatType
    def getValue(self):
        return float(self.value)

class BooleanElement(TypedElement):
    ELEMENT_TYPE = types.BooleanType
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
    def getValue(self):
        return None

class MemberElement(StackElement):
    def __init__(self, name):
        StackElement.__init__(self)
        self.name = name
        self.value = None
    def addElement(self, elem):
        self.value = elem
    def getName(self):
        return self.name
    def getValue(self):
        return self.value.getValue()

class ObjectElement(StackElement):
    def __init__(self, classObj):
        StackElement.__init__(self)
        self.classObj = classObj
        self.dict = {}

    def getTag(self):
        return "XMLObject"

    def addElement(self, elem):
        assert isinstance(elem, MemberElement)
        self.dict[elem.getName()] = elem.getValue()
    def getValue(self):
        obj = self.classObj()
        obj.__dict__.update(self.dict)
        return obj

class ListElement(StackElement):
    def __init__(self):
        StackElement.__init__(self)
        self.list = []
    def getTag(self):
        return 'list'
    def addElement(self, elem):
        self.list.append(elem)
    def getValue(self):
        val_list = []
        for elem in self.list:
            val_list.append(elem.getValue())
        return val_list

class TupleElement(ListElement):
    def getTag(self):
        return "tuple"
    def getValue(self):
        return tuple(ListElement.getValue(self))

class PairKeyElement(StackElement):
    def __init__(self):
        StackElement.__init__(self)
        self.value = None
    def getTag(self):
        return "key"
    def addElement(self, elem):
        self.value = elem.getValue()
    def getValue(self):
        return self.value

class PairValueElement(StackElement):
    def __init__(self):
        StackElement.__init__(self)
        self.value = None
    def getTag(self):
        return "value"
    def addElement(self, elem):
        self.value = elem.getValue()
    def getValue(self):
        return self.value

class PairElement(StackElement):
    def __init__(self):
        StackElement.__init__(self)
        self.key = None
        self.value = None
    def getTag(self):
        return "pair"
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
    def __init__(self):
        StackElement.__init__(self)
        self.dict = {}
    def getTag(self):
        return "dict"
    def addElement(self, elem):
        assert isinstance(elem, PairElement)
        self.dict[elem.getKey()] = elem.getValue()
    def getValue(self):
        return self.dict

# We need a mapping from tags to StackElements for parsing
ELEMENT_LIST = {
    'str': StringElement,
    'none': NoneElement,
    'int': IntegerElement,
    'float': FloatElement,
    'boolean': BooleanElement,
    'list': ListElement,
    'dict': DictionaryElement,
    'tuple': TupleElement,
    'pair': PairElement,
    'value': PairValueElement,
    'key': PairKeyElement
}

class ObjectHandler(handler.ContentHandler):
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
        self.content = []
        self.stack = []
        self.instances = []

    def getInstances(self):
        return self.instances
    def characters(self, ch):
        print "adding content: '%s'" % ch
        self.content.append(ch)

    def startElement(self, name, attrs):
        print "Starting %s" % name
        self.content = []
        parentElement = None
        if len(self.stack) > 0:
            parentElement = self.stack[-1]
        
        if isinstance(parentElement, ObjectElement):
            # This is a special case for when we are parsing objects.
            # The elements we encounter will be the names of our member
            # variables, not a tag we can match to determine the type.
            # Any element we encouter will be a MemberElement
            elem = MemberElement(name)
            self.stack.append(elem)
        else:
            # Any tag we encouter should match the tag specified in our 
            # element classes
            elem = ELEMENT_LIST[name]()
            self.stack.append(elem)

    def endElement(self, name):
        print "Ending %s" % name
        assert len(self.stack) > 0
        elem = self.stack.pop()
        assert isinstance(elem, StackElement), \
               "Not a StackElement?: %s : " % (`elem`)
        assert elem.getTag() == name


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

class OldObjectHandler(handler.ContentHandler):
    def __init__(self):
        handler.ContentHandler.__init__(self)

        self.property_name = ""

        self.in_property = 0
        self.in_object = 0
        self.contents = ""

        self.instances = []
        self.instance_index = None
               
    def popInstance(self):
        inst = self.currentInstance()
        self.instances.remove(inst)
        self.instance_index += -1
        return inst
    
    def currentInstance(self):
        return self.instances[self.instance_index]
    
    def pushInstance(self, instance):
        self.instances.append(instance)
        self.instance_index = len(self.instances) - 1

    def startElement(self, name, attrs):
        # If it's not a comic element, ignore it
        if name == 'XMLObject':
            self.in_object = 1
            class_name = attrs.get("class", "")
            self.pushInstance(create_object(class_name))
        elif self.in_object:
            self.in_property = 1
            self.property_name = name
        else:
            raise Exception("Error parsing '%s' tag" % name)

    def endElement(self, name):
        if name == 'XMLObject':
            closed_instance = self.popInstance()

            if len(self.instances) == 0:
                raise EndOfObjectException(closed_instance)
            else:
                (self.currentInstance()).addObject(closed_instance)

        elif self.in_property and name == self.property_name:
            setattr(self.currentInstance(), name, self.contents)
            self.contents = ""
            self.in_property = 0
        else:
            raise Exception("Error token :%s" % (name))

    def characters(self, ch):
        assert len(self.stack) > 0
        self.stack[-1].addContent(ch)

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
    parser = SocketExpatParser()
    # Tell the parser we are not interested in XML namespaces
    parser.setFeature(feature_namespaces, 0)

    # Create the handler
    obj_par = ObjectHandler()

    # Tell the parser to use our handler
    parser.setContentHandler(obj_par)

    # Parse the input
    try:
        parser.parse(sock)
    except EndOfObjectException, e:
        pass

    return obj_par.final_instance

def load_object_from_file(file):
    # Create a parser
    parser = make_parser()


    # Tell the parser we are not interested in XML namespaces
    parser.setFeature(feature_namespaces, 0)

    # Create the handler
    obj_par = ObjectHandler()

    # Tell the parser to use our handler
    parser.setContentHandler(obj_par)

    # Parse the input
    try:
        parser.parse(file)
    except EndOfObjectException, e:
        pass

    return obj_par.final_instance
