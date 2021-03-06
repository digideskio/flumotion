# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import string

from twisted.internet import defer

from flumotion.common import gstreamer, messages
from flumotion.common.i18n import N_, gettexter

__version__ = "$Rev$"
T_ = gettexter()


def checkOgg():
    """
    Check for a recent enough Ogg muxer.
    """
    result = messages.Result()
    version = gstreamer.get_plugin_version('ogg')
    if version >= (0, 10, 3, 0) and version < (0, 10, 4, 0):
        m = messages.Warning(T_(
            N_("Version %s of the '%s' GStreamer plug-in contains a bug.\n"),
               string.join([str(x) for x in version], '.'), 'ogg'),
            mid='ogg-check')
        m.add(T_(N_("The generated Ogg stream will not be fully compliant, "
            "and might not even play correctly.\n")))
        m.add(T_(N_("Please upgrade '%s' to version %s."), 'gst-plugins-base',
            '0.10.4'))
        result.add(m)

    result.succeed(None)
    return defer.succeed(result)


def checkTicket1344():
    """
    Check if the version of oggmux is the one that can create borked ogg files.

    Note: this also checks for a problem with gdppay reported in #1341.
    """
    result = messages.Result()
    if gstreamer.get_plugin_version('ogg') == (0, 10, 24, 0):
        m = messages.Warning(T_(
                N_("Version %s of the '%s' GStreamer plug-ins set "
                   "contains various bugs.\n"), '0.10.24', 'gst-plugins-base'),
                             mid='oggmux-check')
        m.add(T_(N_("They are regressions introduced in %s and will be "
                    "fixed in %s.\n"), '0.10.24', '0.10.25'))
        m.add(T_(N_("The component will probably never go to happy.\n")))
        m.add(T_(N_("Please use a different version of %s instead."),
                 'gst-plugins-base'))
        result.add(m)

    result.succeed(None)
    return defer.succeed(result)
