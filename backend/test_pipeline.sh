#!/bin/bash
# Quick test script for the new pipeline endpoint

echo "🎵 Songify Intelligent Pipeline Test"
echo "======================================"
echo ""

# Check if server is running
echo "Checking if server is running..."
if ! curl -s http://localhost:8000/ > /dev/null; then
    echo "❌ Server is not running!"
    echo "Start it with: ./start.sh"
    exit 1
fi

echo "✅ Server is running"
echo ""

# Check health
echo "Checking pipeline health..."
curl -s http://localhost:8000/api/health/pipeline | jq
echo ""

# Check for test audio
TEST_FILE="${1}"

if [ -z "$TEST_FILE" ] || [ ! -f "$TEST_FILE" ]; then
    echo "❌ No test audio file provided"
    echo "Usage: $0 <path/to/song.mp3>"
    exit 1
fi

echo "Using test file: $TEST_FILE"
echo ""

# Test pipeline with different target_notes values
echo "🎼 Test 1: Simple melody (target_notes=25)"
echo "-------------------------------------------"
curl -s -X POST "http://localhost:8000/api/pipeline?target_notes=25" \
  -F "file=@$TEST_FILE" | jq '{note_count, stats: .stats | {final_count, reduction_pct, vocal_guided}}'
echo ""

echo "🎼 Test 2: Balanced melody (target_notes=40, recommended)"
echo "-------------------------------------------"
curl -s -X POST "http://localhost:8000/api/pipeline?target_notes=40" \
  -F "file=@$TEST_FILE" -o pipeline_result.json
cat pipeline_result.json | jq '{note_count, stats: .stats | {original_count, final_count, reduction_pct, vocal_guided}}'
echo ""

# Download the MIDI
MIDI_URL=$(jq -r '.melody_midi_url' pipeline_result.json)
curl -s "http://localhost:8000${MIDI_URL}" -o pipeline_melody.mid
echo "✅ Downloaded: pipeline_melody.mid"
echo ""

echo "📊 Full statistics:"
cat pipeline_result.json | jq '.stats'
echo ""

echo "✅ Pipeline test complete!"
echo ""
echo "💡 Compare with old method:"
echo "   Old: /api/transcribe → 660 notes (crowded)"
echo "   New: /api/pipeline → ~40 notes (clean!)"
