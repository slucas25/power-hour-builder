#!/bin/bash
# Serve power hour HTML files locally and open in browser
# Usage: ./serve.sh [filename.html] [port]

PORT="${2:-8000}"
FILE="${1:-}"

# Start server in background
cd output || exit 1

echo "🎵 Starting local server on port $PORT..."
python3 -m http.server "$PORT" &
SERVER_PID=$!

# Give server a moment to start
sleep 1

# Determine URL
if [ -n "$FILE" ]; then
    URL="http://localhost:$PORT/$FILE"
else
    URL="http://localhost:$PORT/"
fi

echo "🌐 Opening: $URL"
echo "🛑 Press Ctrl+C to stop the server"

# Open in default browser
open "$URL"

# Wait for user to stop server
trap "echo ''; echo '🛑 Stopping server...'; kill $SERVER_PID 2>/dev/null; exit 0" INT

# Keep script running
wait $SERVER_PID
