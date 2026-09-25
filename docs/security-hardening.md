# Security hardening checklist

## Implemented in the local profile

- Scrypt password hashing with per-password salts.
- JWT access tokens with short expiry and server-side logout revocation.
- Backend role checks for every mutation and oversight endpoint.
- Pydantic input validation, upload extension/size checks, and managed storage-root checks.
- CORS restricted to local frontend origins.
- Security headers: frame denial, MIME sniffing protection, referrer policy, permissions policy, and CSP.
- In-process login rate limiting for the single-process Windows profile.
- Append-oriented audit service with no public update/delete route.
- Synthetic development credentials isolated in `.env.example`.

## Required before shared deployment

- Replace the in-memory rate limiter with a shared store.
- Use HttpOnly/Secure/SameSite cookies or a managed session service instead of localStorage bearer tokens.
- Set a strong `CNI_JWT_SECRET` through a secret manager; never commit `.env`.
- Enforce HTTPS, HSTS, secure reverse-proxy headers, and database TLS.
- Give the application database user insert/select-only permissions on the audit table in production.
- Add malware scanning, file-content validation, and quarantine for uploads.
- Add dependency/SAST/secret scanning to CI.
- Define backup encryption, restore testing, retention, legal hold, and deletion workflows.
- Add MFA/SSO, session management, and account lockout policy.
- Run an external penetration test and threat-model review.

## Windows notes

Use PowerShell and Windows service managers for the native profile. Docker is optional and should not be treated as a security boundary by itself.
