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

def escape(s, replace=string.replace):
    s = replace(s, "&", "&amp;")
    s = replace(s, "<", "&lt;")
    return replace(s, ">", "&gt;",)

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
        value = escape(value)
    
    # TODO: escape special characters
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

class ObjectHandler(handler.ContentHandler):
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
        if self.in_property:
            self.contents += ch

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
