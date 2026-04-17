import subprocess

# File containing the list of plugins
PLUGIN_LIST_FILE = "plugins_list.txt"

# Dictionaries to hold plugins categorized by their source module
plugin_categories = {
    "gstreamer": [],
    "gst-plugins-base": [],
    "gst-plugins-good": [],
    "gst-plugins-bad": [],
    "gst-plugins-ugly": [],
    "gst-libav": [],
    "gst-editing-services": [],
}


def read_plugins_from_file(file_path):
    """Reads the list of plugins from the specified file."""
    with open(file_path, "r") as file:
        plugins = [line.strip() for line in file if line.strip() and not line.startswith("#")]
    return plugins


def categorize_plugins(plugins):
    """Categorizes plugins based on their source module."""
    for plugin in plugins:
        try:
            # Run gst-inspect-1.0 for the plugin
            result = subprocess.run(
                ["/Library/Frameworks/GStreamer.framework/Commands/gst-inspect-1.0", plugin],
                capture_output=True,
                text=True,
                check=True,
            )
            # Find the line containing "source module"
            for line in result.stdout.splitlines():
                if "Source module" in line:
                    source_module = line.split(" ")[-1].strip()
                    # Add the plugin to the appropriate category
                    if source_module in plugin_categories:
                        plugin_categories[source_module].append(plugin)
                    else:
                        print(f"Unknown source module '{source_module}' for plugin '{plugin}'")
                    break
        except subprocess.CalledProcessError:
            print(f"Failed to inspect plugin '{plugin}'")


# Read plugins from the file
plugins = read_plugins_from_file(PLUGIN_LIST_FILE)

# Categorize the plugins
categorize_plugins(plugins)


meson_cmd = [
    "meson",
    "setup",
    "builddir",
    "-Dauto_features=disabled",
    "-Dbase=enabled",
    "-Dgood=enabled",
    "-Dbad=enabled",
    "-Dugly=enabled",
    "-Dges=enabled",
]


# Print the categorized plugins
for category, plugins in plugin_categories.items():
    for plugin in plugins:
        if category == "gstreamer":
            continue
            meson_cmd.append(f"-D{plugin}=enabled")
        else:
            meson_cmd.append(f"-D{category}:{plugin}=enabled")

print(" ".join(meson_cmd))

meson_cmd = [
    "meson",
    "setup",
    "builddir",
    "-Dauto_features=disabled",
    "-Dbase=enabled",
    "-Dgood=enabled",
    "-Dbad=enabled",
    "-Dugly=enabled",
    "-Dges=enabled",
    "-Dcoreelements=enabled",
    "-Dgst-plugins-base:app=enabled",
    "-Dgst-plugins-base:audioconvert=enabled",
    "-Dgst-plugins-base:audiomixer=enabled",
    "-Dgst-plugins-base:audiorate=enabled",
    "-Dgst-plugins-base:audioresample=enabled",
    "-Dgst-plugins-base:audiotestsrc=enabled",
    "-Dgst-plugins-base:compositor=enabled",
    "-Dgst-plugins-base:encoding=enabled",
    "-Dgst-plugins-base:ogg=enabled",
    "-Dgst-plugins-base:opengl=enabled",
    "-Dgst-plugins-base:opus=enabled",
    "-Dgst-plugins-base:pango=enabled",
    "-Dgst-plugins-base:playback=enabled",
    "-Dgst-plugins-base:subparse=enabled",
    "-Dgst-plugins-base:typefind=enabled",
    "-Dgst-plugins-base:videoconvertscale=enabled",
    "-Dgst-plugins-base:videorate=enabled",
    "-Dgst-plugins-base:videotestsrc=enabled",
    "-Dgst-plugins-base:volume=enabled",
    "-Dgst-plugins-base:vorbis=enabled",
    "-Dgst-plugins-good:audiofx=enabled",
    "-Dgst-plugins-good:audioparsers=enabled",
    "-Dgst-plugins-good:autodetect=enabled",
    "-Dgst-plugins-good:avi=enabled",
    "-Dgst-plugins-good:deinterlace=enabled",
    "-Dgst-plugins-good:flv=enabled",
    "-Dgst-plugins-good:imagefreeze=enabled",
    "-Dgst-plugins-good:isomp4=enabled",
    "-Dgst-plugins-good:jpeg=enabled",
    "-Dgst-plugins-good:lame=enabled",
    "-Dgst-plugins-good:matroska=enabled",
    "-Dgst-plugins-good:multipart=enabled",
    "-Dgst-plugins-good:osxaudio=enabled",
    "-Dgst-plugins-good:png=enabled",
    "-Dgst-plugins-good:rtp=enabled",
    "-Dgst-plugins-good:rtpmanager=enabled",
    "-Dgst-plugins-good:rtsp=enabled",
    "-Dgst-plugins-good:soup=enabled",
    "-Dgst-plugins-good:udp=enabled",
    "-Dgst-plugins-good:videocrop=enabled",
    "-Dgst-plugins-good:videofilter=enabled",
    "-Dgst-plugins-good:vpx=enabled",
    "-Dgst-plugins-bad:autoconvert=enabled",
    "-Dgst-plugins-bad:codectimestamper=enabled",
    "-Dgst-plugins-bad:decklink=enabled",
    "-Dgst-plugins-bad:jpegformat=enabled",
    "-Dgst-plugins-bad:mpegdemux=enabled",
    "-Dgst-plugins-bad:mpegtsdemux=enabled",
    "-Dgst-plugins-bad:openh264=enabled",
    "-Dgst-plugins-bad:opus=enabled",
    "-Dgst-plugins-bad:srtp=enabled",
    "-Dgst-plugins-bad:transcode=enabled",
    "-Dgst-plugins-bad:videoparsers=enabled",
    "-Dgst-plugins-bad:voaacenc=enabled",
    "-Dgst-plugins-bad:applemedia=enabled",
    "-Dgst-plugins-ugly:asf=enabled",
    "-Dgst-libav:libav=enabled",
    "-Dgst-editing-services:ges=enabled",
    "-Dgst-editing-services:nle=enabled",
]


print(" ".join(meson_cmd))
