# -*- coding: utf-8 -*-
"""
Created on Fri Feb 21 10:22:18 2014

/**
*
* Copyright (c) 2014 Ian Hincks
* Distributed under the GNU GPL v2. For full terms see the file http://github.com/ihincks/ishuttle/LICENSE
*
*/
"""

__version__ = '0.1a'

import os
from subprocess import check_output, CalledProcessError
from IPython.parallel import interactive

import signal, contextlib

import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class RemoteCommander(object):
    """
    RemoteCommander is a backbone class which abstracts sending remote commands
    over ssh and using scp.
    """
    _scp_cmd = 'scp'
    _scp_args = ['-r']
    _ssh_cmd = 'ssh'
    _ssh_args = ['-tt']

    def __init__(self):
        pass


    def _cmd(self, cmd_list, timeout=None):
        with alarm(timeout if timeout is not None else 0):
            # just in case we want to add logging or something later
            logger.debug("RemoteCommander: {}".format(cmd_list))
            check_output(cmd_list) 

    def _remote_cmd(self, cmd, host, timeout=None):
        # Run a command remotely on a single host
        # cmd can be a string with no spaces, or a list of strings
        
        cmd_list = cmd if not isinstance(cmd, basestring) else [cmd]
        self._cmd([self._ssh_cmd] + self._ssh_args + [host] + cmd_list, timeout=timeout)

    def _send(self, local, remote, host, clean=False):
        # scp local to the working directory of the host
        # if clean is True, remote is first emptied with -rf flag
        if clean:
            self._remote_cmd(['rm', '-rf', remote])
        self._cmd([self._scp_cmd] + self._scp_args + [local, host + ':' + remote])

class Shuttle(RemoteCommander):
    """
    A convenience class for shuttling module files to remote engine's servers
    before doing a batch execute of import on each engine.
    """

    _hostnames = None

    def __init__(self, client, remote_working_dir):
        """
        Constructor creates the remote working directory on all engine servers 
        and changes the working directory of all engines to this folder.

        :param Ipython.parallel.Client client: The parrallel client object.
        :param str remote_working_dir: The path of the remote working directory to use.
        """

        super(Shuttle, self).__init__()

        self._client = client
        self._dview = client[:]
        self._wd = remote_working_dir

        self._create_working_dirs()
        self._change_working_dirs()

    def _create_working_dirs(self):
        # Ensures that the working_dir folder actually exists
        try:
            self.circulate_remote_cmd(['mkdir', '-p', '--', self._wd], timeout=20)
        except Alarm:
            raise IOError("Could not create working directories in 20 seconds. Perhaps you have a problem with your SSH configuration?")

    def _change_working_dirs(self):
        # Goes through each engine and switches its working directory
        # to working_dir

        # We need to decorate as interactive or else chdir_wd will show up
        # in ishuttle on the engines, which won't exist
        @interactive
        def chdir_wd(wd):
            import os
            os.chdir(wd)

        self._dview.apply_sync(chdir_wd, self._wd)
        

    def _fetch_hostnames(self):
        # Fetch all distinct hostnames across engines

        # We need to decorate as interactive or else gethostname will show up
        # in ishuttle on the engines, which won't exist
        @interactive
        def gethostname():
            import socket, getpass
            return (getpass.getuser(), socket.gethostname())

        results = self._dview.apply_sync(gethostname)
        results = map(lambda pair: '@'.join(pair), results)

        # delete duplicates and store
        self._hostnames = list(set(results))
        

    @property
    def hostnames(self):
        if self._hostnames is None:
            self._fetch_hostnames()
        return self._hostnames

    def circulate_send(self, local, clean=False):
        """
        Send local files to all hosts' working directory over scp
        If clean is True, the working directory is first emptied with -rf flag
        """
        for host in self.hostnames:
            self._send(local, self._wd, host, clean=clean)

    def circulate_remote_cmd(self, cmd, timeout=None):
        """
        Run the same Popen command list on each of the engine servers
        """

        for host in self.hostnames:
            self._remote_cmd(cmd, host, timeout=timeout)

    def remote_import(self, module, import_as=None, path=None):
        """
            Attempts to import the given module on all engines. Follows the 
            import immediately with a reload.

            :param str module: Module to import
            :param str import_as: Alias of imported module, default is `None`.
            :param str path: Optional path of module on local machine.
        """
        
        # TODO: test the case where a . exists
        mod_name = module.split('.')[0]

        # if there's no dot, assume the module has name module.py
        # otherwise, assume it's a folder. in both cases, send it to all hosts
        path = os.getcwd() if path is None else path
        if '.' in module:
            self.circulate_send(os.path.join(path, module))
        else:
            self.circulate_send(os.path.join(path, module + '.py'))

        # Now import and reload on all engines
        if import_as is None:
            self._dview.execute('import ' + module)
            self._dview.execute('reload(' + module + ')')
        else:
            self._dview.execute('import ' + module + ' as ' + import_as)
            self._dview.execute('reload(' + import_as + ')')
        
        
# See http://stackoverflow.com/questions/1191374/subprocess-with-timeout for
# why this works, and why it will never work on Windows.

class Alarm(Exception):
    def __init__(self, signum, frame):
        super(Alarm, self).__init__()
        self.signum = signum
        self.frame = frame
    
def alarm_handler(signum, frame):
    raise Alarm(signum, frame)
    
signal.signal(signal.SIGALRM, alarm_handler)

@contextlib.contextmanager
def alarm(timeout):
    signal.alarm(timeout)
    yield
    signal.alarm(0)

