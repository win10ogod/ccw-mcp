# JSON-RPC Notification Handling Fix

## Problem

The MCP server was encountering errors when clients sent JSON-RPC messages with `id: null`:

```
pydantic_core._pydantic_core.ValidationError: 9 validation errors for JSONRPCMessage
JSONRPCResponse.id.int
  Input should be a valid integer [type=int_type, input_value=None, input_type=NoneType]
```

## Root Cause

According to the JSON-RPC 2.0 specification:

1. **Notification**: A request with `id: null` or without an `id` field is a notification
2. **Notification Behavior**: The server MUST NOT send a response for notifications

The issue occurred when:
- Client sends a request with `id: null` (or no `id` field)
- Server incorrectly sent a response with `id: null`
- Client's Pydantic model rejected responses with `id: null` (expecting int or string)

## Solution

Modified `ccw_mcp/server.py` to properly handle notifications according to JSON-RPC 2.0 spec:

### Key Changes

1. **Detect Notifications**: Check if `req_id is None` to identify notifications
2. **No Response for Notifications**: Return `None` instead of sending responses
3. **No Error Responses for Notifications**: Even for errors, don't send responses
4. **Preserve Error Responses for Parse Errors**: Keep `id: null` for genuine parse errors (per spec)

### Code Changes

```python
# Detect notification
is_notification = req_id is None

# For notifications, don't send success response
if is_notification:
    return None

# For notifications, don't send error response
if is_notification:
    print(f"Error in notification: {error}", file=sys.stderr)
    return None
```

## Testing

Created comprehensive test suite (`test_jsonrpc_fix.py`) covering:

- ✓ Normal requests with valid `id` (get response)
- ✓ Notifications with `id: null` (no response)
- ✓ Notifications without `id` field (no response)
- ✓ `initialized` notification (always no response)
- ✓ Unknown method notifications (no error response)
- ✓ Unknown method requests (get error response)
- ✓ Parse errors (get error response with `id: null`)

All tests pass. Existing test suite remains green.

## JSON-RPC 2.0 Compliance

This fix ensures full compliance with JSON-RPC 2.0 specification:

> **3.2 Notification**: A Notification is a Request object without an "id" member. A Request object that is a Notification signifies the Client's lack of interest in the corresponding Response object, and as such no Response object needs to be returned to the client.

> **The Server MUST NOT reply to a Notification**, including those that are within a batch request.

## Impact

- Fixes compatibility with MCP SDK clients using strict Pydantic validation
- Reduces unnecessary network traffic (no responses for notifications)
- Improves spec compliance and interoperability
- No breaking changes to existing functionality

## Related

- JSON-RPC 2.0 Specification: https://www.jsonrpc.org/specification
- MCP Protocol: https://modelcontextprotocol.io/
