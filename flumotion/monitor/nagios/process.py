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


import os

from flumotion.common import format as formatting
from flumotion.monitor.nagios import util

__version__ = "$Rev: 6687 $"

# ad-hoc library


class ProcessFactory:
    """
    I create a Process instance or subclass.
    """

    def process(self, pid):
        """
        @rtype: L{Process} instance
        """
        # this is a factory function, so suppress inconsistent return value
        # warnings
        __pychecker__ = '--no-returnvalues'
        handle = open('/proc/%d/stat' % pid)
        line = handle.read()
        fields = line.split(' ')
        cmd = fields[1][1:-1] # strip off parentheses
        if cmd == 'flumotion-job':
            return JobProcess(pid)
        elif cmd.startswith('flumotion-worke'):
            return WorkerProcess(pid)
        elif cmd.startswith('flumotion-manag'):
            return ManagerProcess(pid)
        else:
            return Process(pid)


class Process:
    """
    I hold information about a process with a given pid based on information in
    /proc/(pid)/stat.  See man proc for more info.

    @ivar  pid:     the PID of the process
    @type  pid:     int
    @ivar  cmdline: the command line arguments for this process
    @type  cmdline: list of str
    @ivar  vsize:   virtual memory size in bytes
    @type  vsize:   int
    @ivar  rss:     number of pages in real memory, minus 3.
    @type  rss:     int
    """

    def __init__(self, pid):
        handle = open('/proc/%d/stat' % pid)
        line = handle.read()

        # see man proc
        fields = line.split(' ')
        assert pid == int(fields[0])
        self.pid = pid
        self.cmd = fields[1][1:-1] # strip off parentheses
        self.ppid = int(fields[3])
        self.vsize = int(fields[22])
        self.rss = int(fields[23])

        handle = open('/proc/%d/cmdline' % pid)
        line = handle.read()
        bits = line.split('\0')
        self.cmdline = bits

    def __repr__(self):
        return '<process %d: %s>' % (self.pid, self.cmd)


class JobProcess(Process):

    def __init__(self, pid):
        Process.__init__(self, pid)

        self.component = None

        if self.cmdline[2].startswith('/'):
            self.component = self.cmdline[2]

    def __repr__(self):
        return '<flumotion-job %d: %s>' % (self.pid, self.component)


class WorkerProcess(Process):

    def __init__(self, pid):
        Process.__init__(self, pid)

        self.service = None

        # FIXME: this assumes the worker being started with a given order of
        # arguments, the way the service scripts do; e.g.
        # /usr/bin/python /usr/bin/flumotion-worker -D
        # --daemonize-to /var/cache/flumotion
        # --service-name default /etc/flumotion/workers/default.xml
        if self.cmdline[5].startswith('--service-name'):
            self.service = self.cmdline[6]

    def __repr__(self):
        return '<flumotion-worker %d: %s>' % (self.pid, self.service)


class ManagerProcess(Process):

    def __init__(self, pid):
        Process.__init__(self, pid)

        self.service = None

        # FIXME: this assumes the worker being started with a given order of
        # arguments, the way the service scripts do; e.g.
        # /usr/bin/python /usr/bin/flumotion-worker -D
        # --daemonize-to /var/cache/flumotion
        # --service-name default /etc/flumotion/workers/default.xml
        if self.cmdline[5].startswith('--service-name'):
            self.service = self.cmdline[6]

    def __repr__(self):
        return '<flumotion-manager %d: %s>' % (self.pid, self.service)


def getProcesses(prefix='flumotion'):
    """
    Get all running processes whose command starts with the given prefix.

    Note: since we use the /proc interface, only the first 15 characters can
    actually be matched. (FIXME: this might not be the case on other OS/Linux
    versions)

    @rtype:   dict of int -> Process
    @returns: a dict of pid -> process
    """
    assert len(prefix) <= 15, "prefix can be at most 15 characters"
    factory = ProcessFactory()
    procs = {}

    for entry in os.listdir('/proc'):
        try:
            pid = int(entry)
        except ValueError:
            continue

        p = factory.process(pid)
        if not p.cmd.startswith(prefix):
            continue

        procs[pid] = p

    return procs

# actual command implementations


def getMultiple(prefix='flumotion'):
    processes = getProcesses(prefix=prefix)

    # convert to a dict based on service name
    serviceToProcess = {}
    for p in processes.values():
        if p.service not in serviceToProcess.keys():
            serviceToProcess[p.service] = []

        serviceToProcess[p.service].append(p)

    # count the number of service names with more than one prefixed running
    return [s for s, p in serviceToProcess.items() if len(p) > 1]


def parseSize(size):
    """
    Given a size string, convert to an int in base unit.
    suffixes are interpreted in SI, as multiples of 1000, not 1024.
    Opposite of L{flumotion.common.formatting.formatStorage}

    @rtype: int
    """
    if len(size) == 0:
        return 0

    suffixes = ['E', 'P', 'T', 'G', 'M', 'k']

    suffix = size[-1]

    if suffix not in suffixes:
        raise KeyError(
            'suffix %c not in accepted list of suffixes %r' % (
            suffix, suffixes))

    i = suffixes.index(suffix)
    power = (len(suffixes) - i) * 3
    multiplier = 10 ** power

    return int(float(size[:-1]) * multiplier)


class JobMultiple(util.LogCommand):
    name = 'multiple'
    description = ("Check for job processes for the same component "
                   "under the same worker.")

    def do(self, args):
        processes = getProcesses(prefix='flumotion')

        # convert to a dict of (worker pid, component name) -> component pid
        components = {}
        for p in processes.values():
            if not p.cmd.startswith('flumotion-job'):
                continue

            # ignore workerPid 1, which is init - see orphaned for that
            if p.ppid == 1:
                continue

            t = (p.ppid, p.component)
            if not t in components.keys():
                components[t] = []

            components[t].append(str(p.pid))

        # count the number of tuples with more than one component running
        which = [(t, p) for t, p in components.items() if len(p) > 1]
        if not which:
            return util.ok('No multiple component jobs running.')

        l = []
        for (workerPid, component), pids in which:
            l.append('worker %d: component %s (%s)' % (
                workerPid, component, ", ".join(pids)))

        return util.critical('%d multiple component job(s) running (%s).' % (
            len(which), ", ".join(l)))


class JobOrphaned(util.LogCommand):
    name = 'orphaned'
    description = "Check for orphaned job processes (without a parent worker)."

    def do(self, args):
        # get a list of pid, vsize and sort on vsize in reverse order
        processes = getProcesses(prefix='flumotion-job')
        orphaned = [str(pid) for pid, p in processes.items() if p.ppid == 1]
        if not orphaned:
            return util.ok('No orphaned job processes running.')

        return util.critical('%d orphaned job process(es) running (%s).' % (
            len(orphaned), ", ".join(orphaned)))


class ProcessVSize(util.LogCommand):
    name = 'vsize'
    usage = '[vsize-options]'

    def addOptions(self):
        default = "128M"
        self.parser.add_option('-w', '--warning',
            action="store", dest="warning",
            help="vsize to warn for (defaults to %s)" % (default),
            default=default)
        default = "512M"
        self.parser.add_option('-c', '--critical',
            action="store", dest="critical",
            help="vsize to give a critical for (defaults to %s)" % (default),
            default=default)

    def do(self, args):
        # get a list of pid, vsize and sort on vsize in reverse order
        l = []
        processes = getProcesses(prefix=self.prefix)
        if not processes:
            return util.ok('No job processes running.')

        for process in processes.values():
            l.append((process.pid, process.vsize))

        l.sort(key=lambda t: t[1])
        l.reverse()

        # check the one with the mostest
        pid, vsize = l[0]

        warning = parseSize(self.options.warning)
        critical = parseSize(self.options.critical)

        if vsize >= critical:
            # count number of critical jobs
            which = [t for t in l if t[1] >= critical]
            return util.critical(
                '%d %s(s) above critical level - highest is %d at %s' % (
                    len(which), self.process_type, pid,
                    formatting.formatStorage(vsize)))

        if vsize >= warning:
            # count number of warning jobs
            which = [t for t in l if t[1] >= warning]
            return util.warning(
                '%d %s(s) above warning level - highest is %d at %s' % (
                    len(which), self.process_type, pid,
                    formatting.formatStorage(vsize)))

        return util.ok('No %s processes above warning level '
            '(highest is %d at %s)' % (
                self.process_type, pid, formatting.formatStorage(vsize)))


class JobVSize(ProcessVSize):
    prefix = 'flumotion-job'
    process_type = 'job'
    description = "Check the vsize of job processes."


class WorkerVSize(ProcessVSize):
    prefix = 'flumotion-worke'
    process_type = 'worker'
    description = "Check the vsize of worker processes."


class ManagerVSize(ProcessVSize):
    prefix = 'flumotion-manag'
    process_type = 'manager'
    description = "Check the vsize of manager processes."


class Job(util.LogCommand):
    description = "Check job processes."

    subCommandClasses = [JobMultiple, JobOrphaned, JobVSize]


class ManagerMultiple(util.LogCommand):
    name = 'multiple'
    description = "Check for manager services running with the same name."

    def do(self, args):
        which = getMultiple('flumotion-manag')
        if which:
            return util.critical(
                '%d manager service(s) running more than once (%s)' % (
                    len(which), ", ".join(which)))

        return util.ok('no manager services running more than once')


class Manager(util.LogCommand):
    description = "Check manager processes."

    subCommandClasses = [ManagerMultiple, ManagerVSize]


class WorkerMultiple(util.LogCommand):
    name = 'multiple'
    description = "Check for worker services running with the same name."

    def do(self, args):
        which = getMultiple('flumotion-worke')
        if which:
            return util.critical(
                '%d worker service(s) running more than once (%s)' % (
                    len(which), ", ".join(which)))

        return util.ok('no worker services running more than once')


class Worker(util.LogCommand):
    description = "Check worker processes."

    subCommandClasses = [WorkerMultiple, WorkerVSize]


class ProcessCommand(util.LogCommand):
    name = "process"
    description = "Check flumotion processes."

    subCommandClasses = [Job, Manager, Worker]
