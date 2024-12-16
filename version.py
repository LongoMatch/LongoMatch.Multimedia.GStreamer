#!/usr/bin/env python3
from functools import total_ordering
import subprocess
import sys
import argparse


@total_ordering
class Version:
    def __init__(self, major: int, minor: int, patch: int, build: int = 0, hash=None):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.build = build
        self.hash = hash

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}.{self.build}"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Version):
            return NotImplemented
        return (
            self.major == value.major
            and self.minor == value.minor
            and self.patch == value.patch
            and self.build == value.build
        )

    def __lt__(self, value: object) -> bool:
        if not isinstance(value, Version):
            return NotImplemented
        if self.major < value.major:
            return True
        if self.major > value.major:
            return False
        if self.minor < value.minor:
            return True
        if self.minor > value.minor:
            return False
        if self.patch < value.patch:
            return True
        if self.patch > value.patch:
            return False
        if self.build < value.build:
            return True
        if self.build > value.build:
            return False
        return False

    @staticmethod
    def parse(version_str: str, hash: str = None):
        parts = version_str.split(".")
        if len(parts) < 2:
            raise ValueError(f"Invalid version string '{version_str}'")

        major = int(parts[0])
        minor = int(parts[1])
        if len(parts) == 3:
            patch = int(parts[2])
        else:
            patch = 0
        build = 0
        if len(parts) > 3:
            build = int(parts[3])

        return Version(major, minor, patch, build, hash)


def _get_version_from_file(file_path: str) -> Version:
    with open(file_path, "r") as file:
        return Version.parse(file.readline().strip())


def _get_commit_list(git_dir, vcommit, head_commit):
    try:
        commit_list = subprocess.check_output(
            ["git", "rev-list", f"{vcommit}..{head_commit}"],
            stderr=subprocess.DEVNULL,
            cwd=git_dir,
        )
        return commit_list.decode("utf-8").split()
    except subprocess.CalledProcessError:
        print("WARNING: git rev-list failed", file=sys.stderr)
        return []


def _get_tagged_versions(git_dir) -> list[Version]:
    try:
        versions_tags = (
            subprocess.check_output(
                [
                    "git",
                    "describe",
                    "--tags",
                    "--abbrev=0",
                    "--match=[0-9]*.[0-9]*.[0-9]*",
                ],
                stderr=subprocess.DEVNULL,
                cwd=git_dir,
            )
            .decode("utf-8")
            .split()
        )
        return sorted([Version.parse(v, v) for v in versions_tags])
    except subprocess.CalledProcessError:
        print("WARNING: failed to list tags", file=sys.stderr)
        return []


def _get_num_commits(commit_list):
    return len(commit_list)


def _get_current_commit_hash(git_dir):
    return (
        subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"], cwd=git_dir)
        .decode("utf-8")
        .strip()
    )


def get_version(git_dir=".", version_file="version.txt", current_commit_hash=None):
    version = _get_version_from_file(version_file)
    current_commit_hash = current_commit_hash or _get_current_commit_hash(git_dir)
    tagged_versions = _get_tagged_versions(git_dir)

    last_tagged_version = tagged_versions[-1] if tagged_versions else Version(0, 0, 0)
    if version > last_tagged_version:
        vcommit = (
            subprocess.check_output(
                ["git", "log", "-n", "1", "--pretty=format:%H", "--", version_file],
                cwd=git_dir,
            )
            .decode("utf-8")
            .strip()
        )
    else:
        # Increase the patch version +1 of the last tagged version
        version = Version(
            last_tagged_version.major,
            last_tagged_version.minor,
            last_tagged_version.patch + 1,
        )
        vcommit = last_tagged_version.hash

    commit_list = _get_commit_list(git_dir, vcommit, current_commit_hash)
    version.build = _get_num_commits(commit_list)
    version.hash = current_commit_hash

    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate version information.")
    parser.add_argument(
        "version_file",
        type=str,
        default="version.txt",
        nargs="?",
        help="Path to the version file",
    )
    parser.add_argument(
        "--version_type",
        type=str,
        choices=["short", "long"],
        default="short",
        nargs="?",
        help="Type of version output (short or long, default is short)",
    )
    parser.add_argument(
        "--commit_hash",
        type=str,
        default=None,
        nargs="?",
        help="Commit to calculate the build number from (default is last commit)",
    )

    args = parser.parse_args()
    version = get_version(".", args.version_file, args.commit_hash)

    if args.version_type == "short":
        final_version = f"{version}"
    else:
        final_version = f"{version}-{version.hash}"

    # Omit the trailing newline, so we can use the result directly.
    print(final_version, end="")
