#!/usr/bin/env python3
# cerbero - a multi-platform build system for Open Source software
# Copyright (C) 2012 Andoni Morales Alastruey <ylatuya@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import subprocess


INT_CMD = 'install_name_tool'
OTOOL_CMD = 'otool'


class OSXRelocator(object):
    '''
    Wrapper for OS X's install_name_tool and otool commands to help
    relocating shared libraries. This reduced relocator only changes
    libraries paths and does not do a full relocation.
    '''

    def __init__(self, recursive, logfile=None):
        self.recursive = recursive
        self.use_relative_paths = True
        self.logfile = None

    def change_libs_path(self, object_file):
        lib_prefixes = self._get_prefixes(object_file)
        for lib in self.list_shared_libraries(object_file):
            prefix = os.path.dirname(lib)
            if prefix in lib_prefixes:
                new_lib = lib.replace(prefix, '@rpath')
                subprocess.call(
                    [INT_CMD, '-change', lib, new_lib, object_file])
        subprocess.call([INT_CMD, '-add_rpath', '.', '-add_rpath',
                        '@loader_path',  '-add_rpath',  '@executable_path', object_file])

    @staticmethod
    def list_shared_libraries(object_file):
        res = subprocess.getoutput(
            "{} -L {}".format(OTOOL_CMD, object_file)).splitlines()
        # We don't use the first line
        libs = res[1:]
        # Remove the first character tabulation
        libs = [str(x[1:]) for x in libs]
        # Remove the version info
        libs = [x.split(' ', 1)[0] for x in libs]
        return libs

    def _get_prefixes(self, object_file):
        prefixes = set([os.path.dirname(x)
                       for x in self.list_shared_libraries(object_file)])
        return [x for x in prefixes if not x.startswith(('/usr/lib', '/System/Library'))]

    def _fix_path(self, path):
        if path.endswith('/'):
            return path[:-1]
        return path


class Main(object):

    def run(self):
        # We use OptionParser instead of ArgumentsParse because this script
        # might be run in OS X 10.6 or older, which do not provide the argparse
        # module
        import optparse
        usage = "usage: %prog [options] library_path"
        description = 'Rellocates object files changing the dependant '\
                      ' dynamic libraries location path with a new one'
        parser = optparse.OptionParser(usage=usage, description=description)
        parser.add_option('-r', '--recursive', action='store_true',
                          default=False, dest='recursive',
                          help='Scan directories recursively')

        options, args = parser.parse_args()
        if len(args) != 1:
            parser.print_usage()
            exit(1)
        relocator = OSXRelocator(options.recursive)
        relocator.change_libs_path(args[0])
        exit(0)


if __name__ == "__main__":
    main = Main()
    main.run()
