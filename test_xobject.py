#!/usr/bin/python

import unittest
from test import test_support
from xobject import *


class XMLObjectTestClass(XMLObject):
    def __init__(self):
        XMLObject.__init__(self)
        self.id = 12345
        self.name = "Rhett"
        self.da_map = {'key1': 1.2345,
                       'key2': 12345}
        self.da_list = []
        self.none_list = [None]
        self.none_value = None

    def addToList(self, value):
        self.da_list.append(value)

class ConvertValuesTestCase(unittest.TestCase):
    # Only use setUp() and tearDown() if necessary

    def shortDescription(self):
        return "Test the convert to XML code"

    def setUp(self):
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
            print convert_value(val)
        return True

    def test_feature_two(self):
        obj = XMLObjectTestClass()
        for ndx in range(0, 5):
            obj.addToList(XMLObjectTestClass())
        print "Here is the value:"
        print str(obj)

def test_main():
    test_support.run_unittest(ConvertValuesTestCase)

if __name__ == '__main__':
    test_main()

