# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import sys
import warnings

# hack for import funkiness together with flumotion.twisted.reflect.namedAny
from twisted.internet import reactor

from flumotion.common import registry, common
from flumotion.twisted import reflect

exitCode = 0

# count DeprecationWarning as an error
_old_showwarning = warnings.showwarning


def showwarning(message, category, filename, lineno, file=None, line=None):
    # python 2.4 does not have line as a kwarg
    _old_showwarning(message, category, filename, lineno, file)
    if category is not DeprecationWarning:
        return
    # uncomment to see better where the problem comes from when it claims
    # to be in ihooks.py
    # import traceback; traceback.print_stack()

    # if it's not in our code, it's not our fault
    if filename.startswith('/usr/lib'):
        return

    # count the deprecation as a fatal error
    global exitCode
    exitCode += 1

warnings.showwarning = showwarning

from flumotion.common import setup
setup.setup()
setup.setupPackagePath()

registry = registry.getRegistry()

basket = registry.makeBundlerBasket()

bundlerNames = basket.getBundlerNames()

for name in bundlerNames:
    # skip locale bundles, they're autogenerated and I'm too lazy to figure out
    # why validating the registry in the template module expects locale
    # bundles of core to be in the template's build dir
    if name.find('-locale-') > -1:
        continue
    try:
        basket.getBundlerByName(name).bundle()
    except OSError, e:
        sys.stderr.write("Bundle %s references missing file %s\n" % (
            name, e.filename))
        exitCode += 1

# verify all components


def componentError(c, msg):
    global exitCode
    sys.stderr.write("Component %s from %s %s.\n" %(
            c.type, c.filename, msg))
    exitCode += 1

for c in registry.getComponents():
    if c.type != c.type.lower():
        componentError(c, 'contains capitals')
    if c.type.find('_') > -1:
        componentError(c, 'contains underscores')
    if not c.description:
        componentError(c, 'is missing a description')

    for s in c.sockets:
        try:
            function = reflect.namedAny(s)
        except AttributeError:
            componentError(c, 'could not import socket %s' % s)

    def propertyError(c, p, msg):
        global exitCode
        sys.stderr.write("Property %s on component %s from %s %s.\n" %(
                p.name, c.type, c.filename, msg))
        exitCode += 1

    for p in c.getProperties():
        if p.name != p.name.lower():
            propertyError(c, p, "contains capitals")
        if p.name.find('_') > -1:
            propertyError(c, p, "contains underscores")
        if not p.description:
            propertyError(c, p, "is missing a description")

    #import code; code.interact(local=locals())

# verify all plugs


def plugError(p, msg):
    global exitCode
    sys.stderr.write("Plug %s from %s %s.\n" % (
            p.type, p.filename, msg))
    exitCode += 1

for plug in registry.getPlugs():
    if plug.type != plug.type.lower():
        plugError(plug, 'contains capitals')
    if plug.type.find('_') > -1:
        plugError(plug, 'contains underscores')
    if not plug.description:
        plugError(plug, 'is missing a description')

    # a plug type and its class name should match too
    normalizedType = ''.join(plug.type.split('-')) + 'plug'
    function = plug.entries['default'].function
    normalizedClass = function.lower()
    if normalizedType != normalizedClass:
        plugError(plug, 'type %s does not match class %s' % (
            plug.type, function))

    # a plug's socket should be creatable
    try:
        function = reflect.namedAny(plug.socket)
    except AttributeError:
        plugError(plug, 'could not import socket %s' % plug.socket)


    # a plug should be creatable
    for name, entry in plug.entries.items():
        moduleName = common.pathToModuleName(entry.location)
        entryPoint = "%s.%s" % (moduleName, entry.function)
        try:
            function = reflect.namedAny(entryPoint)
        except AttributeError:
            plugError(plug, 'could not import plug %s' % entryPoint)

    def propertyError(plug, p, msg):
        global exitCode
        sys.stderr.write("Property %s on plug %s from %s %s.\n" %(
                p.name, plug.type, plug.filename, msg))
        exitCode += 1

    for p in plug.getProperties():
        if p.name != p.name.lower():
            propertyError(plug, p, "contains capitals")
        if p.name.find('_') > -1:
            propertyError(plug, p, "contains underscores")
        if not p.description:
            propertyError(plug, p, "is missing a description")

    #import code; code.interact(local=locals())


sys.exit(exitCode)
