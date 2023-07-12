<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2011/08/nuspec.xsd">
  <metadata>
    <id>LongoMatch.Multimedia.GStreamer.runtime.{platform}</id>
    <version>{version}</version>
    <title>GStreamer native libraries by Fluendo</title>
    <authors>Fluendo S.A.</authors>
    <owners>Fluendo S.A.</owners>
    <description>Unnoficial GStreamer native libraries and dependencies maintained by Fluendo.</description>
    <tags>native graphics linux windows</tags>
    <repository type="git" url="https://github.com/fluendo/fluendo-gstreamer-sharp.git" />
    <dependencies>
      <group targetFramework=".NETFramework4.7.2" />
      <group targetFramework=".NETCoreApp3.0" />
    </dependencies>
    <contentFiles>
      <files include="**\lib\**" buildAction="None" copyToOutput="true"/>
      <files include="**\libexec\**" buildAction="None" copyToOutput="true"/>
    </contentFiles>
  </metadata>
   <files>
    <file src="nuget\runtimes\{platform}\native\*" target="runtimes\{platform}\native" />
    <file src="nuget\runtimes\{platform}\native\lib\**" target="contentFiles\any\netcoreapp3.0\lib\" />
    <file src="nuget\runtimes\{platform}\native\libexec\**" target="contentFiles\any\netcoreapp3.0\libexec\" />
    <file src="nuget\_._" target="lib\net472" />
    <file src="nuget\_._" target="lib\netcoreapp3.0" />
    <file src="nuget\LongoMatch.Multimedia.GStreamer.runtime.{platform}.targets" target="build\net472" />
  </files>
</package>