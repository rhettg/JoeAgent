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
from xobject import *
import StringIO

class XMLObjectTestClass(XMLObject):
    def __init__(self):
        XMLObject.__init__(self)
        self.id = 12345
        self.name = "Rhett<da man>"
        self.da_map = {'key1': 1.2345,
                       'key2': 12345}
        self.da_list = []
        self.none_list = [None]
        self.none_value = None

    def addToList(self, value):
        self.da_list.append(value)

    def __eq__(self, obj):
        if not isinstance(obj, self.__class__):
            return False
        if not self.__dict__ == obj.__dict__:
            return False

        return True


class ConvertValuesTestCase(unittest.TestCase):
    # Only use setUp() and tearDown() if necessary

    def shortDescription(self):
        return "Test the convert to XML code"

    def setUp(self):
        self.parser = make_parser()
        self.parser.setFeature(feature_namespaces, 0)

        self.obj_hndler = XMLObjectHandler()
        self.parser.setContentHandler(self.obj_hndler)

        self.basic_values = [123,
                        '123',
                        'My Name Is',
                        1.2345,
                        1.23e10,
                        True,
                        False,
                        None,
                        [1,2,3],
                        ['1', 2, True],
                        {'key1': 'value1',
                         'key2': 'value2<with a tag/>'},
                        (1, 2, 3),
                        ('1', 2, {'blah': None})
                       ]

    def tearDown(self):
        pass

    def test_feature_one(self):
        # Test feature one.
        for val in self.basic_values:
            txt = convert_value(val)
            io = StringIO.StringIO(txt)
            self.parser.parse(io)
            instances = self.obj_hndler.getInstances()
            assert len(instances) == 1, "No output?: %s   %s" % (`val`, txt)
            inst = instances[0]
            assert inst == val, \
                   "In: %s (%s)   Out: %s (%s)" \
                   % (str(val), `val`, str(inst), `inst`)
            self.obj_hndler.reset()
            self.parser.reset()

class ConvertObjectTestCase(unittest.TestCase):
    # Only use setUp() and tearDown() if necessary

    def shortDescription(self):
        return "Test the convert Objects to XML code"

    def setUp(self):
        self.parser = make_parser()
        self.parser.setFeature(feature_namespaces, 0)

        self.obj_hndler = SingleXMLObjectHandler()
        self.parser.setContentHandler(self.obj_hndler)

    def tearDown(self):
        pass

    def test_feature_one(self):
        obj = XMLObjectTestClass()
        obj.name = "New Rhett <with tag>/"
        obj.id = 1234
        obj.da_map = {'who': 'do not know   ',
                      'what': '<no>',
                      1234: 63}

        for ndx in range(0, 5):
            obj.addToList(XMLObjectTestClass())

        #print "Here is the value:"
        #print str(obj)

        txt = convert_value(obj)
        io = StringIO.StringIO(txt)

        try:
            self.parser.parse(io)
        except EndOfObjectException, e:
            new_obj = e.getObject()

        assert new_obj.name == obj.name
        assert new_obj.id == obj.id

        # Verify correct class
        assert new_obj.__class__ == obj.__class__

        # Verify correct map
        assert new_obj.da_map == obj.da_map

        # Verify list elements
        assert len(new_obj.da_list) == len(obj.da_list)
        for ndx in range(0, len(new_obj.da_list)):
            assert new_obj.da_list[ndx] == obj.da_list[ndx], "Element does not match: '%s' vs. '%s'" % (str(new_obj.da_list[ndx]), str(obj.da_list[ndx]))
        
        #print "Old: %s" % str(obj)
        #print "\nNew: %s" % str(new_obj)

def test_main():
    test_support.run_unittest(ConvertValuesTestCase,
                              ConvertObjectTestCase)

if __name__ == '__main__':
    test_main()

