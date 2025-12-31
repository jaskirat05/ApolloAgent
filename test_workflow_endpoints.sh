#!/bin/bash
# Test script for new workflow discovery endpoints

GATEWAY="http://localhost:8001"

echo "========================================"
echo "Testing Workflow Discovery Endpoints"
echo "========================================"
echo

echo "1. List all workflows"
echo "GET $GATEWAY/workflows"
echo "----------------------------------------"
curl -s "$GATEWAY/workflows" | python3 -m json.tool
echo
echo

echo "2. Get workflow details"
echo "GET $GATEWAY/workflows/video_wan2_2_14B_i2v"
echo "----------------------------------------"
curl -s "$GATEWAY/workflows/video_wan2_2_14B_i2v" | python3 -m json.tool | head -50
echo "... (truncated)"
echo
echo

echo "3. Execute workflow with parameter overrides"
echo "POST $GATEWAY/workflows/video_wan2_2_14B_i2v/execute"
echo "----------------------------------------"
curl -s -X POST "$GATEWAY/workflows/video_wan2_2_14B_i2v/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "93.text": "A majestic dragon soaring through stormy clouds",
      "98.width": 1024,
      "98.height": 576
    },
    "strategy": "least_loaded"
  }' | python3 -m json.tool
echo
echo

echo "4. Test error handling - invalid parameter"
echo "POST $GATEWAY/workflows/video_wan2_2_14B_i2v/execute"
echo "----------------------------------------"
curl -s -X POST "$GATEWAY/workflows/video_wan2_2_14B_i2v/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "999.invalid": "This should fail"
    }
  }' | python3 -m json.tool
echo
echo

echo "5. Test error handling - workflow not found"
echo "GET $GATEWAY/workflows/nonexistent_workflow"
echo "----------------------------------------"
curl -s "$GATEWAY/workflows/nonexistent_workflow" | python3 -m json.tool
echo
echo

echo "========================================"
echo "Tests Complete"
echo "========================================"
