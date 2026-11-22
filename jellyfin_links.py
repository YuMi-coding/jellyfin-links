#!/usr/bin/env python3
"""Create a Jellyfin season from a flat directory of completed anime episodes."""

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".m4v", ".avi", ".webm", ".ts"}
EPISODE_PATTERN = r"(?i)(?:^|\s)-\s*(?P<episode>[0-9]{1,4})(?:v[0-9]+)?(?=\s|\[|\(|$)"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="directory of completed episodes for one season")
    parser.add_argument("library", type=Path, help="separate directory scanned by Jellyfin")
    parser.add_argument("--title", required=True, help="series title used in Jellyfin")
    parser.add_argument("--season", required=True, type=int, help="Jellyfin season number")
    parser.add_argument("--episode-offset", type=int, default=0, help="add to the parsed episode number")
    parser.add_argument("--pattern", default=EPISODE_PATTERN, help="regex on filename stem with a named episode group")
    parser.add_argument("--apply", action="store_true", help="create links after validating the plan")
    args = parser.parse_args()

    title = args.title.strip()
    if title in {"", ".", ".."} or "/" in title or "\x00" in title or args.season < 0:
        parser.error("provide a valid title and a nonnegative season number")
    try:
        pattern = re.compile(args.pattern)
    except re.error as exc:
        parser.error(str(exc))
    if "episode" not in pattern.groupindex:
        parser.error("--pattern must contain a named episode group")

    try:
        return generate(args, title, pattern)
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


def generate(args, title, pattern):
    source = args.source.resolve(strict=True)
    library = args.library.resolve()
    if source == library or source in library.parents or library in source.parents:
        raise RuntimeError("source and library must be separate directory trees")

    show_directory = library / title
    season_directory = show_directory / f"Season {args.season:02d}"
    for directory in (show_directory, season_directory):
        if directory.is_symlink():
            raise RuntimeError(f"refusing symlinked output directory: {directory}")
        if directory.exists() and not directory.is_dir():
            raise RuntimeError(f"output directory is occupied: {directory}")

    episodes = defaultdict(list)
    for video in sorted(source.iterdir()):
        if video.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if video.is_symlink() or not video.is_file():
            print(f"SKIP {video.name!r}: expected a regular video file")
            continue
        matches = [match.group("episode") for match in pattern.finditer(video.stem)]
        if len(matches) != 1 or not re.fullmatch(r"[0-9]{1,6}", matches[0] or ""):
            print(f"SKIP {video.name!r}: no unambiguous episode number")
            continue
        episode = int(matches[0]) + args.episode_offset
        if episode < 1:
            print(f"SKIP {video.name!r}: episode number is below 1 after applying offset")
            continue
        episodes[episode].append(video)

    pending = []
    conflicts = False
    for episode, videos in sorted(episodes.items()):
        episode_id = f"S{args.season:02d}E{episode:02d}"
        if len(videos) > 1:
            names = ", ".join(repr(video.name) for video in videos)
            print(f"CONFLICT {episode_id}: {names}", file=sys.stderr)
            conflicts = True
            continue
        video = videos[0]
        link = season_directory / f"{title} - {episode_id}{video.suffix.lower()}"
        target = os.path.relpath(video, start=season_directory)
        if link.is_symlink() and os.readlink(link) == target:
            print(f"KEEP {link}")
        elif link.exists() or link.is_symlink():
            print(f"CONFLICT {link}: destination already exists", file=sys.stderr)
            conflicts = True
        else:
            print(f"LINK {link} -> {target}")
            pending.append((link, target))

    if conflicts:
        raise RuntimeError("resolve the reported conflicts before applying the plan")
    if not episodes:
        raise RuntimeError("no episodes were matched")
    if args.apply and pending:
        season_directory.mkdir(parents=True, exist_ok=True)
        for link, target in pending:
            try:
                link.symlink_to(target)
            except FileExistsError:
                if not link.is_symlink() or os.readlink(link) != target:
                    raise
    print(f"{len(pending)} links {'created or confirmed' if args.apply else 'planned (preview only)'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
