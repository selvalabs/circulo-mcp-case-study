# Testing the boundary

The purpose of the MCP tests is not to prove that a tool returns a happy-path object. The useful question is whether authority stays consistent when a request is missing, conflicting or malicious.

This document summarizes evidence reviewed in the private Círculo repository on September 1, 2026. It does not publish the source tests or their private fixtures.

## Test layers

The current implementation uses several layers because no single test style covers the whole boundary.

| Layer | What it checks |
| --- | --- |
| Transport and tool unit tests | Authentication, origin checks, JSON-RPC handling, scope enforcement, confirmation and handler invocation. |
| Scope-matrix test | Every tool in the tested configuration has an intentional scope; all writes require confirmation. |
| Credential and OAuth tests | One-time secrets, hashed storage, token lifetime, scope subsets, discovery, rotation and revocation. |
| RLS verifier | PostgreSQL policies with a non-owner, non-bypass role and concurrent tenant contexts. |
| PostgreSQL MCP integration runner | OAuth, real application stores, two tenants, writes, uploads and token revocation. |
| MCP-specific browser journey | Administrative credential creation followed by OAuth and MCP calls over HTTP. |
| Main CI | Unit tests, database preparation, RLS verification, general browser coverage, build, container build and dependency audit. |

## Risk-to-evidence map

### Missing or invalid authentication

**Risk:** an unauthenticated caller reaches tool discovery or execution.

**Evidence:** transport tests send an MCP request without a bearer token and with an invalid token. Both are rejected before method handling.

### Origin confusion

**Risk:** a browser-originated request comes from an unapproved origin.

**Evidence:** unit and browser-level tests send an otherwise valid bearer token with a disallowed `Origin` and expect HTTP `403`.

Origin validation is an additional browser boundary. It is not presented as a replacement for bearer authentication.

### Inactive tenant

**Risk:** an agent keeps operating after its project has been suspended or archived.

**Evidence:** the transport suite resolves a valid principal and then rejects it through the active-project guard before tool execution.

### Scope escalation

**Risk:** a read-only agent calls a write tool.

**Evidence:** a valid token with `catalog:read` attempts a `catalog:write` operation. The server returns the insufficient-scope error and the mocked handler is never called.

The scope-matrix test also compares the exposed tool catalog with an expected tool-to-scope mapping.

### Implicit mutation

**Risk:** a model discovers a write tool and executes it while exploring, without making mutation intent explicit.

**Evidence:** a write-capable token calls a write tool without `confirm: true`. The server returns the missing-confirmation error and the handler is not called.

The scope-matrix test separately checks that every write tool in the tested catalog is marked as requiring confirmation.

### Caller-selected tenant

**Risk:** a token for Tenant A adds `projectId: Tenant B` to a tool payload.

**Evidence:** a transport test sends a conflicting tenant value to a confirmed write call. The application service receives Tenant A from the authenticated principal rather than Tenant B from the arguments.

### Database leakage

**Risk:** an incomplete application query reads or changes rows owned by another project.

**Evidence:** the RLS verifier creates or updates a dedicated PostgreSQL role with `NOSUPERUSER` and `NOBYPASSRLS`, then checks that:

- tenant-owned reads return only the current project;
- a missing project context returns no tenant rows;
- a mismatched tenant insert is blocked;
- cross-tenant update and delete operations are blocked;
- two concurrent connections keep separate project contexts;
- MCP credential, access-token and upload-ticket tables have both `ENABLE` and `FORCE ROW LEVEL SECURITY`.

This verifier is run against a disposable PostgreSQL fixture during the main CI workflow.

### Cross-tenant upload-ticket use

**Risk:** an agent prepares a file-upload ticket in Tenant A and a token from Tenant B consumes it.

**Evidence:** the dedicated PostgreSQL MCP runner creates two project credentials, prepares a tenant-bound upload ticket, attempts to use it with the other tenant's token and expects the resource to be unavailable. It then verifies that the rejected attempt did not consume the original ticket.

The same runner exercises successful image and PDF uploads with generated references.

### Revoked authority

**Risk:** a token or credential remains usable after revocation.

**Evidence:** credential-store tests cover token revocation through authenticated client credentials. The PostgreSQL runner revokes an issued access token and confirms that a later MCP request receives HTTP `401`.

The MCP browser journey also creates a credential through the administration UI, rotates its secret, revokes it and confirms that new token issuance fails.

## The PostgreSQL MCP runner

The deeper integration runner is useful because it does not replace persistence with mocks.

Before exercising MCP, it verifies that the application connection is using a PostgreSQL role that is neither a superuser nor able to bypass RLS. It then uses two seeded tenants and the current Prisma stores to cover a representative workflow:

- create tenant-bound OAuth credentials;
- issue short-lived access tokens;
- reject a write without confirmation;
- create a track, course, module and draft lesson through MCP;
- read members and change access through scoped tools;
- update appearance and project settings;
- keep asset listings isolated by tenant;
- reject cross-tenant ticket consumption;
- revoke a token and reject later use.

This is not a load test. Its role is to check that the transport, credential store, tool layer, application stores and RLS context agree about tenant authority.

## The browser journey

A dedicated Playwright flow starts the application with MCP enabled on isolated local ports. Through the administrative interface it:

1. authenticates an administrator;
2. creates an agent credential with an expiry;
3. checks that the client secret is shown once;
4. exchanges it through OAuth Client Credentials;
5. initializes the MCP session;
6. rejects an invalid origin;
7. rotates the secret;
8. revokes the credential;
9. rejects token issuance with the revoked credential.

This test covers the path a project administrator would actually use, rather than calling only the credential store directly.

## What runs in the main CI workflow

The private product's main workflow currently prepares PostgreSQL and runs:

- dependency installation from the lockfile;
- Prisma client generation and schema validation;
- the Vitest suite, which includes MCP transport, scope and credential tests;
- a disposable database reset and seed;
- the RLS verifier;
- the general Playwright suite;
- TypeScript and Vite production build;
- production container build;
- dependency audit.

The general Playwright configuration deliberately excludes the MCP-specific browser spec. The product provides separate runners for the PostgreSQL MCP integration flow and the MCP browser journey.

This distinction matters: the dedicated flows exist and are reviewable in the private repository, but this case does not claim that both run on every main-branch CI execution.

## What these tests do not prove

The evidence supports the authorization and tenant-isolation behavior described in this case. It does not prove:

- performance or reliability at production traffic volume;
- compatibility with every MCP client or model harness;
- absence of all security vulnerabilities;
- resistance to a fully compromised agent environment;
- formal verification of the authorization model;
- independent penetration testing;
- correct human approval outside the protocol's `confirm` field;
- production backup, restore or incident-response readiness;
- safe behavior for future tools that have not yet been added to the scope matrix.

Those are separate validation problems. Keeping them out of this case is preferable to turning existing tests into claims they do not support.
