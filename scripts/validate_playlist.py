#!/usr/bin/env python3
"""
Validate a YouTube playlist CSV by checking:
1. Video availability (embeddability)
2. Title accuracy
3. Potential issues (album art, topic channels, etc.)
"""

import csv
import json
import sys
import time
import urllib.request
from pathlib import Path


def extract_video_id(url_or_id: str) -> str:
    """Extract YouTube video ID from URL or return ID as-is."""
    s = url_or_id.strip()
    if not s:
        return s
    # Support plain IDs
    if "/" not in s and "?" not in s and "&" not in s and len(s) >= 8:
        return s
    # Common URL forms
    import urllib.parse as up
    try:
        u = up.urlparse(s)
        if u.netloc.endswith("youtu.be"):
            return u.path.strip("/")
        if u.netloc.endswith("youtube.com"):
            qs = up.parse_qs(u.query)
            vid = qs.get("v", [""])[0]
            if vid:
                return vid
    except Exception:
        pass
    return s


def check_video(video_id: str, expected_title: str) -> dict:
    """Check if video is embeddable and get its actual title."""
    result = {
        "video_id": video_id,
        "expected_title": expected_title,
        "embeddable": False,
        "actual_title": None,
        "error": None,
        "warnings": [],
        "severity": "ok"  # ok, warning, error
    }
    
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        with urllib.request.urlopen(oembed_url) as response:
            data = json.loads(response.read())
            actual_title = data.get("title", "")
            author = data.get("author_name", "")
            
            result["embeddable"] = True
            result["actual_title"] = actual_title
            result["author"] = author
            
            # Check for potential issues
            actual_lower = actual_title.lower()
            expected_lower = expected_title.lower()
            
            # Extract key parts from expected title (artist and song)
            expected_parts = expected_lower.replace(" - ", " ").split()
            actual_parts = actual_lower.replace(" - ", " ").split()
            
            # Check if artist name appears in actual title
            if expected_parts:
                artist_in_title = any(part in actual_lower for part in expected_parts[:2])
                if not artist_in_title:
                    result["warnings"].append("❌ WRONG ARTIST - completely different video!")
                    result["severity"] = "error"
            
            # Check if titles match reasonably (at least 2 words in common)
            expected_words = set(w for w in expected_parts if len(w) > 2)
            actual_words = set(w for w in actual_parts if len(w) > 2)
            common_words = expected_words & actual_words
            
            if len(common_words) < 2 and result["severity"] != "error":
                result["warnings"].append("⚠️  Title mismatch - may be wrong video")
                result["severity"] = "warning"
            
            # Check for album art indicators
            if any(keyword in actual_lower for keyword in ["audio", "lyric", "lyrics", "topic"]):
                result["warnings"].append("🎵 Audio-only/lyrics (not music video)")
                if result["severity"] == "ok":
                    result["severity"] = "warning"
            
            # Check for full album uploads
            if "full album" in actual_lower or "full ep" in actual_lower:
                result["warnings"].append("💿 Full album upload (not single video)")
                if result["severity"] == "ok":
                    result["severity"] = "warning"
            
            # Check for live/cover indicators
            if "cover" in actual_lower and "cover" not in expected_lower:
                result["warnings"].append("🎤 Cover version (not original)")
                if result["severity"] == "ok":
                    result["severity"] = "warning"
            
            # Topic channels are often just album art
            if "- topic" in author.lower():
                result["warnings"].append("📀 Topic channel (likely album art only)")
                if result["severity"] == "ok":
                    result["severity"] = "warning"
            
            # Check for completely unrelated content
            unrelated_keywords = ["tutorial", "how to", "reaction", "review", "scene", "clip", "trailer", "funny", "compilation"]
            if any(keyword in actual_lower for keyword in unrelated_keywords):
                result["warnings"].append("❌ UNRELATED - Not a music video!")
                result["severity"] = "error"
            
    except urllib.error.HTTPError as e:
        result["error"] = f"HTTP {e.code}"
        result["severity"] = "error"
        if e.code == 401:
            result["error"] += " (not embeddable)"
        elif e.code == 404:
            result["error"] += " (video not found/removed)"
        elif e.code == 403:
            result["error"] += " (access forbidden)"
    except Exception as e:
        result["error"] = str(e)
        result["severity"] = "error"
    
    return result


def validate_csv(csv_path: Path, max_videos: int = None):
    """Validate all videos in a CSV file."""
    if not csv_path.exists():
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    if max_videos:
        rows = rows[:max_videos]
    
    # Check for duplicate video IDs
    video_id_map = {}
    duplicates = []
    for idx, row in enumerate(rows, 1):
        url = row.get('id', '')
        title = row.get('title', '')
        if url:
            video_id = extract_video_id(url)
            if video_id in video_id_map:
                duplicates.append((idx, title, video_id, video_id_map[video_id]))
            else:
                video_id_map[video_id] = (idx, title)
    
    # Check for genre mismatches (basic keyword detection)
    genre_keywords = {
        'metal': ['metal', 'metallica', 'slipknot', 'korn', 'disturbed', 'pantera', 'slayer', 'megadeth', 
                  'sepultura', 'lamb of god', 'killswitch', 'trivium', 'avenged', 'bullet', 'hatebreed',
                  'mudvayne', 'godsmack', 'tool', 'deftones', 'system of a down', 'rammstein'],
        'pop-punk': ['blink-182', 'sum 41', 'green day', 'good charlotte', 'simple plan', 'yellowcard'],
        'rock': ['nickelback', 'creed', 'three days grace', 'breaking benjamin', 'chevelle', 'shinedown'],
    }
    
    potential_genre_mismatches = []
    playlist_name_lower = csv_path.name.lower()
    expected_genre = None
    for genre, keywords in genre_keywords.items():
        if genre in playlist_name_lower:
            expected_genre = genre
            break
    
    if expected_genre:
        for idx, row in enumerate(rows, 1):
            title = row.get('title', '').lower()
            artist = title.split(' - ')[0] if ' - ' in title else title
            
            # Check if artist matches expected genre
            matches_genre = any(keyword in artist for keyword in genre_keywords.get(expected_genre, []))
            
            # Check if it matches a different genre
            for genre, keywords in genre_keywords.items():
                if genre != expected_genre and any(keyword in artist for keyword in keywords):
                    potential_genre_mismatches.append((idx, row.get('title', ''), genre, expected_genre))
                    break
    
    if duplicates:
        print(f"⚠️  Found {len(duplicates)} duplicate video ID(s):\n")
        for idx, title, vid_id, (orig_idx, orig_title) in duplicates:
            print(f"  Track {idx}: {title}")
            print(f"    → Same video ID as Track {orig_idx}: {orig_title}")
            print(f"    → ID: {vid_id}\n")
    
    if potential_genre_mismatches:
        print(f"⚠️  Found {len(potential_genre_mismatches)} potential genre mismatch(es):\n")
        for idx, title, actual_genre, expected_genre in potential_genre_mismatches:
            print(f"  Track {idx}: {title}")
            print(f"    → Appears to be {actual_genre}, but playlist is {expected_genre}\n")
    
    print(f"🔍 Validating {len(rows)} videos from {csv_path.name}\n")
    
    issues = []
    for idx, row in enumerate(rows, 1):
        url = row.get('id', '')
        title = row.get('title', '')
        
        if not url or not title:
            print(f"❌ Row {idx}: Missing id or title")
            continue
        
        video_id = extract_video_id(url)
        result = check_video(video_id, title)
        
        # Print status with severity-based icons
        if result["severity"] == "error":
            status = "❌"
            issues.append((idx, title, result))
        elif result["severity"] == "warning":
            status = "⚠️ "
            issues.append((idx, title, result))
        else:
            status = "✅"
        
        print(f"{status} {idx:2d}. {title}")
        
        if result["error"]:
            print(f"      Error: {result['error']}")
        elif result["embeddable"]:
            if result["actual_title"] != title:
                print(f"      Actual: {result['actual_title']}")
            for warning in result["warnings"]:
                print(f"      {warning}")
        
        # Rate limit
        time.sleep(0.3)
    
    # Summary with severity breakdown
    print(f"\n{'='*70}")
    print(f"Summary: {len(rows)} videos checked")
    
    errors = [i for i in issues if i[2]["severity"] == "error"]
    warnings = [i for i in issues if i[2]["severity"] == "warning"]
    ok = len(rows) - len(issues)
    
    print(f"  ✅ OK: {ok}")
    print(f"  ⚠️  Warnings: {len(warnings)}")
    print(f"  ❌ Errors: {len(errors)}")
    
    if issues:
        print(f"\n{'='*70}")
        print("Videos with issues:")
        for idx, title, result in issues:
            print(f"\n{idx}. {title}")
            print(f"   ID: {result['video_id']}")
            if result['error']:
                print(f"   ❌ {result['error']}")
            else:
                print(f"   Actual: {result['actual_title']}")
                for warning in result['warnings']:
                    print(f"   {warning}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_playlist.py <csv_file> [max_videos]")
        print("\nExample:")
        print("  python validate_playlist.py input/early_2000s_metal_list.csv")
        print("  python validate_playlist.py input/early_2000s_metal_list.csv 10")
        sys.exit(1)
    
    csv_path = Path(sys.argv[1])
    max_videos = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    validate_csv(csv_path, max_videos)
