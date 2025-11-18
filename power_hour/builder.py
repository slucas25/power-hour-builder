from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from moviepy.editor import (  # type: ignore
    CompositeVideoClip,
    VideoFileClip,
    concatenate_videoclips,
)


@dataclass
class BuildOptions:
    clip_seconds: float = 60.0
    crossfade: float = 0.0  # seconds of overlap between clips
    target_size: Optional[Tuple[int, int]] = (1280, 720)
    start_offset: float = 0.0  # seconds to skip at start of each clip
    audio_fade: float = 0.1  # to avoid popping at clip edges
    fps: Optional[int] = None  # infer from first clip if None


def _load_and_trim(
    path: Path, opts: BuildOptions, target_size: Optional[Tuple[int, int]]
) -> VideoFileClip:
    clip = VideoFileClip(str(path))
    duration = clip.duration or 0
    start = max(0.0, min(opts.start_offset, max(0.0, duration - 0.01)))
    end = min(duration, start + opts.clip_seconds)
    if end <= start:
        # Fallback: use as much as available
        end = min(duration, start + max(0.5, opts.clip_seconds))
    sub = clip.subclip(start, end)

    if target_size is not None:
        sw, sh = target_size
        sub = sub.resize(newsize=(sw, sh))

    # Small audio fades to avoid clicks
    if sub.audio is not None and opts.audio_fade > 0:
        sub = sub.audio_fadein(opts.audio_fade).audio_fadeout(opts.audio_fade)

    return sub


def build_power_hour(
    input_files: Sequence[Path | str],
    output_path: Path | str,
    options: Optional[BuildOptions] = None,
) -> Path:
    """
    Build the power hour video from the provided input files.

    - input_files: list of file paths to videos (order matters)
    - output_path: resulting mp4 file path
    - options: BuildOptions for clip length, crossfade, etc.
    """
    if options is None:
        options = BuildOptions()

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    paths = [Path(p) for p in input_files]
    if len(paths) == 0:
        raise ValueError("No input files provided")

    # Determine target size from first clip if not provided
    target_size = options.target_size
    if target_size is None:
        with VideoFileClip(str(paths[0])) as first:
            target_size = (first.w, first.h)

    # Load and trim all clips
    clips: List[VideoFileClip] = []
    try:
        for p in paths:
            clips.append(_load_and_trim(p, options, target_size))

        if options.crossfade and options.crossfade > 0:
            # Compose on a timeline with overlaps
            timeline_clips = []
            start = 0.0
            step = max(0.0, options.clip_seconds - options.crossfade)
            for idx, c in enumerate(clips):
                cc = c
                # Apply visual crossfade-in to current clip
                if idx > 0:
                    cc = cc.crossfadein(options.crossfade)
                timeline_clips.append(cc.set_start(start))
                start += step

            duration = start + (clips[-1].duration or 0)
            final = CompositeVideoClip(timeline_clips, size=target_size)
            final = final.set_duration(duration)
        else:
            # Simple cut concatenation
            final = concatenate_videoclips(clips, method="compose")

        # Set FPS if requested
        if options.fps is not None:
            final = final.set_fps(options.fps)

        # Write the video
        final.write_videofile(
            str(out_path),
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(out_path.with_suffix(".temp-audio.m4a")),
            remove_temp=True,
            threads=4,
            preset="medium",
            ffmpeg_params=["-movflags", "+faststart"],
        )
    finally:
        for c in clips:
            try:
                c.close()
            except Exception:
                pass

    return out_path
