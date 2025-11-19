#!/usr/bin/env python3
"""
Generate index.html landing page from existing power hour HTML files.
Automatically creates playlist cards with descriptions.
"""

import os
import re
from pathlib import Path

# Playlist metadata: filename stem -> (title, description)
PLAYLIST_INFO = {
    "70s_light_rock_power_hour": (
        "70s Light Rock",
        "Simon & Garfunkel, Fleetwood Mac, Eagles, and more soft rock classics"
    ),
    "70s_metal_power_hour": (
        "70s Metal",
        "Black Sabbath, Judas Priest, Motörhead, and heavy metal pioneers"
    ),
    "80s_synth_pop_power_hour": (
        "80s Synth Pop",
        "Depeche Mode, New Order, Duran Duran, and synth-driven hits"
    ),
    "90s_grunge_power_hour": (
        "90s Grunge",
        "Nirvana, Pearl Jam, Soundgarden, Alice in Chains"
    ),
    "90s_grunge_deep_cuts": (
        "90s Grunge Deep Cuts",
        "Temple of the Dog, Mad Season, Screaming Trees, and hidden gems"
    ),
    "90s_punk_power_hour": (
        "90s Punk",
        "Green Day, Rancid, NOFX, Blink-182, and punk rock anthems"
    ),
    "early_2000s_metal_power_hour": (
        "Early 2000s Metal",
        "Slipknot, Static-X, Mudvayne, Tool, and nu-metal heavyweights"
    ),
    "americana_power_hour": (
        "Americana",
        "Alt-country, folk-rock, and rootsy Americana vibes"
    ),
    "one_hit_wonders": (
        "One Hit Wonders",
        "Those unforgettable songs from artists you forgot existed"
    ),
    "90s_pop_rock_female_power_hour": (
        "90s Pop/Rock/Female",
        "No Doubt, Alanis Morissette, Garbage, Hole, The Cranberries, TLC, Spice Girls, and more 90s hits"
    ),
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Power Hour Creator - Playlists</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
            color: #fff;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            font-size: 3rem;
            margin-bottom: 0.5rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .subtitle {{
            font-size: 1.2rem;
            opacity: 0.9;
            margin-bottom: 3rem;
        }}
        .playlists {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.5rem;
        }}
        .playlist-card {{
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
            text-decoration: none;
            color: #fff;
            display: block;
        }}
        .playlist-card:hover {{
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.15);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        .playlist-title {{
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        .playlist-desc {{
            opacity: 0.8;
            font-size: 0.9rem;
        }}
        .footer {{
            margin-top: 4rem;
            text-align: center;
            opacity: 0.7;
            font-size: 0.9rem;
        }}
        .footer a {{
            color: #fff;
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Power Hour Creator</h1>
        <p class="subtitle">60 songs × 60 seconds = 1 epic hour</p>
        
        <div class="playlists">
{playlist_cards}
        </div>
        
        <div class="footer">
            <p>Made with ❤️ using the <a href="https://github.com/slucas25/power-hour-builder" target="_blank">Power Hour Creator</a></p>
            <p>Want your own playlist? <a href="https://github.com/slucas25/power-hour-builder/issues/new?template=playlist-idea.md" target="_blank">Submit an idea</a></p>
        </div>
    </div>
</body>
</html>
"""

CARD_TEMPLATE = """            <a href="{filename}" class="playlist-card">
                <div class="playlist-title">{title}</div>
                <div class="playlist-desc">{description}</div>
            </a>
"""


def generate_index():
    """Generate index.html from HTML files in output/ directory."""
    output_dir = Path(__file__).parent.parent / "output"
    
    # Find all power hour HTML files (exclude index, test, preview files)
    html_files = []
    for file in output_dir.glob("*.html"):
        if file.stem in ["index", "test", "preview_youtube", "power_hour_youtube"]:
            continue
        html_files.append(file)
    
    # Sort by filename for consistent order
    html_files.sort()
    
    # Generate cards
    cards = []
    for file in html_files:
        stem = file.stem
        
        # Get metadata or generate default
        if stem in PLAYLIST_INFO:
            title, description = PLAYLIST_INFO[stem]
        else:
            # Generate title from filename
            title = stem.replace("_", " ").replace(" power hour", "").title()
            description = f"A curated power hour playlist"
            print(f"⚠️  Warning: No metadata for '{stem}', using defaults")
        
        card = CARD_TEMPLATE.format(
            filename=file.name,
            title=title,
            description=description
        )
        cards.append(card)
    
    # Generate full HTML
    html = HTML_TEMPLATE.format(
        playlist_cards="\n".join(cards)
    )
    
    # Write to file
    index_file = output_dir / "index.html"
    index_file.write_text(html)
    
    print(f"✅ Generated {index_file} with {len(cards)} playlists")


if __name__ == "__main__":
    generate_index()
