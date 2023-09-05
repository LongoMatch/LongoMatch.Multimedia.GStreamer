import argparse
import glob
import hashlib
import platform
import shutil
import subprocess
import os
import shlex
import urllib.request
from pathlib import Path
from osxrelocator import OSXRelocator
from depstracker import DepsTracker

GST_TEMPLATE = {
    'Windows': "gstreamer-1.0{}-msvc-x86_64-{}.msi",
    'Darwin': "gstreamer-1.0{}-{}-universal.pkg"
}
GST_URL_TEMPLATE = {
    'Windows': "https://gstreamer.freedesktop.org/data/pkg/windows/{}/msvc/",
    'Darwin': "https://gstreamer.freedesktop.org/data/pkg/osx/{}"
}


def download(url, output_file=None, md5=None):
    if output_file is None:
        output_file = url.split("/")[:-1]
    if os.path.exists(output_file):
        if md5 is not None:
            with open(output_file) as file_to_check:
                data = file_to_check.read()
                md5_returned = hashlib.md5(data).hexdigest()
                if md5_returned == md5:
                    print(f"File {output_file} already downloaded")
                    return
        else:
            print(f"File {output_file} already downloaded")
            return
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, output_file)
    print(f"Downloaded {output_file}")


def run(cmd, cwd=None, split=False):
    if split:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
    if isinstance(cmd, list):
        print(f"Running command: {' '.join([str(x) for x in cmd])} in {cwd}")
    else:
        print(f"Running command: {cmd} in {cwd}")
    popen = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, universal_newlines=True, cwd=cwd
    )
    lines = []
    for stdout_line in iter(popen.stdout.readline, ""):
        lines.append(stdout_line.split('\n')[0])
        print(stdout_line)
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)
    return lines


def replace(filepath, replacements):
    ''' Replaces keys in the 'replacements' dict with their values in file '''
    with open(filepath, 'r') as f:
        content = f.read()
    for k, v in replacements.items():
        content = content.replace(k, v)
    with open(filepath, 'w+') as f:
        f.write(content)


class Build:

    def __init__(self, platform: str, nuget_platform, source_dir: Path, build_dir: Path, cache_dir: Path = None):
        self.platform = platform
        self.nuget_platform = nuget_platform
        self.source_dir = source_dir
        self.build_dir = build_dir
        if cache_dir is None:
            cache_dir = self.build_dir / "cache"
        self.cache_dir = cache_dir
        self.cerbero_dir = self.cache_dir / "cerbero"
        self.gst_dir = self.cache_dir / "gstreamer"
        self.gst_build_dir = self.build_dir / "gst-build"
        self.prefix = self.build_dir / 'prefix'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.nuget_cmd = [self.cache_dir / "nuget.exe"]
        self._set_gst_version()
        self._set_nuget_version()
        self.nuget_dir = self.build_dir / "nuget"
        self.nuget_dir.mkdir(parents=True, exist_ok=True)

    def install_deps(self):
        run(["pip3", "install", "meson", "ninja"])
        download("https://dist.nuget.org/win-x86-commandline/latest/nuget.exe",
                 self.cache_dir / "nuget.exe")

    def install_gst_pkg(self):
        filename = GST_TEMPLATE[self.platform].format("", self.gst_version)
        filename_devel = GST_TEMPLATE[self.platform].format(
            "-devel", self.gst_version)
        url = f"{GST_URL_TEMPLATE[self.platform].format(self.gst_version)}/{filename}"
        url_devel = f"{GST_URL_TEMPLATE[self.platform].format(self.gst_version)}/{filename_devel}"
        download(url, self.cache_dir / filename)
        download(url_devel, self.cache_dir / filename_devel)
        self._install_package(self.cache_dir / GST_TEMPLATE[self.platform].format("", self.gst_version),
                              self.build_dir / "gst_install.log")
        self._install_package(self.cache_dir / GST_TEMPLATE[self.platform].format("-devel", self.gst_version),
                              self.build_dir / "gst_devel_install.log")

    def configure_gst(self):
        cmd = ["meson", "setup", ".", self.gst_dir.as_posix(),
               "--wrap-mode=nofallback",
               f"--prefix={self.prefix.as_posix()}",
               "-Dauto_features=disabled",
               "-Dbase=disabled",
               "-Dgood=disabled",
               "-Dbad=enabled",
               "-Dgst-plugins-bad:mpegtsdemux=enabled"]
        if self.gst_build_dir.exists():
            shutil.rmtree(self.gst_build_dir)
        self.gst_build_dir.mkdir(parents=True)
        run(cmd, self.gst_build_dir)

    def build_gst(self):
        run(f"ninja", self.gst_build_dir)

    def install_gst(self):
        pass

    def install_gst_sharp_from_gstreamer(self):
        subprojects = self.gst_build_dir / "subprojects"

        gtk_sharp_src = subprojects / "gtk-sharp" / "Source"

        shutil.copy(gtk_sharp_src / "gio" / "gio-sharp.dll", self.nuget_dir)
        shutil.copy(gtk_sharp_src / "glib" / "glib-sharp.dll", self.nuget_dir)
        shutil.copy(subprojects / "gstreamer-sharp" /
                    "sources" / "gstreamer-sharp.dll", self.nuget_dir)
        shutil.copy(subprojects / "gstreamer-sharp" / "ges" /
                    "gst-editing-services-sharp.dll", self.nuget_dir)

    def create_runtime_nuget_package(self):
        replacements = {'{version}': self.nuget_version,
                        '{platform}': self.nuget_platform}

        shutil.copy(self.source_dir / "runtime.json.tpl",
                    self.build_dir / "runtime.json")
        replace(self.build_dir / "runtime.json", replacements)
        shutil.copy(self.source_dir / "longomatch-multimedia-gstreamer.runtime.nuspec.tpl",
                    self.build_dir / f"longomatch-multimedia-gstreamer.runtime.{self.nuget_platform}.nuspec")
        replace(self.build_dir /
                f"longomatch-multimedia-gstreamer.runtime.{self.nuget_platform}.nuspec", replacements)
        shutil.copy(self.source_dir / "LongoMatch.Multimedia.GStreamer.runtime.targets",
                    self.nuget_dir / f"LongoMatch.Multimedia.GStreamer.runtime.{self.nuget_platform}.targets")
        open(self.nuget_dir / "_._", mode='w').close()

        run(self.nuget_cmd + ["pack", f"longomatch-multimedia-gstreamer.runtime.{self.nuget_platform}.nuspec",
                              "-Verbosity", "detailed"], self.build_dir)

    def push_runtime_nuget_package(self):
        # From macOS we only push the native binaries
        self._push_nuget(
            f"LongoMatch.Multimedia.GStreamer.runtime.{self.nuget_platform}", self.nuget_version)

    def _get_files_from_plugins(self):
        plugins = [x.split('\n')[0] for x in open(self.source_dir / "plugins_list.txt").readlines() if not x.startswith('#')]
        plugins_files = [self._get_file_from_plugin_name(p) for p in plugins]
        tracker = DepsTracker (platform.system(), self._get_gst_install_dir())
        return tracker.list_deps(plugins_files)

    def _get_files_from_libs(self):
        libs = ["gstreamer-1.0",
                "gstapp-1.0",
                "gstaudio-1.0",
                "gstbase-1.0",
                "gstcontroller-1.0",
                "gstfft-1.0",
                "gstgl-1.0",
                "gstnet-1.0",
                "gstpbutils-1.0",
                "gstrtp-1.0",
                "gstrtsp-1.0",
                "gstsdp-1.0",
                "gsttag-1.0",
                "gstvideo-1.0",
                "gstwebrtc-1.0",
                "ges-1.0"]
        lib_files = [self._get_file_from_lib_name(p) for p in libs]
        tracker = DepsTracker (platform.system(), self._get_gst_install_dir())
        return tracker.list_deps(lib_files)

    def _install_package(self, path, log_file):
        raise NotImplemented()

    def _push_nuget(self, name, version):
        path = self.build_dir / f"{name}.{version}.nupkg"
        run(["dotnet", "nuget", "push", path,
            "--source", "https://nuget.pkg.github.com/longomatch/index.json",
             "--api-key", os.environ["GITHUB_TOKEN"]])

    def _set_gst_version(self):
        self.gst_version = os.environ.get("GITVERSION_MAJORMINORPATCH", None)
        if self.gst_version is None:
            self.gst_version = run(
                ["dotnet-gitversion", "/showvariable", "MajorMinorPatch"])[0]

    def _set_nuget_version(self):
        self.nuget_version = os.environ.get("GITVERSION_FULLSEMVER", None)
        if self.nuget_version is None:
            self.nuget_version = run(
                ["dotnet-gitversion", "/showvariable", "FullSemVer"])[0]

    def all_deps(self):
        self.install_deps()
        self.install_gst_pkg()
        #self.clone_gst()
        #self.configure_gst()
        #self.build_gst()
        #self.build_gst_sharp()
        self.install_gst()
        self.create_runtime_nuget_package()
        self.push_runtime_nuget_package()


class BuildMacOS(Build):

    def __init__(self, source_dir: Path, build_dir: Path, cache_dir: Path = None):
        super().__init__('Darwin', 'osx-x64', source_dir, build_dir, cache_dir)
        self.nuget_cmd = ["mono", self.cache_dir / "nuget.exe"]

    def configure_gst(self):
        gst_install_dir = self._get_gst_install_dir()
        os.environ["PKG_CONFIG"] = str(
            (gst_install_dir / "bin" / "pkg-config").absolute())
        os.environ["PKG_CONFIG_LIBDIR"] = str(
            (gst_install_dir / "lib" / "pkgconfig").absolute())
        super().configure_gst()

    def install_gst(self):
        super().install_gst()
        gst_native = self.nuget_dir / "runtimes" / self.nuget_platform / "native"
        gst_native_scanner_dir = self.nuget_dir / "runtimes" / \
            self.nuget_platform / "native" / "libexec" / "gstreamer-1.0"
        gst_native_scanner_dir.mkdir(parents=True, exist_ok=True)
        gst_native_plugins = gst_native / "lib" / "gstreamer-1.0"
        gst_native_plugins.mkdir(parents=True, exist_ok=True)
        gst_native_gio_modules_dir = gst_native / "lib" / "gio" / "modules"
        gst_native_gio_modules_dir.mkdir(parents=True, exist_ok=True)

        # GStreamer
        gst_install_dir = self._get_gst_install_dir()
        lib_files = self._get_files_from_plugins()
        lib_files += self._get_files_from_libs()
        lib_files = set(lib_files)

        # The installer does not respect symlinks, copy only the real
        # library:
        # Pick libgobject-2.0.0.dylib and leave libgobject-2.0.dylib
        files = {}
        for f in lib_files:
            if not f.exists():
                print(f"File not found: {f}")
                continue
            if f.is_symlink():
                continue
            key = f.stem
            # Take the path with the longest path libgobject-2.0.0.dylib vs libgobject-2.0.dylib
            if not key in files or len(files[key].name) < len(f.name):
                files[key] = f

        relocator = OSXRelocator(False)
        strip = os.environ.get("STRIP", "strip")

        for f in files.values():
            if "lib/gstreamer-1.0" in str(f):
                self.copy(f, gst_native_plugins, relocator, strip)
            else:
                self.copy(f, gst_native, relocator, strip)

        self.copy(gst_install_dir / "libexec" / "gstreamer-1.0" /
                  "gst-plugin-scanner", gst_native_scanner_dir, relocator, strip)
        self.copy(gst_install_dir / "lib" / "gio" / "modules" / "libgioopenssl.so",
                gst_native_gio_modules_dir, relocator, strip)

        avlibs = glob.glob("/Library/Frameworks/GStreamer.framework/Versions/1.0/lib/libav*.*.*.dylib")
        avlibs = [os.path.split(x)[-1] for x in avlibs]
        for avlib in avlibs:
            avlib_link = avlib.rsplit('.', 3)[0] + '.dylib'
            run(["rm", "-f", avlib_link], gst_native)
            run(["ln", "-s", avlib, avlib_link], gst_native)

    def copy(self, src, dst_dir, relocator, strip):
        filename = src.name
        dst = dst_dir / filename
        run(["lipo", src, "-thin", "x86_64", "-output", dst])
        if dst.suffix == ".dylib" or dst.name == "gst-plugin-scanner":
            relocator.change_libs_path(dst)
            run([strip, "-SX", dst])

    def _get_gst_install_dir(self):
        return Path("/Library/Frameworks/GStreamer.framework/Versions/1.0/")

    def _install_package(self, path, log_file):
        run(["sudo", "installer", "-pkg", path, "-target", "/"])

    def _get_file_from_plugin_name(self, plugin_name):
        return self._get_gst_install_dir() / "lib" / "gstreamer-1.0" / f'libgst{plugin_name}.dylib'

    def _get_file_from_lib_name(self, lib_name):
        return self._get_gst_install_dir() / "lib" / f'lib{lib_name}.0.dylib'


class BuildWin64(Build):

    def __init__(self, source_dir: Path, build_dir: Path, cache_dir: Path = None):
        super().__init__('Windows', 'win-x64', source_dir, build_dir, cache_dir)

    def install_deps(self):
        super().install_deps()
        Path("C:/Strawberry/c/bin/xsltproc.EXE").unlink()
        download("https://dist.nuget.org/win-x86-commandline/latest/nuget.exe",
                 self.cache_dir / "nuget.exe")

    def configure_gst(self):
        gst_install_dir = self._get_gst_install_dir()
        os.environ["PKG_CONFIG"] = str(
            (gst_install_dir / "bin" / "pkg-config.exe").absolute())
        os.environ["PKG_CONFIG_LIBDIR"] = str(
            (gst_install_dir / "lib" / "pkgconfig").absolute())
        os.environ["PATH"] = f'{str(gst_install_dir / "bin")};{os.environ["PATH"]}'

        super().configure_gst()

    def install_gst(self):
        super().install_gst()
        gst_native = self.nuget_dir / "runtimes" / "win-x64" / "native"
        gst_native_plugins = gst_native / "lib" / "gstreamer-1.0"
        gst_native_plugins.mkdir(parents=True, exist_ok=True)
        gst_native_scanner_dir = self.nuget_dir / "runtimes" / \
            self.nuget_platform / "native" / "libexec" / "gstreamer-1.0"
        gst_native_scanner_dir.mkdir(parents=True, exist_ok=True)
        gst_native_gio_modules_dir = gst_native / "lib" / "gio" / "modules"
        gst_native_gio_modules_dir.mkdir(parents=True, exist_ok=True)
        subprojects = self.gst_build_dir / "subprojects"

        # GStreamer
        gst_install_dir = self._get_gst_install_dir()
        for file in glob.glob(f'{gst_install_dir / "bin"}/*.dll'):
            shutil.copy(file, gst_native)
        for file in glob.glob(f'{gst_install_dir / "lib" / "gstreamer-1.0"}/*.dll'):
            shutil.copy(file, gst_native_plugins)
        shutil.copy(gst_install_dir / "libexec" / "gstreamer-1.0" /
                    "gst-plugin-scanner.exe", gst_native_scanner_dir)
        shutil.copy(gst_install_dir / "lib" / "gio" / "modules" / "gioopenssl.dll",
                gst_native_gio_modules_dir)

        # Strip GCC shared libraries
        strip = os.environ.get("STRIP", "strip.exe")
        for av in ['avcodec', 'avformat', 'avfilter', 'avutil']:
            for f in glob.glob(f'{gst_native}/{av}*.dll'):
                run(f"{strip} -s {f}")
        for f in glob.glob(f"{gst_native}/lib*dll"):
            run(f"{strip} -s {f}")

    def _get_gst_install_dir(self):
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\GStreamer1.0\x86_64",
                             0, winreg.KEY_ALL_ACCESS)
        return Path(winreg.QueryValueEx(key, 'InstallDir')[0]) / "1.0" / "msvc_x86_64"

    def _install_package(self, path, log_file):
        run(f"msiexec /i {path} /quiet /l* {log_file} /norestart ADDLOCAL=All")

    def _get_file_from_plugin_name(self, plugin_name):
        return self._get_gst_install_dir() / "lib" / "gstreamer-1.0" / f'gst{plugin_name}.dll'

    def _get_file_from_lib_name(self, lib_name):
        return self._get_gst_install_dir() / "lib" / f'{lib_name}-0.dll'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('build_rule', type=str,
                        help='The name of the build rule to call', default='all')
    parser.add_argument('-c', '--cache-dir', type=str,
                        help='Cache directory to use')
    parser.add_argument('-b', '--build-dir', type=str,
                        help='Build directory to use')
    args = parser.parse_args()
    root_dir = Path(os.path.dirname(__file__))
    if args.build_dir is None:
        build_dir = root_dir / "build"
    else:
        build_dir = Path(os.path.expanduser(args.build_dir))
    build_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(build_dir)
    if args.cache_dir is None:
        cache_dir = build_dir / "cache"
    else:
        cache_dir = Path(os.path.expanduser(args.cache_dir))

    plat = platform.system()
    if plat == 'Windows':
        build_cls = BuildWin64
    elif plat == 'Darwin':
        build_cls = BuildMacOS
    else:
        print("OS not supported")
        exit(-1)
    build = build_cls(root_dir, build_dir, cache_dir)
    print(f"Using cache: {str(cache_dir.absolute())}")
    getattr(build, args.build_rule)()
