# MCP design

Círculo uses MCP as a controlled application interface, not as a generic bridge to its database or internal HTTP routes.

The server exposes product operations as named tools. Each tool has a description, an input schema, one required scope and, for mutations, a confirmation requirement. The handler receives an authenticated principal rather than a caller-selected tenant.

## Transport

The current interface uses an HTTP `POST /mcp` endpoint with JSON-RPC 2.0 messages.

It implements the three methods needed by the current tool workflow:

- `initialize` — returns server information and MCP capabilities;
- `tools/list` — returns the tools and their published input schemas;
- `tools/call` — authorizes and invokes one tool.

Successful tool calls return both a text representation and `structuredContent`. The structured value lets a client use the result without parsing prose generated for a person.

The server rejects malformed JSON-RPC requests, unknown methods and unknown tools with bounded errors. Tool exceptions are not returned verbatim to the caller.

## Request pipeline

A request passes through the following sequence:

```text
HTTP request
  -> Origin check when present
  -> Bearer token extraction
  -> Token resolution
  -> Active-project check
  -> JSON-RPC validation
  -> Tool lookup
  -> Scope check
  -> Confirmation check for writes
  -> Tool handler
  -> Structured result
```

The sequence keeps policy checks outside the domain handler. A handler does not need to decide whether a read-only token should have reached it, and a missing confirmation does not become a branch repeated in every write implementation.

## OAuth and token lifecycle

The product provides OAuth discovery metadata and a Client Credentials flow when MCP credential support is enabled.

A project administrator creates a credential for one agent inside one tenant. The secret is displayed once and stored only as a hash. The agent exchanges that credential for a short-lived opaque bearer token.

At issuance time, the requested scopes must be a subset of the credential scopes. At request time, the token resolves to a principal containing the agent, project, scopes and expiry.

Rotation or revocation invalidates the affected token lifecycle. The MCP endpoint is not responsible for guessing whether a credential is still valid from data embedded in a long-lived self-contained token; the current production path resolves the opaque token against server-side state.

A signed-token verifier also exists as a lower-level server option and test path, but it is not the primary credential-store design described in this case.

## Tool model

A tool declaration contains:

```text
name
description
input schema
required scope
confirmation requirement
handler
```

The input schema helps clients discover the expected contract. Domain handlers still validate identifiers, lengths, allowed values and references before calling application stores.

Representative tool groups in the current implementation include:

| Product area | Read examples | Write examples |
| --- | --- | --- |
| Project | `get_project_context`, `list_mcp_capabilities` | — |
| Members | `list_members` | `create_member`, `grant_member_access`, `revoke_member_access` |
| Catalog | `list_tracks`, `list_courses`, `list_modules`, `list_lessons` | create, update and delete tools for tracks, courses, modules and lessons |
| Publication | — | `publish_lesson` |
| Appearance | `get_appearance` | `update_appearance` |
| Settings | `get_project_settings_public` | `update_project_settings` |
| Assets | `list_assets` | `prepare_asset_upload`, `delete_asset` |
| Materials | `list_materials` | `prepare_material_upload`, `delete_material` |
| Commerce | provider and integration status reads | controlled configuration and offer-mapping operations |

The table is a product-oriented summary rather than a promise that every internal operation is exposed through MCP.

## Read and write are different capabilities

Círculo does not use one broad `catalog` or `admin` permission.

Reading a catalog requires `catalog:read`. Editing it requires `catalog:write`. Publishing a lesson uses the separate `catalog:publish` scope. The same pattern appears in members, appearance, settings, assets, materials and commerce.

Every current write tool is marked as requiring confirmation. This includes preparatory writes such as creating an upload ticket, not only final content changes.

The transport test suite verifies that scope and confirmation failures occur before the handler is invoked. A separate scope-matrix test checks the mapping between the tool catalog and its intended scopes.

## Tenant context is not a tool argument

Tools accept business identifiers, not authority identifiers.

For example, `create_course` may accept a track slug and a title. It does not need a trusted `projectId` in its arguments because the project has already been resolved from the bearer token.

A test deliberately adds a conflicting tenant value to a write request and verifies that the application service receives the project from the token principal.

This avoids a common multi-tenant failure mode:

```text
valid credential for Tenant A
+
caller-controlled projectId for Tenant B
=
unauthorized Tenant B operation
```

The design removes the second term from the authority equation.

## Two-stage file uploads

Binary files are not embedded as base64 inside `tools/call`.

The agent first calls a confirmed tool to prepare an upload. The application creates a short-lived, tenant-bound ticket for one declared purpose, filename, media type and exact size. The agent then sends one multipart upload to the returned path.

The upload boundary checks:

- the bearer token and required write scope;
- ticket ownership by the token tenant;
- ticket purpose and expiry;
- one-time consumption;
- declared and actual size;
- media type, extension and file signature;
- generated storage names rather than caller-controlled paths.

The current product limits images to 5 MiB and PDF materials to 25 MiB. Remote URLs are not accepted as a replacement for these uploads.

The PostgreSQL integration flow verifies that a token from another tenant cannot consume a prepared ticket and that the failed attempt does not mark the ticket as used.

## External-service boundary

Some content may refer to media hosted by an external provider. The current MCP contract stores an allowed public reference rather than accepting provider API keys inside lesson data.

The agent can operate the external account through the client's own authorized integration and then pass the resulting reference to Círculo. This keeps the product operation and the external provider operation as separate authority boundaries.

This case does not claim that every external setup step is automated through Círculo.

## What MCP does not do here

The MCP server does not:

- give an agent generic SQL access;
- let tool arguments select a tenant;
- turn read scopes into implied write access;
- infer confirmation from conversational context;
- run an autonomous planning loop;
- host or select an LLM;
- expose the complete administrative surface of the product;
- make unsupported external-provider calls appear successful.

It is a narrow interface between an already authorized agent workflow and specific product operations.
