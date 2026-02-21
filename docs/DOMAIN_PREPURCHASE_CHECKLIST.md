# Domain and Brand Pre-Purchase Checklist

## Scope
Use this checklist before buying and locking domains for `Mindblast`.

## 1) Name and Brand Checks
- Confirm the name can expand beyond one category (not tied to history only).
- Check for confusingly similar names in the same product space.
- Search app stores for close matches.
- Search GitHub for existing projects with the same or very close name.
- Check major social platforms for handle availability.

## 2) Basic Legal Risk Screen
- Run a quick USPTO TESS search for exact and similar marks in software/education classes.
- Run an EUIPO search if you expect EU users.
- Search WIPO Global Brand Database for obvious conflicts.
- Capture screenshots or notes of what you checked and when.
- If anything looks close, get a short legal review before launch branding.

## 3) Domain Selection
- Check availability for `mindblast.app`.
- Check availability for `mindblast.com`.
- Check availability for 1 to 2 fallback domains you would accept.
- Compare registrar renewal pricing, not only first-year promo pricing.
- Compare transfer-out policy, renewal grace period, and redemption fees.
- Prefer registrars with free WHOIS privacy and clear DNS controls.

## 4) Domain Purchase Strategy
- Buy the primary domain first.
- Buy obvious typo or defensive variants if budget allows.
- Use a shared team account or password manager vault for registrar access.
- Enable auto-renew on day one.
- Add a payment method that supports long-term renewal reliability.

## 5) Security and Operations
- Enable registrar account MFA before DNS changes.
- Lock domain transfer where possible.
- Set registrar lock and keep recovery contacts up to date.
- Document domain ownership details in internal docs.
- Set calendar reminders 30 and 7 days before renewal.

## 6) DNS and Launch Readiness
- Choose authoritative DNS provider (Cloudflare or registrar DNS).
- Create `A`/`AAAA` for root if needed.
- Create `CNAME` for `www`.
- Create `MX` only if email is required.
- Create `TXT` for SPF/verification as needed.
- If using `.app`, remember HTTPS is effectively mandatory due to HSTS.
- Test DNS propagation and TLS certificates before public launch.

## 7) Project Documentation Updates
- Confirm docs use the project name `Mindblast`.
- Confirm docs use the user-facing app name `Mindblast`.
- Update docs with the primary domain.
- Update docs with fallback domain(s).
- Update repo README and CI environment variables to use final base URL.

## 8) Go/No-Go Gate
- GO if no obvious legal conflicts are found in quick screens.
- GO if the primary domain is purchased and secured.
- GO if social handles are reserved.
- GO if DNS and HTTPS are validated.
- NO-GO if a strong trademark conflict appears in your target category.
- NO-GO if domain ownership/security setup is incomplete.
