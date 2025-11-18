#!/usr/bin/env python3
"""
Playlist Generator Script
Can be triggered by GitHub Actions or run manually.
"""
import os
import sys
import json
from pathlib import Path

def parse_issue_body(body: str) -> dict:
    """Extract structured data from issue template."""
    import re
    
    theme_match = re.search(r'## Playlist Theme\s*(?:<!--.*?-->\s*)?(.*?)(?=\n##|\n---|\Z)', body, re.DOTALL)
    desc_match = re.search(r'## Description\s*(?:<!--.*?-->\s*)?(.*?)(?=\n##|\n---|\Z)', body, re.DOTALL)
    samples_match = re.search(r'## Sample Songs/Artists\s*(?:<!--.*?-->\s*)?(.*?)(?=\n##|\n---|\Z)', body, re.DOTALL)
    era_match = re.search(r'## Target Era/Genre\s*(?:<!--.*?-->\s*)?(.*?)(?=\n##|\n---|\Z)', body, re.DOTALL)
    notes_match = re.search(r'## Additional Notes\s*(?:<!--.*?-->\s*)?(.*?)(?=\n##|\n---|\Z)', body, re.DOTALL)
    
    return {
        'theme': theme_match.group(1).strip() if theme_match else '',
        'description': desc_match.group(1).strip() if desc_match else '',
        'samples': samples_match.group(1).strip() if samples_match else '',
        'era': era_match.group(1).strip() if era_match else '',
        'notes': notes_match.group(1).strip() if notes_match else ''
    }

def generate_filename(theme: str) -> str:
    """Generate safe filename from theme."""
    import re
    return re.sub(r'[^a-z0-9]+', '_', theme.lower()).strip('_')

def main():
    """Main entry point for playlist generation."""
    if len(sys.argv) < 2:
        print("Usage: python generate_playlist.py <issue_body_json>")
        sys.exit(1)
    
    # Load issue data from JSON
    issue_data = json.loads(sys.argv[1])
    
    # Parse the issue
    parsed = parse_issue_body(issue_data['body'])
    theme = parsed['theme'] or issue_data['title'].replace('[PLAYLIST] ', '')
    filename = generate_filename(theme)
    
    print(f"🎵 Generating playlist: {theme}")
    print(f"📝 Filename: {filename}")
    print(f"📋 Description: {parsed['description']}")
    print(f"🎸 Samples: {parsed['samples'][:100]}...")
    print(f"📅 Era: {parsed['era']}")
    
    # Output instructions for the coding agent
    prompt = f"""Create a power hour playlist for: {theme}

**Theme Details:**
- Description: {parsed['description']}
- Era/Genre: {parsed['era']}
- Sample Artists/Songs:
{parsed['samples']}
- Additional Notes: {parsed['notes']}

**Instructions:**
1. Research 60 songs matching this theme
2. Find official music videos on YouTube (no &start_radio=1 URLs)
3. Verify each URL with curl
4. Prefer studio versions over live performances
5. Create: input/{filename}_list.csv
6. Generate HTML: output/{filename}_power_hour.html
7. Run validation: pytest tests/
8. Create PR linking to issue #{issue_data.get('number', 'N/A')}

Refer to README.md for the verification process.
"""
    
    print("\n" + "="*60)
    print("AGENT PROMPT:")
    print("="*60)
    print(prompt)
    
    # Write to file for agent consumption
    Path('agent_prompt.txt').write_text(prompt)
    print("\n✅ Agent prompt written to agent_prompt.txt")

if __name__ == '__main__':
    main()
