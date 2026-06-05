# Security Policy

## Supported Versions

We provide security fixes for the following versions:

| Version | Supported |
|---------|-----------|
| 1.x     | ✅        |

Older versions do not receive security updates. Please upgrade to the latest release.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a vulnerability, report it privately by emailing:

**iglesias@ifca.es**

Include as much of the following as possible:

- A description of the vulnerability and its potential impact.
- The affected version(s).
- Steps to reproduce or a proof-of-concept.
- Any suggested fix, if you have one.

You will receive an acknowledgement within **3 business days**. We aim to provide a resolution timeline within **14 days** of the initial report. We will keep you informed throughout the process.

## Disclosure Policy

We follow a coordinated disclosure model:

1. You report the vulnerability privately.
2. We confirm the issue and work on a fix.
3. We release the fix and publish a security advisory.
4. You may disclose publicly after the advisory is published, or after 90 days from the initial report — whichever comes first.

We will credit reporters in the advisory unless you prefer to remain anonymous.

## Scope

This policy applies to the `wattnet-storage` library and the Docker Compose stack in this repository. Vulnerabilities in third-party dependencies (ClickHouse, Grafana, etc.) should be reported directly to those projects.
