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
        self.version = self._get_git_version()
        self.gst_version = (
            f"{self.version.major}.{self.version.minor}.{self.version.patch}"
        )
        self.nuget_version = f"{self.version}"
        self.nuget_dir = self.build_dir / "nuget"
        self.nuget_dir.mkdir(parents=True, exist_ok=True)
        self.gst_configure_cmd = [
            "meson",
            "setup",
            self.gst_build_dir.as_posix(),
            self.gst_dir.as_posix(),
            "--wrap-mode=nofallback",
            f"--prefix={self.prefix.as_posix()}",
            "-Dauto_features=disabled",
            "--reconfigure",
        ]

    def install_deps(self):
        run(["pip3", "install", "--break-system-packages", "meson", "ninja"])
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

    def clone_gst(self):
        if self.gst_dir.exists():
            run(["git", "fetch"], self.gst_dir)
            run(["git", "reset", "--hard", "1.24"], self.gst_dir)
        else:
            run(
                [
                    "git",
                    "clone",
                    "https://github.com/LongoMatch/gstreamer.git",
                    self.gst_dir,
                    "--single-branch",
                    "--branch",
                    "1.24",
                ],
            )

    def configure_gst(self):
        run(self.gst_configure_cmd)

    def compile_gst(self):
        run(["meson", "compile", "-C", self.gst_build_dir])

    def install_gst(self):
        self.gst_plugins = Path("lib") / "gstreamer-1.0"
        self.gst_native = self.nuget_dir / "runtimes" / self.nuget_platform / "native"
        self.gst_native_plugins = self.gst_native / self.gst_plugins
        self.gst_native_plugins.mkdir(parents=True, exist_ok=True)
        self.gst_native_scanner_dir = (
            self.nuget_dir
            / "runtimes"
            / self.nuget_platform
            / "native"
            / "libexec"
            / "gstreamer-1.0"
        )
        self.gst_native_scanner_dir.mkdir(parents=True, exist_ok=True)
        self.gst_native_gio_modules_dir = self.gst_native / "lib" / "gio" / "modules"
        self.gst_native_gio_modules_dir.mkdir(parents=True, exist_ok=True)
        self.subprojects = self.gst_build_dir / "subprojects"

        self.gst_native_debug = (
            self.nuget_dir / "runtimes" / self.nuget_platform / "native-debug"
        )
        self.gst_native_plugins_debug = self.gst_native_debug / self.gst_plugins
        self.gst_native_debug.mkdir(parents=True, exist_ok=True)
        self.gst_native_plugins_debug.mkdir(parents=True, exist_ok=True)

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
        self._create_nuget_package()

    def create_runtime_debug_nuget_package(self):
        self._create_nuget_package(True)

    def push_runtime_nuget_packages(self):
        self._push_nuget(
            f"LongoMatch.Multimedia.GStreamer.runtime.{self.nuget_platform}", self.nuget_version)
        self._push_nuget(
            f"LongoMatch.Multimedia.GStreamer.runtime.debug.{self.nuget_platform}",
            self.nuget_version,
        )

    def _create_nuget_package(self, is_debug=False):
        name = "LongoMatch.Multimedia.GStreamer"
        debug = ".debug" if is_debug else ""
        src_name = f"{name}.runtime{debug}"
        dst_name = f"{name}.runtime{debug}.{self.nuget_platform}"

        replacements = {
            "{version}": self.nuget_version,
            "{platform}": self.nuget_platform,
        }
        shutil.copy(
            self.source_dir / "runtime.json.tpl", self.build_dir / "runtime.json"
        )
        replace(self.build_dir / "runtime.json", replacements)
        shutil.copy(
            self.source_dir / f"{src_name}.nuspec.tpl",
            self.build_dir / f"{dst_name}.nuspec",
        )
        replace(self.build_dir / f"{dst_name}.nuspec", replacements)

        shutil.copy(
            self.source_dir / f"{name}.runtime.targets",
            self.nuget_dir / f"{dst_name}.targets",
        )

        open(self.nuget_dir / "_._", mode="w").close()

        run(
            self.nuget_cmd
            + [
                "pack",
                f"{dst_name}.nuspec",
                "-Verbosity",
                "detailed",
            ],
            self.build_dir,
        )

    def _get_files_from_plugins(self, tracker: DepsTracker):
        plugins = [x.split('\n')[0] for x in open(self.source_dir / "plugins_list.txt").readlines() if not x.startswith('#')]
        plugins_files = [self._get_file_from_plugin_name(p) for p in plugins]
        return tracker.list_deps(plugins_files)

    def _get_files_from_libs(self, tracker: DepsTracker):
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
        return tracker.list_deps(lib_files)

    def _install_package(self, path, log_file):
        raise NotImplemented()

    def _push_nuget(self, name, version):
        path = self.build_dir / f"{name}.{version}.nupkg"
        run(["dotnet", "nuget", "push", path,
            "--source", "https://nuget.pkg.github.com/longomatch/index.json",
             "--api-key", os.environ["GITHUB_TOKEN"]])

    def _get_git_version(self):
        from version import get_version

        return get_version(self.source_dir, self.source_dir / "version.txt")

    def build_gst(self):
        self.clone_gst()
        self.configure_gst()
        self.compile_gst()

    def all_deps(self):
        self.install_deps()
        self.install_gst_pkg()
        self.build_gst()
        self.install_gst()
        self.create_runtime_nuget_package()
        self.create_runtime_debug_nuget_package()
        self.push_runtime_nuget_packages()


class BuildMacOS(Build):

    def __init__(self, source_dir: Path, build_dir: Path, cache_dir: Path = None):
        super().__init__('Darwin', 'osx', source_dir, build_dir, cache_dir)
        self.nuget_cmd = ["mono", self.cache_dir / "nuget.exe"]

    def _get_configure_cmd(self, arch):
        gst_configure_cmd = [
            "meson",
            "setup",
            (self.gst_build_dir / arch).as_posix(),
            self.gst_dir.as_posix(),
            "--wrap-mode=nofallback",
            f"--prefix={self.prefix.as_posix()}",
            "--reconfigure",
            "-Dauto_features=disabled",
            "-Dbase=enabled",
            "-Dgst-plugins-base:gl=enabled",
            "-Dgst-plugins-base:gl_api=auto",
            "-Dgst-plugins-base:gl_platform=auto",
            "-Dgst-plugins-base:gl_winsys=auto",
            "-Dgood=disabled",
            "-Dugly=disabled",
            "-Dbad=enabled",
            "-Dgst-plugins-bad:gl=enabled",
            "-Dgst-plugins-bad:applemedia=enabled",
        ]
        if arch == "x86_64":
            gst_configure_cmd += [
                f"--cross-file={self.source_dir / 'meson-cross-file.txt'}",
            ]
        return gst_configure_cmd

    def configure_gst(self):
        gst_install_dir = self._get_gst_install_dir()
        os.environ["PKG_CONFIG"] = str(
            (gst_install_dir / "bin" / "pkg-config").absolute()
        )
        os.environ["PKG_CONFIG_LIBDIR"] = str(
            (gst_install_dir / "lib" / "pkgconfig").absolute()
        )
        self.gst_configure_cmd = self._get_configure_cmd("x86_64")
        super().configure_gst()
        self.gst_configure_cmd = self._get_configure_cmd("arm64")
        super().configure_gst()

    def compile_gst(self):
        run(["meson", "compile", "-C", self.gst_build_dir / "x86_64"])
        run(["meson", "compile", "-C", self.gst_build_dir / "arm64"])

    def install_gst(self):
        super().install_gst()

        # GStreamer
        tracker = DepsTracker (platform.system(), self._get_gst_install_dir())
        gst_install_dir = self._get_gst_install_dir()
        lib_files = self._get_files_from_plugins(tracker)
        lib_files += self._get_files_from_libs(tracker)
        gst_gio_openssl = gst_install_dir / "lib" / "gio" / "modules" / "libgioopenssl.so"
        gst_libsoup = gst_install_dir / "lib" / "libsoup-2.4.1.dylib"
        gst_inspect = gst_install_dir / "bin" / "gst-inspect-1.0"
        lib_files += tracker.list_deps([gst_gio_openssl, gst_libsoup, gst_inspect])
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
                self.copy(f, self.gst_native_plugins, relocator, strip)
            elif "lib/gio/modules" in str(f):
                self.copy(f, self.gst_native_gio_modules_dir, relocator, strip)
            else:
                self.copy(f, self.gst_native, relocator, strip)

        self.copy(
            gst_install_dir / "libexec" / "gstreamer-1.0" / "gst-plugin-scanner",
            self.gst_native_scanner_dir,
            relocator,
            strip,
        )

        plugins = ["subprojects/gst-plugins-bad/sys/applemedia/libgstapplemedia.dylib"]
        for plugin in plugins:
            universal_lib_path = self.gst_build_dir / plugin.split("/")[-1]
            run(
                [
                    "lipo",
                    self.gst_build_dir / "x86_64" / plugin,
                    self.gst_build_dir / "arm64" / plugin,
                    "-create",
                    "-output",
                    universal_lib_path,
                ]
            )
            self.copy(universal_lib_path, self.gst_native_plugins, relocator, strip)

        avlibs = glob.glob("/Library/Frameworks/GStreamer.framework/Versions/1.0/lib/libav*.*.*.dylib")
        avlibs = [os.path.split(x)[-1] for x in avlibs]
        for avlib in avlibs:
            avlib_link = avlib.rsplit('.', 3)[0] + '.dylib'
            run(["rm", "-f", avlib_link], self.gst_native)
            run(["ln", "-s", avlib, avlib_link], self.gst_native)

    def copy(self, src, dst_dir, relocator, strip):
        filename = src.name
        dst = dst_dir / filename
        shutil.copy(src, dst)
        if dst.suffix in [".dylib", ".so"] or dst.name.startswith("gst-"):
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

        xsltproc = Path("C:/Strawberry/c/bin/xsltproc.EXE")
        if xsltproc.exists():
            xsltproc.unlink()
        download("https://dist.nuget.org/win-x86-commandline/latest/nuget.exe",
                 self.cache_dir / "nuget.exe")

    def build_gst(self):
        pass

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

        tracker = DepsTracker(platform.system(), self._get_gst_install_dir())
        gst_install_dir = self._get_gst_install_dir()
        files = self._get_files_from_plugins(tracker)
        files += self._get_files_from_libs(tracker)
        gst_gio_openssl = gst_install_dir / "lib" / "gio" / "modules" / "gioopenssl.dll"
        gst_libsoup = gst_install_dir / "lib" / "soup-2.4.1.dll"
        gst_inspect = gst_install_dir / "bin" / "gst-inspect-1.0.exe"
        files += tracker.list_deps([gst_gio_openssl, gst_libsoup, gst_inspect])
        files = set(files)

        for f in files:
            if "lib\\gstreamer-1.0" in str(f):
                shutil.copy(f, self.gst_native_plugins)
            elif "lib\\gio\\modules" in str(f):
                shutil.copy(f, self.gst_native_gio_modules_dir)
            else:
                shutil.copy(f, self.gst_native)

        # Strip GCC shared libraries
        strip = os.environ.get("STRIP", "strip.exe")
        for av in ['avcodec', 'avformat', 'avfilter', 'avutil']:
            for f in glob.glob(f"{self.gst_native}/{av}*.dll"):
                run(f"{strip} -s {f}")
        for f in glob.glob(f"{self.gst_native}/lib*dll"):
            if 'libssl' in f:
                continue
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
