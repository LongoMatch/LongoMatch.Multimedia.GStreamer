# cerbero - a multi-platform build system for Open Source software
# Copyright (C) 2013 Andoni Morales Alastruey <ylatuya@gmail.com>
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
import re
import subprocess
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True).stdout.decode('utf-8').splitlines()


class RecursiveLister():

    def list_file_deps(self, prefix:Path, path):
        raise NotImplemented()

    def find_deps(self, prefix, lib, state={}, ordered=[]):
        if state.get(lib, 'clean') == 'processed':
            return
        if state.get(lib, 'clean') == 'in-progress':
            return
        state[lib] = 'in-progress'
        lib_deps = self.list_file_deps(prefix, lib)
        for libdep in lib_deps:
            self.find_deps(prefix, libdep, state, ordered)
        state[lib] = 'processed'
        ordered.append(lib)
        return ordered

    def list_deps(self, prefix: Path, paths: list):
        deps = set()
        state = {}
        ordered = []
        for path in paths:
            if not path.exists():
                continue
            new_deps = self.find_deps(prefix, path.resolve(), state, ordered)
            if new_deps is None:
                continue
            new_deps.append(path)
            deps.update(new_deps)
        return deps


class ObjdumpLister(RecursiveLister):

    def list_file_deps(self, prefix:Path, path:Path):
        env = os.environ.copy()
        env['LC_ALL'] = 'C'
        cmd = ['objdump', '-xw', path]
        files = subprocess.run(cmd, capture_output=True).stdout.decode('utf-8').splitlines()
        prog = re.compile(r"(?i)^.*DLL[^:]*: (\S+\.dll)$")
        files = [prog.sub(r"\1", x) for x in files if prog.match(x) is not None]
        files = [os.path.join(prefix, 'bin', x) for x in files if
                 x.lower().endswith('dll')]
        return [os.path.realpath(x) for x in files if os.path.exists(x)]


class OtoolLister(RecursiveLister):

    def list_file_deps(self, prefix:Path, path:Path):
        cmd = ['otool', '-L', path]
        deps = set(subprocess.run(cmd, capture_output=True).stdout.decode('utf-8').splitlines())
        # Shared libraries might be relocated, we look for files with the
        # prefix or starting with @rpath
        deps = [x.strip().split(' ')[0]
                 for x in deps if str(prefix) in x or "@rpath" in x]
        # Remove link to the same library
        # /Library/Frameworks/GStreamer.framework/Versions/1.0/lib/gstreamer-1.0/libgstapp.dylib' -> '@rpath/libgstapp.dylib'
        deps = [d for d in deps if not d.endswith(path.name)]
        rpaths = self._get_rpaths(path, prefix)
        deps_paths = [self._replace_rpath(x, rpaths) for x in deps]
        return deps_paths

    def _get_rpaths(self, path, prefix):
        rpaths = set()
        cmd = ['otool', '-l', path]
        lines_iter = iter(subprocess.run(cmd, capture_output=True).stdout.decode('utf-8').splitlines())
        while True:
            line = next(lines_iter, None)
            if line is None:
                break
            elif "cmd LC_RPATH" in line:
                line = next(lines_iter)
                rpath = next(lines_iter).strip().split(' ')[1]
                if len(rpath) == 1:
                    rpath = rpath.replace(".", str(prefix))
                else:
                    rpath = rpath.replace(
                        "@loader_path", os.path.dirname(path))
                    rpath = rpath.replace(
                        "@executable_path", os.path.dirname(path))
                rpaths.add(Path(rpath))
        return rpaths

    def _replace_rpath(self, path:str, rpaths:list):
        for rpath in rpaths:
            translatedPath = Path(path.replace("@rpath", str(rpath)))
            if translatedPath.exists():
                return translatedPath.resolve()
        return Path(path).resolve()


class LddLister():

    def list_deps(self, prefix, path):
        cmd =  ['ldd', path]
        files = subprocess.run(cmd, capture_output=True).stdout.decode('utf-8').splitlines()
        return [x.split(' ')[2] for x in files if prefix in x]


class DepsTracker():

    BACKENDS = {
        "Windows": ObjdumpLister,
        "Linux" : LddLister,
        "Darwin" : OtoolLister}

    def __init__(self, platform, prefix):
        self.libs_deps = {}
        self.prefix = prefix
        self.lister = self.BACKENDS[platform]()

    def list_deps(self, paths:list):
        deps = self.lister.list_deps(self.prefix, paths)
        return [d.resolve() for d in deps]