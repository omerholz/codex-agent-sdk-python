# Documentation

- `CONTRIBUTING.md`: contributor setup and workflow
- `RELEASE.md`: build and publish steps

## Inspiration

This SDK is inspired by the Claude Agent SDK for Python, particularly its subprocess
transport and streaming JSON protocol patterns.

## Schema Tooling

This repo includes schema tooling to help detect upstream protocol changes:

- Generate schema: `codex-agent-sdk schema generate --out ./codex-schema`
- Diff against baseline: `codex-agent-sdk schema diff --baseline ./codex-schema`
- CI guardrail: `codex-agent-sdk schema check-breaking --baseline ./codex-schema`
