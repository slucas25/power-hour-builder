# Power Hour Creator

Create a configurable "power hour" video: 60 music videos, each clipped to N seconds (default 60s), stitched into a single MP4. You bring the videos you have the rights to use; this tool assembles them locally.

## Project Structure

```
power-hour/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   └── playlist-idea.md      # Template for playlist requests
│   └── workflows/
│       ├── playlist-automation.yml # Automated playlist generation
│       ├── release.yml             # Automated releases
│       └── tests.yml               # CI testing
├── input/              # CSV playlists for YouTube-based power hours
│   ├── 70s_light_rock_list.csv
│   ├── 70s_metal_list.csv
│   ├── 90s_grunge_list.csv
│   ├── 90s_grunge_deep_cuts.csv
│   ├── americana_list.csv
│   └── one_hit_wonders_list.csv
├── output/             # Generated HTML files
│   ├── 70s_light_rock_power_hour.html
│   ├── 70s_metal_power_hour.html
│   └── ...
├── power_hour/         # Python package
│   ├── builder.py
│   └── cli.py
├── scripts/
│   └── generate_playlist.py       # Playlist generation helper
├── tests/
│   └── test_basics.py             # Unit and regression tests
└── README.md
```

## Features

- Build a 60-track power hour from local video files (mp4/mov/mkv/webm)
- Clip length configurable (default 60 seconds)
- Optional crossfade between clips
- Normalize resolution to a target size
- Flexible selection:
  - Provide a playlist file (one path per line)
  - Point at a folder and auto-pick files (with glob patterns and shuffle)
  - Filter by a simple genre label (via filename contains or optional CSV mapping)
- Dry-run planning and validation before rendering

> Legal note: This tool does not fetch or download copyrighted content. Only use videos you created or have licenses/rights to use.

## Prerequisites

- macOS (tested), Python 3.9+
- FFmpeg installed on your system and available on PATH
  - On macOS (Homebrew): `brew install ffmpeg`

## Quick start

1) Create and activate a virtualenv (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2) Install dependencies

```bash
pip install -r requirements.txt
```

3) Plan your power hour (dry-run)

```bash
python -m power_hour.cli plan \
  --input-dir "/path/to/your/music_videos" \
  --pattern "*.mp4,*.mov" \
  --limit 60 \
  --clip-seconds 60
```

4) Build it

```bash
python -m power_hour.cli build \
  --input-dir "/path/to/your/music_videos" \
  --pattern "*.mp4,*.mov" \
  --limit 60 \
  --clip-seconds 60 \
  --crossfade 0.5 \
  --target-width 1280 --target-height 720 \
  --output "./output/power_hour.mp4"
```

### Using a playlist file

Create a text file with one absolute path per line:

```text
/Volumes/Media/vids/Artist1 - TrackA.mp4
/Volumes/Media/vids/Artist2 - TrackB.mov
...
```

Then run:

```bash
python -m power_hour.cli build \
  --playlist ./playlist.txt \
  --clip-seconds 60 \
  --output ./output/power_hour.mp4
```

### Genre filtering (simple)

- By filename: `--genre pop` will include files whose path contains "pop" (case-insensitive).
- By CSV mapping: Provide `--genres-csv mapping.csv` where the CSV has headers `path,genre`. Multiple genres can be `|`-separated.

```bash
python -m power_hour.cli plan \
  --input-dir ./videos \
  --genre pop \
  --genres-csv ./genres.csv
```

## YouTube (no-download) mode

If you'd rather not download anything and want to play clips directly from YouTube, generate a local HTML player that uses the official YouTube IFrame API and advances every N seconds. You supply a text file of YouTube URLs or IDs (one per line):

```text
https://www.youtube.com/watch?v=VIDEOID1
https://youtu.be/VIDEOID2
VIDEOID3
```

Then run:

```bash
python -m power_hour.cli build-youtube-html \
  --urls-file ./input/yt_list.txt \
  --clip-seconds 60 \
  --output ./output/power_hour_youtube.html
```

### Viewing the Generated HTML

**Important:** Due to browser security policies, YouTube embeds won't work when opening HTML files directly (`file://` protocol). You must serve them through a web server:

**Quick Local Server:**
```bash
# From the project root
cd output
python3 -m http.server 8000
```

Then open your browser to: `http://localhost:8000/power_hour_youtube.html`

**Or use the convenience script:**
```bash
./serve.sh 70s_light_rock_power_hour.html
```

The HTML will play each video for the requested clip length and then advance to the next, without downloading the content.

Notes:
- This uses the YouTube IFrame Player API. Review and follow YouTube's API Terms of Service and branding/controls policies.
- Embedding works as long as videos allow embedding; private/blocked videos may not play.
- This is separate from the local video builder, which requires local files you have rights to use.

**Finding videos that embed reliably:**
- **DO NOT use `&start_radio=1` parameter** - this creates a radio playlist that plays random songs, not the specific song you want
- Use direct video URLs only: `https://www.youtube.com/watch?v=VIDEO_ID`
- Videos from "Topic" channels (auto-generated by YouTube) typically have better embed permissions
- Official artist channels are more reliable than user uploads
- Regional restrictions and copyright blocks can prevent playback - test videos in your region before building a full power hour

**REQUIRED: Verifying song/artist matches when creating new lists:**
When creating a new power hour list, you MUST verify each video URL matches the intended artist and song:

1. Search for the video ID:
```bash
curl -s "https://www.youtube.com/results?search_query=Artist+Song+Name" | grep -o '"videoId":"[^"]*"' | head -1 | cut -d'"' -f4
```

2. Verify the video matches:
```bash
curl -s "https://www.youtube.com/watch?v=VIDEO_ID" | grep -o '<title>[^<]*</title>'
```

3. Only add verified URLs to the CSV - the YouTube search results may return wrong videos, so always check the actual video title.

**Avoiding live/concert versions:**
Studio versions are usually preferred over live performances. Check for these indicators in video titles:
- ❌ "Live", "Concert", "Tour", "Performance", "Festival"
- ✅ "Official Audio", "Official Video", "Official Music Video", "Audio", "Studio"

To prefer studio versions, add keywords to your search:
```bash
# Prefer official studio versions
curl -s "https://www.youtube.com/results?search_query=Artist+Song+Name+official+audio" | grep -o '"videoId":"[^"]*"' | head -1
```

**Automated verification script template:**
Save this as a script to build and verify a complete playlist:
```bash
#!/bin/bash
declare -a songs=(
  "Artist 1 - Song Title 1"
  "Artist 2 - Song Title 2"
  # ... add all songs
)

echo "id,title,start" > input/playlist.csv

for song in "${songs[@]}"; do
  search_query=$(echo "$song" | sed 's/ /+/g')
  echo "Searching: $song"
  
  # Prefer official audio/video versions
  video_id=$(curl -s "https://www.youtube.com/results?search_query=${search_query}+official" | grep -o '"videoId":"[^"]*"' | head -1 | cut -d'"' -f4)
  
  if [ -n "$video_id" ]; then
    actual_title=$(curl -s "https://www.youtube.com/watch?v=$video_id" | grep -o '<title>[^<]*</title>' | sed 's/<title>//;s/<\/title>//')
    echo "  Found: $actual_title"
    
    # Check for live version indicators
    if echo "$actual_title" | grep -iE "(live|concert|tour|performance|festival)" > /dev/null; then
      echo "  ⚠️  WARNING: This may be a LIVE version"
    fi
    
    echo "https://www.youtube.com/watch?v=$video_id,$song,15" >> input/playlist.csv
  else
    echo "  ERROR: No video found"
  fi
  
  sleep 0.5
done
```

Review the output and manually fix any mismatched videos before building the HTML.

### CSV with titles

You can provide a CSV instead of a text file to show clip titles in the UI overlay and status. The CSV should have a header row and include either `id` or `url`, and an optional `title`:

```csv
id,title
VIDEOID1,Artist – Track 1
VIDEOID2,Artist – Track 2
```

Or:

```csv
url,title
https://youtu.be/VIDEOID1,Artist – Track 1
https://www.youtube.com/watch?v=VIDEOID2,Artist – Track 2
```

Run:

```bash
python -m power_hour.cli build-youtube-html \
  --urls-csv ./input/yt_list.csv \
  --genre pop \
  --limit 60 \
  --shuffle \
  --clip-seconds 60 \
  --output ./output/power_hour_youtube.html
```

CSV may include a `genre` column (optionally pipe-separated like `pop|dance`). Use `--genre` to filter rows. You can also combine `--limit`, `--shuffle`, and `--seed` for selection control.

## Automated Playlist Generation

This project includes automation for community-driven playlist creation:

### For Users: Requesting a Playlist

1. Go to [Issues](../../issues) and click "New Issue"
2. Select "Power Hour Playlist Idea" template
3. Fill in:
   - Theme (e.g., "90s Britpop", "Motown Classics")
   - Description of the vibe
   - 5-10 sample songs/artists
   - Target era/genre
4. Submit the issue

### What Happens Next

When you label an issue with `playlist-idea`:
1. GitHub Actions triggers automatically
2. A coding agent is notified to create the playlist
3. The agent will:
   - Research 60 songs matching your theme
   - Find verified YouTube videos (studio versions preferred)
   - Create the CSV file in `input/`
   - Generate the HTML player in `output/`
   - Run validation tests
   - Open a PR for review
4. Once the PR is merged, your issue is automatically closed
5. Your power hour is ready to play!

### For Maintainers: Manual Playlist Generation

If you prefer to generate playlists manually:

```bash
# Parse an issue and get agent instructions
python scripts/generate_playlist.py '{"title": "80s Synth Pop", "body": "...", "number": 42}'

# Or trigger the coding agent manually with:
# @github-copilot create a power hour for [theme]
```

The workflow creates structured prompts for the coding agent with all verification steps included.

### Updating the Landing Page

After adding new playlists, regenerate the `index.html` landing page:

```bash
python3 scripts/generate_index.py
```

This automatically:
- Scans `output/` for power hour HTML files
- Generates playlist cards with titles and descriptions
- Updates the landing page

**To add metadata for a new playlist**, edit `scripts/generate_index.py` and add an entry to the `PLAYLIST_INFO` dictionary:

```python
"your_playlist_name_power_hour": (
    "Display Title",
    "Description of the playlist vibe and artists"
),
```

## Notes and tips

- Performance: Rendering 60 clips can take time. Prefer local SSD storage and avoid super-high resolutions. 1280x720 (HD) is a good balance.
- Crossfades are optional and increase render time/memory. Start with `--crossfade 0` if you hit memory limits.
- Audio levels vary across sources; this simple tool doesn’t loudness-normalize. For consistent volume, consider pre-processing your videos or extend the pipeline.
- Text overlays (track numbers, timers) are intentionally omitted to avoid external dependencies (ImageMagick). If you want overlays, we can add an optional layer.

## Disclaimer

This tool is provided for assembling or sequencing videos you’re legally permitted to use. It does not download, rip, or otherwise obtain copyrighted material. The YouTube HTML mode plays via the YouTube IFrame API without downloading.

## License

MIT