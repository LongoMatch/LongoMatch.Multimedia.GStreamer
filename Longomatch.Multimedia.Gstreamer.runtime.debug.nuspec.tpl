<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2011/08/nuspec.xsd">
  <metadata>
    <id>LongoMatch.Multimedia.GStreamer.runtime.debug.{platform}</id>
    <version>{version}</version>
    <title>GStreamer native libraries debug symbols by Fluendo</title>
    <authors>Fluendo S.A.</authors>
    <owners>Fluendo S.A.</owners>
    <description>Unnoficial GStreamer native libraries and dependencies maintained by Fluendo.</description>
    <tags>native graphics linux windows</tags>
    <repository type="git" url="https://github.com/fluendo/fluendo-gstreamer-sharp.git" />
    <dependencies>
      <group targetFramework=".NETFramework4.7.2" />
      <group targetFramework=".NETCoreApp3.0" />
    </dependencies>
  </metadata>
   <files>
    <file src="nuget\runtimes\{platform}\native-debug\**" target="runtimes\{platform}\native" />
    <file src="nuget\_._" target="lib\net472" />
    <file src="nuget\_._" target="lib\netcoreapp3.0" />
    <file src="nuget\LongoMatch.Multimedia.GStreamer.runtime.debug.{platform}.targets" target="build\net472" />
  </files>
</package>