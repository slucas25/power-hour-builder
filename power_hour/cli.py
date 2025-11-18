from __future__ import annotations

import csv
import random
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import typer
from rich import box
from rich.console import Console
from rich.table import Table

app = typer.Typer(add_completion=False)
console = Console()


VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def _scan_dir(input_dir: Path, patterns: Sequence[str]) -> List[Path]:
    files: List[Path] = []
    for pat in patterns:
        files.extend(sorted(input_dir.rglob(pat)))
    # Fallback to all known extensions if patterns return nothing
    if not files:
        files = [p for p in input_dir.rglob("**/*") if p.suffix.lower() in VIDEO_EXTS]
    # Deduplicate
    seen = set()
    unique: List[Path] = []
    for p in files:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(rp)
    return unique


def _read_playlist(playlist: Path) -> List[Path]:
    out: List[Path] = []
    for line in playlist.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(Path(s).expanduser().resolve())
    return out


def _load_genre_map(csv_path: Optional[Path]) -> dict[Path, set[str]]:
    mapping: dict[Path, set[str]] = {}
    if not csv_path or not csv_path.exists():
        return mapping
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = Path(row.get("path", "")).expanduser().resolve()
            g = row.get("genre", "").strip()
            if not p or not g:
                continue
            genres = {x.strip().lower() for x in g.split("|") if x.strip()}
            mapping[p] = genres
    return mapping


def _filter_by_genre(files: List[Path], genre: Optional[str], genre_map: dict[Path, set[str]]) -> List[Path]:
    if not genre:
        return files
    g = genre.strip().lower()
    out: List[Path] = []
    for p in files:
        # CSV mapping first
        mapped = genre_map.get(p)
        if mapped and g in mapped:
            out.append(p)
            continue
        # Fallback: filename contains
        if g in p.name.lower() or g in str(p.parent).lower():
            out.append(p)
    return out


def _pick(files: List[Path], limit: int, shuffle: bool, seed: Optional[int]) -> List[Path]:
    items = list(files)
    if shuffle:
        rnd = random.Random(seed)
        rnd.shuffle(items)
    if limit > 0:
        items = items[:limit]
    return items


def _print_plan(files: Sequence[Path]):
    table = Table(title="Power Hour Plan", box=box.SIMPLE_HEAVY)
    table.add_column("#", justify="right")
    table.add_column("File")
    for i, p in enumerate(files, start=1):
        table.add_row(str(i), str(p))
    console.print(table)


@app.command()
def plan(
    input_dir: Optional[Path] = typer.Option(None, exists=True, dir_okay=True, file_okay=False, help="Directory containing videos"),
    pattern: str = typer.Option("*.mp4,*.mov", help="Comma-separated glob patterns (relative)"),
    playlist: Optional[Path] = typer.Option(None, exists=True, file_okay=True, dir_okay=False, help="Text file with one absolute path per line"),
    genre: Optional[str] = typer.Option(None, help="Simple genre filter: filename contains or CSV mapping"),
    genres_csv: Optional[Path] = typer.Option(None, exists=True, help="CSV with headers path,genre where genre may be | separated"),
    limit: int = typer.Option(60, min=1, help="Number of clips to include"),
    shuffle: bool = typer.Option(True, help="Shuffle candidates before picking"),
    seed: Optional[int] = typer.Option(None, help="Random seed for reproducibility"),
):
    """Dry-run: list selected files and their order."""

    files: List[Path] = []
    if playlist:
        files = _read_playlist(playlist)
    elif input_dir:
        pats = [p.strip() for p in pattern.split(",") if p.strip()]
        files = _scan_dir(input_dir, pats)
    else:
        raise typer.BadParameter("Provide either --playlist or --input-dir")

    genre_map = _load_genre_map(genres_csv)
    files = _filter_by_genre(files, genre, genre_map)
    if not files:
        console.print("[red]No files after filtering[/red]")
        raise typer.Exit(code=2)

    picked = _pick(files, limit=limit, shuffle=shuffle, seed=seed)
    _print_plan(picked)


@app.command()
def build(
    input_dir: Optional[Path] = typer.Option(None, exists=True, dir_okay=True, file_okay=False),
    pattern: str = typer.Option("*.mp4,*.mov"),
    playlist: Optional[Path] = typer.Option(None, exists=True, file_okay=True, dir_okay=False),
    output: Path = typer.Option(Path("./output/power_hour.mp4")),
    clip_seconds: float = typer.Option(60.0, min=1.0),
    crossfade: float = typer.Option(0.0, min=0.0, help="Overlap seconds between clips"),
    start_offset: float = typer.Option(0.0, min=0.0, help="Start offset into each clip"),
    target_width: Optional[int] = typer.Option(1280),
    target_height: Optional[int] = typer.Option(720),
    fps: Optional[int] = typer.Option(None),
    limit: int = typer.Option(60, min=1),
    shuffle: bool = typer.Option(True),
    seed: Optional[int] = typer.Option(None),
    genre: Optional[str] = typer.Option(None),
    genres_csv: Optional[Path] = typer.Option(None, exists=True),
):
    """Build the power hour video."""

    # Lazy import to avoid requiring moviepy when using YouTube HTML mode
    from .builder import BuildOptions, build_power_hour

    files: List[Path] = []
    if playlist:
        files = _read_playlist(playlist)
    elif input_dir:
        pats = [p.strip() for p in pattern.split(",") if p.strip()]
        files = _scan_dir(input_dir, pats)
    else:
        raise typer.BadParameter("Provide either --playlist or --input-dir")

    # Filter genre
    genre_map = _load_genre_map(genres_csv)
    files = _filter_by_genre(files, genre, genre_map)
    if not files:
        console.print("[red]No files after filtering[/red]")
        raise typer.Exit(code=2)

    picked = _pick(files, limit=limit, shuffle=shuffle, seed=seed)
    if len(picked) < limit:
        console.print(f"[yellow]Warning: only {len(picked)} files available (requested {limit})[/yellow]")

    # Options
    tsize: Optional[Tuple[int, int]]
    if target_width and target_height:
        tsize = (target_width, target_height)
    else:
        tsize = None
    opts = BuildOptions(
        clip_seconds=clip_seconds,
        crossfade=crossfade,
        start_offset=start_offset,
        target_size=tsize,
        fps=fps,
    )

    console.rule("Building power hour")
    console.print(
        {
            "clips": len(picked),
            "output": str(output),
            **{k: v for k, v in asdict(opts).items()},
        }
    )

    out = build_power_hour(picked, output, options=opts)
    console.print(f"[green]Done:[/green] {out}")


def _extract_video_id(url_or_id: str) -> str:
        s = url_or_id.strip()
        if not s:
                return s
        # Support plain IDs
        if "/" not in s and "?" not in s and "&" not in s and len(s) >= 8:
                return s
        # Common URL forms
        # https://www.youtube.com/watch?v=VIDEOID
        # https://youtu.be/VIDEOID
        import urllib.parse as _up

        try:
                u = _up.urlparse(s)
                if u.netloc.endswith("youtu.be"):
                        vid = u.path.strip("/")
                        return vid
                if u.netloc.endswith("youtube.com"):
                        qs = _up.parse_qs(u.query)
                        vid = qs.get("v", [""])[0]
                        if vid:
                                return vid
        except Exception:
                pass
        return s


def _read_youtube_list(path: Path) -> list[tuple[str, str]]:
    """Reads a text file of URLs/IDs. Returns list of (id, title). Title is empty string."""
    out: list[tuple[str, str]] = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append((_extract_video_id(s), ""))
    return out


def _parse_timecode(val: str) -> Optional[float]:
    """Parse seconds or mm:ss or hh:mm:ss into float seconds. Returns None if empty/invalid."""
    s = (val or "").strip()
    if not s:
        return None
    # Try plain seconds
    try:
        return float(s)
    except Exception:
        pass
    # Try hh:mm:ss or mm:ss
    parts = s.split(":")
    try:
        parts = [int(p) for p in parts]
    except Exception:
        return None
    if len(parts) == 2:
        m, sec = parts
        return float(m * 60 + sec)
    if len(parts) == 3:
        h, m, sec = parts
        return float(h * 3600 + m * 60 + sec)
    return None


def _read_youtube_csv(path: Path) -> list[dict]:
    """Reads a CSV and returns rows as dicts with keys: id, title, genre.

    Accepts flexible headers (case-insensitive):
      - id: id, video_id, youtube_id
      - url: url, link, youtube_url
      - title: title, name, track
      - genre: genre, genres, tag, tags
    If both id and url are present, prefer id.
    """
    def pick_key(d: dict, candidates: list[str]) -> str:
        for k in candidates:
            if k in d and d[k].strip():
                return d[k].strip()
        # fuzzy: find any key containing the word
        for key, val in d.items():
            lk = key.lower()
            if any(word in lk for word in candidates) and str(val).strip():
                return str(val).strip()
        return ""

    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # normalize keys to lowercase and strip values
            lower = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }
            vid = pick_key(lower, ["id", "video_id", "youtube_id"]) or ""
            url = pick_key(lower, ["url", "link", "youtube_url"]) or ""
            title = pick_key(lower, ["title", "name", "track"]) or ""
            genre = pick_key(lower, ["genre", "genres", "tag", "tags"]) or ""
            chorus_raw = pick_key(lower, ["chorus", "chorus_at", "chorus_time"]) or ""
            start_raw = pick_key(lower, ["start", "start_at", "offset", "clip_start", "start_seconds"]) or ""
            ref = vid or url
            if not ref:
                continue
            vid_id = _extract_video_id(ref)
            rows.append({
                "id": vid_id,
                "title": title,
                "genre": genre,
                "chorus": _parse_timecode(chorus_raw),
                "start": _parse_timecode(start_raw),
            })
    return rows


def _write_youtube_html(items: list[tuple[str, str, float]], out_path: Path, clip_seconds: float, title_reveal_delay: float = 0.0):
    # Minimal HTML using YouTube IFrame API; advances every clip_seconds
    video_ids = [vid for vid, _, _ in items]
    titles = [title for _, title, _ in items]
    starts = [start for _, _, start in items]
    ids_js = ",".join("'" + vid.replace("'", "") + "'" for vid in video_ids)
    titles_js = ",".join("'" + title.replace("'", "\\u0027") + "'" for title in titles)
    starts_js = ",".join(str(max(0.0, float(s))) for s in starts)
    html_template = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Power Hour (YouTube)</title>
    <style>
        body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; padding: 0; background: #111; color: #eee; }
        header { padding: 12px 16px; background: #181818; position: sticky; top: 0; z-index: 2; }
        .player-wrap { position: relative; width: 100%; max-width: 1280px; margin: 12px auto; }
        .player-wrap::before { content: ''; display: block; width: 100%; padding-top: calc(100% * 9 / 16); }
        #player { position: absolute; inset: 0; width: 100%; height: 100%; }
        .title-blocker { position: absolute; bottom: 0; left: 0; right: 0; height: 60px; background: linear-gradient(to top, rgba(17,17,17,0.95) 0%, rgba(17,17,17,0.8) 50%, transparent 100%); pointer-events: none; z-index: 1; }
        .overlay { position: absolute; left: 8px; top: 8px; background: rgba(0,0,0,0.6); color: #fff; padding: 6px 10px; border-radius: 6px; font-weight: 600; pointer-events: none; max-width: 95%; z-index: 2; }
        .overlay .title { display: block; font-weight: 500; opacity: 0.9; font-size: 14px; margin-top: 2px; }
        .overlay .title.hidden { display: none; }
        .wrap { max-width: 1280px; margin: 0 auto; padding: 8px 16px; }
        .btn { background: #2d6cdf; color: white; border: 0; padding: 8px 12px; border-radius: 6px; margin-right: 8px; cursor: pointer; }
        .btn:disabled { opacity: 0.6; cursor: default; }
        .meta { opacity: 0.8; font-size: 14px; }
    </style>
</head>
<body>
    <header>
        <div class=\"wrap\">
            <button id=\"playBtn\" class=\"btn\">Play</button>
            <button id=\"pauseBtn\" class=\"btn\">Pause</button>
            <button id=\"prevBtn\" class=\"btn\">Prev</button>
            <button id=\"nextBtn\" class=\"btn\">Next</button>
            <span class=\"meta\" id=\"status\"></span>
        </div>
    </header>
    <div class=\"wrap\">
        <div class=\"player-wrap\">
            <div id=\"player\"></div>
            <div class=\"title-blocker\"></div>
            <div class=\"overlay\" id=\"overlay\"></div>
        </div>
    </div>

    <script>
        const VIDEO_IDS = [__IDS__];
        const VIDEO_TITLES = [__TITLES__];
        const CLIP_SECONDS = __CLIP__;
        const VIDEO_STARTS = [__STARTS__];
        const TITLE_REVEAL_DELAY = __TITLE_DELAY__;
        let currentIndex = 0;
        let player = null;
        let timer = null;
        let titleTimer = null;
        let checkInterval = null;

        function updateStatus(showTitle = false) {
            const s = document.getElementById('status');
            const total = VIDEO_IDS.length;
            const cur = currentIndex + 1;
            const t = (VIDEO_TITLES[currentIndex] || '').trim();
            s.textContent = `Clip ${cur} / ${total} (each ${Math.round(CLIP_SECONDS)}s)${showTitle && t ? ' — ' + t : ''}`;
            const ov = document.getElementById('overlay');
            ov.innerHTML = `<div># ${cur} / ${total}</div>` + (t ? `<span class=\"title${showTitle ? '' : ' hidden'}\">${t}</span>` : '');
        }

        function onYouTubeIframeAPIReady() {
            player = new YT.Player('player', {
                videoId: VIDEO_IDS[currentIndex],
                playerVars: {
                    rel: 0,
                    modestbranding: 1,
                    controls: 1,
                    fs: 1
                },
                events: {
                    'onReady': onPlayerReady,
                    'onStateChange': onPlayerStateChange
                }
            });
        }

        function checkPlaybackTime() {
            if (!player || !player.getCurrentTime) return;
            try {
                const currentTime = player.getCurrentTime();
                const startTime = Number(VIDEO_STARTS[currentIndex] || 0);
                const elapsed = currentTime - startTime;
                
                // Check if we've played for the clip duration
                if (elapsed >= CLIP_SECONDS) {
                    nextClip();
                }
                
                // Show title after delay
                if (TITLE_REVEAL_DELAY > 0 && elapsed >= TITLE_REVEAL_DELAY && elapsed < TITLE_REVEAL_DELAY + 0.5) {
                    updateStatus(true);
                }
            } catch(e) {
                console.warn('Error checking playback time:', e);
            }
        }

        function playCurrent() {
            if (!player) return;
            try { player.stopVideo(); } catch(e) {}
            const start = Number(VIDEO_STARTS[currentIndex] || 0);
            player.loadVideoById({videoId: VIDEO_IDS[currentIndex], startSeconds: start});
            player.playVideo();
            clearTimers();
            const showTitleImmediately = TITLE_REVEAL_DELAY <= 0;
            updateStatus(showTitleImmediately);
            // Check playback time every 500ms
            checkInterval = setInterval(checkPlaybackTime, 500);
        }

        function clearTimers() {
            if (timer) { clearTimeout(timer); timer = null; }
            if (titleTimer) { clearTimeout(titleTimer); titleTimer = null; }
            if (checkInterval) { clearInterval(checkInterval); checkInterval = null; }
        }

        function nextClip() {
            clearTimers();
            currentIndex = (currentIndex + 1) % VIDEO_IDS.length;
            playCurrent();
        }

        function prevClip() {
            clearTimers();
            currentIndex = (currentIndex - 1 + VIDEO_IDS.length) % VIDEO_IDS.length;
            playCurrent();
        }

        function onPlayerReady() {
            updateStatus(TITLE_REVEAL_DELAY <= 0);
        }

        function onPlayerStateChange(ev) {
            // No-op; we use timer for advancing
        }

        document.getElementById('playBtn').addEventListener('click', () => {
            playCurrent();
        });
        document.getElementById('pauseBtn').addEventListener('click', () => {
            clearTimers();
            if (player) player.pauseVideo();
        });
        document.getElementById('nextBtn').addEventListener('click', nextClip);
        document.getElementById('prevBtn').addEventListener('click', prevClip);

        // Load the IFrame Player API
        const tag = document.createElement('script');
        tag.src = "https://www.youtube.com/iframe_api";
        document.body.appendChild(tag);
    </script>
</body>
</html>
"""
    html = (
        html_template
        .replace("__IDS__", ids_js)
        .replace("__TITLES__", titles_js)
        .replace("__CLIP__", f"{clip_seconds:.3f}")
        .replace("__STARTS__", starts_js)
        .replace("__TITLE_DELAY__", f"{title_reveal_delay:.3f}")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")


def _write_youtube_preview_html(rows: list[dict], out_path: Path):
    """Generate an interactive HTML to preview videos and mark chorus/start times.

    The HTML lets you play each item, jump around, set 'chorus' or 'start' to
    the current player time, and download an updated CSV containing columns:
    id,title,genre,chorus,start.
    """
    ids = [str(r.get("id", "")) for r in rows]
    titles = [str(r.get("title", "")) for r in rows]
    genres = [str(r.get("genre", "")) for r in rows]
    chorus = ["" if (r.get("chorus") is None or r.get("chorus") == "") else str(int(float(r.get("chorus")))) for r in rows]
    starts = ["" if (r.get("start") is None or r.get("start") == "") else str(int(float(r.get("start")))) for r in rows]

    ids_js = ",".join("'" + i.replace("'", "") + "'" for i in ids)
    titles_js = ",".join("'" + t.replace("'", "\\u0027") + "'" for t in titles)
    genres_js = ",".join("'" + g.replace("'", "\\u0027") + "'" for g in genres)
    chorus_js = ",".join((c if c != "" else "null") for c in chorus)
    starts_js = ",".join((s if s != "" else "null") for s in starts)

    html_template = """<!DOCTYPE html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>Preview YouTube CSV</title>
        <style>
            body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; padding: 0; background: #111; color: #eee; }}
            header {{ padding: 12px 16px; background: #181818; position: sticky; top: 0; z-index: 2; }}
            .wrap {{ max-width: 1280px; margin: 0 auto; padding: 8px 16px; }}
            .player-wrap {{ position: relative; width: 100%; max-width: 1280px; margin: 12px auto; }}
            .player-wrap::before {{ content: ''; display: block; width: 100%; padding-top: calc(100% * 9 / 16); }}
            #player {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
            .row {{ margin-top: 8px; }}
            .btn {{ background: #2d6cdf; color: white; border: 0; padding: 8px 12px; border-radius: 6px; margin-right: 8px; cursor: pointer; }}
            .btn.alt {{ background: #444; }}
            .status {{ opacity: 0.9; font-size: 14px; margin-left: 8px; }}
            .overlay {{ position: absolute; left: 8px; top: 8px; background: rgba(0,0,0,0.6); color: #fff; padding: 6px 10px; border-radius: 6px; font-weight: 600; pointer-events: none; max-width: 95%; }}
            .overlay .title {{ display: block; font-weight: 500; opacity: 0.9; font-size: 14px; margin-top: 2px; }}
            .meta-line {{ margin-top: 6px; font-size: 14px; opacity: 0.9; }}
            input[type=number] {{ width: 90px; }}
        </style>
    </head>
    <body>
        <header>
            <div class=\"wrap\">
                <button id=\"prevBtn\" class=\"btn\">Prev</button>
                <button id=\"nextBtn\" class=\"btn\">Next</button>
                <button id=\"playBtn\" class=\"btn\">Play</button>
                <button id=\"pauseBtn\" class=\"btn\">Pause</button>
                <button id=\"back5Btn\" class=\"btn alt\">-5s</button>
                <button id=\"fwd5Btn\" class=\"btn alt\">+5s</button>
                <span class=\"status\" id=\"status\"></span>
            </div>
        </header>
        <div class=\"wrap\">
            <div class=\"player-wrap\">
                <div id=\"player\"></div>
                <div class=\"overlay\" id=\"overlay\"></div>
            </div>
            <div class=\"row\">
                <button id=\"setChorusBtn\" class=\"btn\">Set Chorus @ Current</button>
                <button id=\"clearChorusBtn\" class=\"btn alt\">Clear Chorus</button>
                <button id=\"setStartBtn\" class=\"btn\">Set Start @ Current</button>
                <button id=\"clearStartBtn\" class=\"btn alt\">Clear Start</button>
                <button id=\"downloadBtn\" class=\"btn\">Download CSV</button>
                <span class=\"status\" id=\"info\"></span>
            </div>
        </div>

        <script>
            const VIDEO_IDS = [__IDS__];
            const VIDEO_TITLES = [__TITLES__];
            const VIDEO_GENRES = [__GENRES__];
            const VIDEO_CHORUS = [__CHORUS__];
            const VIDEO_STARTS = [__STARTS__];
            let currentIndex = 0;
            let player = null;
            let timer = null;
            let apiReady = false;
            let pendingStartAt = null;

            function fmt(t) {{
                if (t == null || isNaN(t)) return '';
                t = Math.floor(Number(t));
                const m = Math.floor(t/60), s = t%60;
                return `${m}:${s.toString().padStart(2,'0')}`;
            }}

            function getCur() {{ return Math.floor(player ? player.getCurrentTime() : 0); }}

            function updateStatus() {{
                const total = VIDEO_IDS.length;
                const cur = currentIndex + 1;
                const t = (VIDEO_TITLES[currentIndex] || '').trim();
                const curTime = fmt(getCur());
                const ch = fmt(VIDEO_CHORUS[currentIndex]);
                const st = fmt(VIDEO_STARTS[currentIndex]);
                document.getElementById('status').textContent = `Clip ${cur}/${total} ${t ? '— ' + t : ''}`;
                document.getElementById('overlay').innerHTML = `# ${cur}/${total}` + (t ? `<span class=\"title\">${t}</span>` : '') + `<div class=\"meta-line\">Now: ${curTime} — Chorus: ${ch || '—'} — Start: ${st || '—'}</div>`;
                document.getElementById('info').textContent = `Chorus=${ch || '—'} Start=${st || '—'}`;
            }}

            function onYouTubeIframeAPIReady() {{
                console.log('[preview] IFrame API ready');
                apiReady = true;
                if (!player && VIDEO_IDS.length > 0) {{
                    player = new YT.Player('player', {{
                        videoId: VIDEO_IDS[currentIndex],
                        playerVars: {{ rel: 0, modestbranding: 1, controls: 1, fs: 1 }},
                        events: {{
                            'onReady': () => {{
                                console.log('[preview] player ready');
                                onPlayerReady();
                                if (pendingStartAt != null) {{
                                    const start = Number(pendingStartAt) || 0;
                                    pendingStartAt = null;
                                    loadCurrent(start);
                                }}
                            }},
                            'onStateChange': onPlayerStateChange
                        }}
                    }});
                }}
            }}

            function loadCurrent(at=0) {{
                if (!player) return;
                try {{ player.stopVideo(); }} catch(e) {{}}
                player.loadVideoById({{videoId: VIDEO_IDS[currentIndex], startSeconds: Math.max(0, at)}});
                player.playVideo();
                updateStatus();
            }}

            function playCurrent() {{
                if (!apiReady) {{ console.log('[preview] API not ready yet'); updateStatus(); return; }}
                if (!player) {{
                    if (VIDEO_IDS.length === 0) {{ alert('No videos found from CSV'); return; }}
                    // Create player now and request load once ready
                    pendingStartAt = Number(VIDEO_STARTS[currentIndex] || 0) || 0;
                    player = new YT.Player('player', {{
                        videoId: VIDEO_IDS[currentIndex],
                        playerVars: {{ rel: 0, modestbranding: 1, controls: 1, fs: 1 }},
                        events: {{
                            'onReady': () => {{
                                onPlayerReady();
                                const start = pendingStartAt || 0; pendingStartAt = null;
                                loadCurrent(start);
                            }},
                            'onStateChange': onPlayerStateChange
                        }}
                    }});
                    return;
                }}
                const at = Number(VIDEO_STARTS[currentIndex] || 0) || 0;
                loadCurrent(at);
            }}
            function pauseCurrent() {{ if (!player) return; player.pauseVideo(); updateStatus(); }}

            function nextClip() {{ currentIndex = (currentIndex + 1) % VIDEO_IDS.length; loadCurrent(0); }}
            function prevClip() {{ currentIndex = (currentIndex - 1 + VIDEO_IDS.length) % VIDEO_IDS.length; loadCurrent(0); }}
            function back5() {{ if (!player) return; player.seekTo(Math.max(0, getCur() - 5), true); updateStatus(); }}
            function fwd5() {{ if (!player) return; player.seekTo(getCur() + 5, true); updateStatus(); }}

            function onPlayerReady() {{ updateStatus(); }}
            function onPlayerStateChange(ev) {{ /* no-op */ }}

            function setChorus() {{ VIDEO_CHORUS[currentIndex] = getCur(); updateStatus(); }}
            function clearChorus() {{ VIDEO_CHORUS[currentIndex] = null; updateStatus(); }}
            function setStart() {{ VIDEO_STARTS[currentIndex] = getCur(); updateStatus(); }}
            function clearStart() {{ VIDEO_STARTS[currentIndex] = null; updateStatus(); }}

            function csvEscape(v) {{
                if (v == null) return '';
                v = String(v);
                if (/[",\\n]/.test(v)) return '"' + v.replaceAll('"','""') + '"';
                return v;
            }}
            function downloadCSV() {
                const NL = '\\n';
                const header = ['id','title','genre','chorus','start'].join(',') + NL;
                const lines = VIDEO_IDS.map((id, i) => {
                    return [
                        id,
                        VIDEO_TITLES[i] || '',
                        VIDEO_GENRES[i] || '',
                        VIDEO_CHORUS[i] == null ? '' : Math.max(0, Math.floor(Number(VIDEO_CHORUS[i]))),
                        VIDEO_STARTS[i] == null ? '' : Math.max(0, Math.floor(Number(VIDEO_STARTS[i])))
                    ].map(csvEscape).join(',');
                }).join(NL);
                const blob = new Blob([header + lines], {type: 'text/csv;charset=utf-8;'});
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'yt_list_with_times.csv';
                document.body.appendChild(a);
                a.click();
                setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
            }

            document.getElementById('playBtn').addEventListener('click', playCurrent);
            document.getElementById('pauseBtn').addEventListener('click', pauseCurrent);
            document.getElementById('nextBtn').addEventListener('click', nextClip);
            document.getElementById('prevBtn').addEventListener('click', prevClip);
            document.getElementById('back5Btn').addEventListener('click', back5);
            document.getElementById('fwd5Btn').addEventListener('click', fwd5);
            document.getElementById('setChorusBtn').addEventListener('click', setChorus);
            document.getElementById('clearChorusBtn').addEventListener('click', clearChorus);
            document.getElementById('setStartBtn').addEventListener('click', setStart);
            document.getElementById('clearStartBtn').addEventListener('click', clearStart);
            document.getElementById('downloadBtn').addEventListener('click', downloadCSV);

            // Initialize UI state
            try {{ updateStatus(); }} catch (e) {{ console.warn('[preview] updateStatus failed', e); }}
            if (VIDEO_IDS.length === 0) {{
                document.getElementById('status').textContent = 'No videos found from CSV';
            }}
            // Load the IFrame API
            const tag = document.createElement('script');
            tag.src = "https://www.youtube.com/iframe_api";
            document.body.appendChild(tag);
        </script>
    </body>
    </html>
    """
    # Convert doubled braces to singles (leftover from earlier f-string escaping)
    html_template = html_template.replace("{{", "{").replace("}}", "}")
    html = (
        html_template
        .replace("__IDS__", ids_js)
        .replace("__TITLES__", titles_js)
        .replace("__GENRES__", genres_js)
        .replace("__CHORUS__", chorus_js)
        .replace("__STARTS__", starts_js)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")


def _filter_items_by_genre(items: list[dict], genre: Optional[str]) -> list[dict]:
    if not genre:
        return items
    g = genre.strip().lower()
    out: list[dict] = []
    for it in items:
        raw = (it.get("genre") or "").lower()
        # support pipe-separated genres
        parts = [x.strip() for x in raw.split("|") if x.strip()]
        if not parts and raw:
            parts = [raw]
        if any(g == p or g in p for p in parts):
            out.append(it)
    return out


def _pick_dict(items: list[dict], limit: int, shuffle: bool, seed: Optional[int]) -> list[dict]:
    lst = list(items)
    if shuffle:
        rnd = random.Random(seed)
        rnd.shuffle(lst)
    if limit > 0:
        lst = lst[:limit]
    return lst


def _pick_tuples(items: list[tuple[str, str]], limit: int, shuffle: bool, seed: Optional[int]) -> list[tuple[str, str]]:
    lst = list(items)
    if shuffle:
        rnd = random.Random(seed)
        rnd.shuffle(lst)
    if limit > 0:
        lst = lst[:limit]
    return lst


@app.command()
def build_youtube_html(
    urls_file: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="Text file with YouTube URLs or IDs (one per line)"),
    urls_csv: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="CSV with columns id or url, optional title, optional genre"),
    genre: Optional[str] = typer.Option(None, help="Filter CSV rows by genre (case-insensitive; supports pipe-separated genres)"),
    limit: int = typer.Option(60, min=1, help="Number of clips to include"),
    shuffle: bool = typer.Option(True, help="Shuffle before picking"),
    seed: Optional[int] = typer.Option(None, help="Random seed for reproducibility"),
    clip_seconds: float = typer.Option(60.0, min=5.0, help="Seconds to play from each video"),
    pre_chorus: float = typer.Option(10.0, min=0.0, help="If CSV has a chorus time, start this many seconds before it"),
    default_start: float = typer.Option(0.0, min=0.0, help="Start at this time if no chorus/start provided in CSV or text file"),
    title_reveal_delay: float = typer.Option(0.0, min=0.0, help="Seconds to wait before revealing song title (0 = show immediately, good for guessing games)"),
    output: Path = typer.Option(Path("./output/power_hour_youtube.html")),
):
    """Generate an HTML player that sequences YouTube videos for N seconds each (no downloading)."""
    final_items: list[tuple[str, str, float]] = []
    if urls_csv is not None:
        rows = _read_youtube_csv(urls_csv)
        total_read = len(rows)
        if genre:
            # If no row has any genre value, warn and skip filtering
            any_genre_val = any((r.get("genre") or "").strip() for r in rows)
            if not any_genre_val:
                console.print("[yellow]No 'genre' data found in CSV; ignoring --genre filter.[/yellow]")
            else:
                rows = _filter_items_by_genre(rows, genre)
        after_filter = len(rows)
        if after_filter == 0:
            # Collect unique genres present to help the user
            genres_present = sorted({ (r.get("genre") or "").strip().lower() for r in _read_youtube_csv(urls_csv) if (r.get("genre") or "").strip() })
            tip = f"Available genres in CSV: {', '.join(genres_present)}" if genres_present else "CSV contains no genre values."
            raise typer.BadParameter(
                f"No rows matched your filters. Read {total_read} rows; 0 after genre='{genre}'. {tip}"
            )
        rows = _pick_dict(rows, limit=limit, shuffle=shuffle, seed=seed)
        for r in rows:
            vid = r.get("id", "")
            if not vid:
                continue
            title = r.get("title", "")
            chorus = r.get("chorus")
            start_field = r.get("start")
            start = default_start
            if isinstance(chorus, (int, float)) and chorus is not None:
                start = max(0.0, float(chorus) - pre_chorus)
            elif isinstance(start_field, (int, float)) and start_field is not None:
                start = max(0.0, float(start_field))
            final_items.append((vid, title, start))
    elif urls_file is not None:
        tuples = _read_youtube_list(urls_file)
        if genre:
            console.print("[yellow]Note: --genre is ignored when using --urls-file; use --urls-csv for genre filtering.[/yellow]")
        tuples = _pick_tuples(tuples, limit=limit, shuffle=shuffle, seed=seed)
        final_items = [(vid, title, default_start) for (vid, title) in tuples if vid]
    else:
        raise typer.BadParameter("Provide either --urls-file or --urls-csv")

    if not final_items:
        raise typer.BadParameter("No valid YouTube IDs/URLs found after filtering/picking. Ensure CSV has 'id' or 'url' headers and rows are not empty.")
    _write_youtube_html(final_items, output, clip_seconds, title_reveal_delay)
    console.print(f"[green]HTML written:[/green] {output}")


@app.command()
def preview_youtube_csv(
    urls_csv: Path = typer.Option(..., exists=True, dir_okay=False, help="CSV with columns id or url, optional title, optional genre, optional chorus/start"),
    output: Path = typer.Option(Path("./output/preview_youtube.html")),
    open_file: bool = typer.Option(False, help="Open the generated HTML after writing (uses default browser)"),
):
    """Generate an interactive HTML to preview YouTube CSV and mark chorus/start times.

    Use the buttons to set 'chorus' or 'start' to the current player time, then
    click 'Download CSV' to save an updated file (id,title,genre,chorus,start).
    """
    rows = _read_youtube_csv(urls_csv)
    if not rows:
        raise typer.BadParameter("CSV seems empty or missing 'id'/'url' columns")
    _write_youtube_preview_html(rows, output)
    console.print(f"[green]Preview HTML written:[/green] {output}")
    console.print("Tip: serve over http for best results: `python3 -m http.server 8000` then open http://localhost:8000/" + str(output).lstrip("./"))
    if open_file:
        try:
            import webbrowser
            webbrowser.open(output.resolve().as_uri())
        except Exception:
            console.print("[yellow]Could not auto-open. Open the file manually or serve via http.[/yellow]")


def _main():  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    _main()
