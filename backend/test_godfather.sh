#!/bin/bash
# Test pipeline with Godfather Theme audio

echo "🎵 Testing Songify Pipeline with Godfather Theme"
echo "================================================="
echo ""

# Start server in background
echo "Starting server..."
cd /home/moustafa/VsCodeProjects/songify/backend
source .venv/bin/activate

# Start server
./start.sh &
SERVER_PID=$!

# Wait for server to be ready
echo "Waiting for server to load models..."
sleep 30

# Check if server is ready
if ! curl -s http://localhost:8000/ > /dev/null; then
    echo "❌ Server failed to start"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi

echo "✅ Server ready!"
echo ""

# Run pipeline
AUDIO_FILE="tmp/The Godfather Theme - EASY Piano Tutorial Synthesia (Download MIDI + PDF Sheets).mp3"

echo "📤 Uploading: $AUDIO_FILE"
echo "⏳ This will take 1-3 minutes (separating, transcribing, analyzing)..."
echo ""

curl -X POST "http://localhost:8000/api/pipeline" \
  -F "file=@${AUDIO_FILE}" \
  -o godfather_result.json

echo ""
echo "📊 Results:"
cat godfather_result.json | jq '{note_count, tempo_bpm, stats: {original_count, final_count, reduction_pct, vocal_guided}}'

# Download MIDI
MIDI_URL=$(jq -r '.melody_midi_url' godfather_result.json)
curl -s "http://localhost:8000${MIDI_URL}" -o godfather_output.mid

echo ""
echo "✅ Done!"
echo ""
echo "Output files:"
echo "  - godfather_output.mid (generated MIDI)"
echo "  - godfather_result.json (analysis stats)"
echo ""
echo "📊 Compare:"
echo "  Reference: tmp/The-Godfather-Theme.mid (~567 notes)"
echo "  Generated: godfather_output.mid"
echo ""

# Stop server
kill $SERVER_PID 2>/dev/null || true

echo "💡 To start server manually: ./start.sh"
