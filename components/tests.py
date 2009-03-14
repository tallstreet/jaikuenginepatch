"""Loads tests from components

All tests.py files inside loaded components are imported and any classes 
derived from unittest.TestCase are then referenced from this file itself 
so that they appear at the top level of the tests "module" that Django will 
import.
"""
import os
import types
import unittest

from common import component

test_names = []

for name, loaded_component in component.loaded.iteritems():
  test_dir = os.path.dirname(loaded_component.__file__)
  for filename in os.listdir(test_dir):
    if filename != "tests.py":
      continue

    # Import the test file and find all TestClass clases inside it.
    test_module = __import__('components.%s.%s' % (name, filename[:-3]), 
                             {}, {},
                             filename[:-3])
    for name in dir(test_module):
      item = getattr(test_module, name)
      if not (isinstance(item, (type, types.ClassType)) and
              issubclass(item, unittest.TestCase)):
        continue
      # Found a test, bring into the module namespace.
      exec "%s = item" % name
      test_names.append(name)

# Hide everything other than the test cases from other modules.
__all__ = test_names
