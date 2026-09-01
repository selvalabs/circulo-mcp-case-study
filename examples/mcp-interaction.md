# Sanitized MCP interaction

The examples below are reduced and use fictional values. They show the shape of the current interaction without exposing a real tenant, credential, endpoint or product response.

## 1. Obtain a short-lived access token

A project administrator has already created a tenant-bound client credential and stored its one-time secret in the agent environment.

```bash
curl --fail-with-body \
  -u "$MCP_CLIENT_ID:$MCP_CLIENT_SECRET" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=client_credentials&resource=https%3A%2F%2Flearning.example.com%2Fmcp" \
  https://learning.example.com/oauth/token
```

Reduced response:

```json
{
  "access_token": "<short-lived opaque token>",
  "token_type": "Bearer",
  "expires_in": 900,
  "scope": "project:read catalog:read catalog:write"
}
```

The access token resolves to one agent identity, one project and the granted scope set. Those values are not supplied again in the tool arguments.

## 2. Initialize the MCP connection

```http
POST /mcp
Authorization: Bearer <access token>
Content-Type: application/json
Origin: https://approved-agent.example
```

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {}
}
```

Reduced response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "capabilities": {
      "tools": {
        "listChanged": false
      }
    }
  }
}
```

The real implementation also returns server and project metadata. They are omitted here because the example does not need a concrete internal server name or tenant identifier.

## 3. Discover tools

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

Reduced response:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "list_tracks",
        "description": "List the published tracks available to the authenticated tenant.",
        "inputSchema": {
          "type": "object",
          "properties": {},
          "additionalProperties": false
        }
      },
      {
        "name": "create_course",
        "description": "Create a course in the authenticated tenant.",
        "inputSchema": {
          "type": "object",
          "required": ["trackSlug", "title", "confirm"],
          "properties": {
            "trackSlug": { "type": "string" },
            "title": { "type": "string" },
            "confirm": { "const": true }
          },
          "additionalProperties": false
        }
      }
    ]
  }
}
```

The current product exposes more tools than this excerpt. The descriptions above are translated and shortened for the case study.

## 4. Call a read tool

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "list_tracks",
    "arguments": {}
  }
}
```

Reduced response:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"slug\":\"example-track\",\"name\":\"Example Track\"}]"
      }
    ],
    "structuredContent": [
      {
        "slug": "example-track",
        "name": "Example Track"
      }
    ]
  }
}
```

The result is already limited to the project bound to the access token.

## 5. Attempt a write without confirmation

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "create_course",
    "arguments": {
      "trackSlug": "example-track",
      "title": "New Course"
    }
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "error": {
    "code": -32005,
    "message": "Explicit confirmation is required for this operation."
  }
}
```

The tool handler is not invoked.

The agent should not automatically retry with confirmation. It must first obtain explicit authorization in the surrounding human-agent workflow.

## 6. Perform the confirmed write

After that authorization has been obtained:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "create_course",
    "arguments": {
      "trackSlug": "example-track",
      "title": "New Course",
      "confirm": true
    }
  }
}
```

Reduced response:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "structuredContent": {
      "slug": "new-course",
      "title": "New Course",
      "visible": true
    }
  }
}
```

There is no trusted `projectId` in the request arguments. The handler receives its project context from the authenticated principal. A non-conforming caller cannot gain authority over another tenant by adding a different project identifier to the payload.

## 7. Revoke the token

The OAuth revocation endpoint requires the same client authentication boundary used to issue the token.

```bash
curl --fail-with-body \
  -u "$MCP_CLIENT_ID:$MCP_CLIENT_SECRET" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "token=$MCP_ACCESS_TOKEN" \
  https://learning.example.com/oauth/revoke
```

A later call using that token is rejected with HTTP `401`.

## Reading these examples correctly

These examples demonstrate the contract, not a hosted public demo. They intentionally omit:

- real tenant identifiers;
- credential formats and secret values;
- private product fields;
- internal paths and infrastructure;
- complete tool responses;
- provider-specific commercial configuration.

The full behavior is validated in the private implementation and summarized in [Testing the boundary](../docs/testing.md).
