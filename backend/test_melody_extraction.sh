#!/bin/bash
# Test script to demonstrate melody extraction feature

echo "🎵 Songify Melody Extraction Test"
echo "=================================="
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

# Check if we have a test audio file
TEST_FILE="${1:-tmp/stems/*.wav}"

if [ -z "$(ls $TEST_FILE 2>/dev/null | head -1)" ]; then
    echo "❌ No test audio file found"
    echo "Usage: $0 <path/to/audio.mp3>"
    echo ""
    echo "Or first run audio separation:"
    echo "  curl -X POST http://localhost:8000/api/separate -F 'file=@song.mp3'"
    exit 1
fi

# Get first available WAV file
AUDIO_FILE=$(ls $TEST_FILE 2>/dev/null | head -1)
echo "Using test file: $AUDIO_FILE"
echo ""

# Test 1: Full transcription (no filtering)
echo "📊 Test 1: Full Transcription (no filtering)"
echo "---------------------------------------------"
curl -s -X POST "http://localhost:8000/api/transcribe?min_amplitude=0.0" \
  -F "file=@$AUDIO_FILE" | jq '{note_count, duration_s, melody_applied}'
echo ""

# Test 2: Melody-only mode
echo "🎼 Test 2: Melody-Only Mode (single note line)"
echo "---------------------------------------------"
curl -s -X POST "http://localhost:8000/api/transcribe?melody_only=true&min_amplitude=0.6" \
  -F "file=@$AUDIO_FILE" | jq '{note_count, duration_s, melody_applied, melody_stats}'
echo ""

# Test 3: Reduced polyphony (allow chords)
echo "🎹 Test 3: Reduced Polyphony (3 simultaneous notes)"
echo "---------------------------------------------"
curl -s -X POST "http://localhost:8000/api/transcribe?polyphony_limit=3&min_amplitude=0.5" \
  -F "file=@$AUDIO_FILE" | jq '{note_count, duration_s, melody_applied, melody_stats}'
echo ""

echo "✅ All tests complete!"
echo ""
echo "💡 Tips:"
echo "  - melody_only=true: Best for readable sheet music"
echo "  - min_amplitude=0.6-0.7: Aggressive filtering"
echo "  - polyphony_limit=1: Monophonic melody"
echo "  - polyphony_limit=3-4: Allow chords"
