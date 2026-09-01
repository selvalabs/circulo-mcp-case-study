# Engineering decisions

This is a short record of the choices that shape the MCP boundary. It is not a complete architecture-decision log for Círculo.

## 1. Derive the tenant from identity

**Problem**

A multi-tenant tool call often needs business identifiers. If it also accepts the tenant as trusted input, a valid credential can attempt to operate another project.

**Decision**

Resolve `projectId` from the authenticated access token and pass it to the tool handler through the MCP principal. Treat any tenant-like field in tool arguments as non-authoritative.

**Why**

The application can reason about one source of tenant authority. The same project context follows the request into services and persistence.

**Trade-off**

Credential and token issuance must preserve a reliable tenant binding. Moving a credential between tenants is not a simple metadata edit; it requires a new identity lifecycle.

## 2. Use short-lived, server-resolved access tokens

**Problem**

A long-lived self-contained token makes immediate revocation and credential rotation harder to enforce.

**Decision**

Issue short-lived opaque bearer tokens, store only their hashes and resolve them against current credential, token and project state.

**Why**

Expiry, token revocation, credential revocation, secret rotation and project suspension can remove authority without waiting for a long token lifetime to end.

**Trade-off**

Each authenticated request depends on a server-side lookup. The token format must also carry enough tenant-bound information for the store to establish the correct RLS context before retrieving the hashed token record.

## 3. Put scopes on tools, not only routes

**Problem**

A single MCP endpoint carries many operations with different risk levels. Route-level authentication alone cannot distinguish listing lessons from deleting one.

**Decision**

Declare a required scope on every tool and validate it before calling the handler. Keep read and write scopes separate, with publication using a narrower scope than general catalog editing.

**Why**

The permission model remains visible in the tool catalog and testable as a matrix. A client can receive only the capabilities needed for its job.

**Trade-off**

The scope matrix becomes part of the product contract. New or renamed tools require a deliberate permission decision and regression coverage.

## 4. Require an explicit field for every mutation

**Problem**

An agent can call a valid write tool while exploring a task or following an ambiguous instruction.

**Decision**

Mark every write tool as confirmation-required and reject calls that do not include `confirm: true` before invoking the handler.

**Why**

Mutation intent is visible in the request and cannot be inferred silently from tool selection.

**Trade-off**

The field is not proof of human approval. A poorly governed agent could add it itself. The agent workflow therefore needs an additional policy forbidding automatic escalation from an unconfirmed call to a confirmed one.

## 5. Keep application authorization and PostgreSQL RLS

**Problem**

Application filters can be omitted or applied inconsistently as a codebase grows. Database-only authorization, on the other hand, does not explain which agent or tool was allowed to reach the query.

**Decision**

Use both. Resolve identity and tool authority in the application, pass an explicit project context to services, and execute tenant-owned queries inside a transaction that sets the current project for forced RLS policies.

The current verifier also requires RLS on MCP credential, access-token and upload-ticket tables.

**Why**

The application layer answers who may attempt the operation. The database layer limits which tenant rows the application role may observe or mutate.

**Trade-off**

This model depends on disciplined connection roles and transaction use. Migrations need a separate owner connection, while ordinary runtime connections must remain non-owner and unable to bypass RLS.

## 6. Upload files outside JSON-RPC

**Problem**

Embedding binary data as base64 in a tool call makes request sizing, file validation, retries and storage boundaries harder to control.

**Decision**

Use a confirmed MCP tool to create a short-lived, tenant-bound upload ticket, followed by one multipart upload for the declared file.

**Why**

The application can validate purpose, scope, tenant, size, media type, extension and byte signature at a dedicated boundary. Generated storage names avoid caller-controlled paths.

**Trade-off**

The agent must complete a two-step workflow and handle ticket expiry. The system also needs cleanup, storage quotas and backup policies outside the ticket mechanism.

## 7. Keep the public case separate from the private product

**Problem**

The private repository contains product code, operational history and commercial context that are not needed to explain the engineering decision.

**Decision**

Publish a documentation-only case study built from an allowlist of reviewed claims and sanitized examples. Do not mirror private source or history.

**Why**

The authorization model can be reviewed without exposing customer information, private infrastructure or proprietary product code.

**Trade-off**

Readers cannot run the full system from this repository. The case must be clear about where evidence exists and avoid presenting documentation as an open-source implementation.
