#!/usr/bin/env python3
"""Test script to verify JSON-RPC notification handling fix."""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ccw_mcp.server import CCWMCPServer


def test_jsonrpc_notifications():
    """Test that notifications (id=null) don't generate responses."""

    # Create temporary storage directory
    import tempfile
    storage_dir = Path(tempfile.mkdtemp())

    try:
        server = CCWMCPServer(storage_dir)

        print("=" * 60)
        print("Testing JSON-RPC Notification Handling")
        print("=" * 60)

        # Test 1: Normal request with valid id (should get response)
        print("\n[Test 1] Normal request with id=1")
        request1 = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ping",
            "params": {}
        }
        response1 = server.handle_request(request1)
        print(f"Request: {json.dumps(request1)}")
        print(f"Response: {json.dumps(response1) if response1 else 'None (no response)'}")
        assert response1 is not None, "Should get response for normal request"
        assert response1["id"] == 1, "Response id should match request id"
        assert "result" in response1, "Response should have result"
        print("✓ PASS: Normal request handled correctly")

        # Test 2: Notification with id=null (should NOT get response)
        print("\n[Test 2] Notification with id=null")
        request2 = {
            "jsonrpc": "2.0",
            "id": None,
            "method": "ping",
            "params": {}
        }
        response2 = server.handle_request(request2)
        print(f"Request: {json.dumps(request2)}")
        print(f"Response: {json.dumps(response2) if response2 else 'None (no response)'}")
        assert response2 is None, "Should NOT get response for notification with id=null"
        print("✓ PASS: Notification with id=null handled correctly (no response)")

        # Test 3: Notification without id field (should NOT get response)
        print("\n[Test 3] Notification without id field")
        request3 = {
            "jsonrpc": "2.0",
            "method": "ping",
            "params": {}
        }
        response3 = server.handle_request(request3)
        print(f"Request: {json.dumps(request3)}")
        print(f"Response: {json.dumps(response3) if response3 else 'None (no response)'}")
        assert response3 is None, "Should NOT get response for notification without id"
        print("✓ PASS: Notification without id handled correctly (no response)")

        # Test 4: 'initialized' notification (always a notification)
        print("\n[Test 4] 'initialized' notification")
        request4 = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        }
        response4 = server.handle_request(request4)
        print(f"Request: {json.dumps(request4)}")
        print(f"Response: {json.dumps(response4) if response4 else 'None (no response)'}")
        assert response4 is None, "Should NOT get response for 'initialized' notification"
        print("✓ PASS: 'initialized' notification handled correctly (no response)")

        # Test 5: Unknown method notification (should NOT get error response)
        print("\n[Test 5] Unknown method notification")
        request5 = {
            "jsonrpc": "2.0",
            "id": None,
            "method": "unknown_method",
            "params": {}
        }
        response5 = server.handle_request(request5)
        print(f"Request: {json.dumps(request5)}")
        print(f"Response: {json.dumps(response5) if response5 else 'None (no response)'}")
        assert response5 is None, "Should NOT get error response for notification with unknown method"
        print("✓ PASS: Unknown method notification handled correctly (no response)")

        # Test 6: Unknown method request (should get error response)
        print("\n[Test 6] Unknown method request with id")
        request6 = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "unknown_method",
            "params": {}
        }
        response6 = server.handle_request(request6)
        print(f"Request: {json.dumps(request6)}")
        print(f"Response: {json.dumps(response6) if response6 else 'None (no response)'}")
        assert response6 is not None, "Should get error response for request with unknown method"
        assert response6["id"] == 6, "Error response id should match request id"
        assert "error" in response6, "Response should have error"
        assert response6["error"]["code"] == -32601, "Error code should be -32601 (Method not found)"
        print("✓ PASS: Unknown method request handled correctly (error response)")

        # Test 7: Parse error (should get error response with id=null)
        print("\n[Test 7] Invalid request (not a dict)")
        request7 = "not a dict"
        response7 = server.handle_request(request7)
        print(f"Request: {request7}")
        print(f"Response: {json.dumps(response7) if response7 else 'None (no response)'}")
        assert response7 is not None, "Should get error response for invalid request"
        assert response7["id"] is None, "Error response for parse error should have id=null"
        assert "error" in response7, "Response should have error"
        print("✓ PASS: Parse error handled correctly (error response with id=null)")

        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)

    finally:
        # Cleanup
        import shutil
        shutil.rmtree(storage_dir, ignore_errors=True)


if __name__ == "__main__":
    test_jsonrpc_notifications()
