# Content Compliance Policy

Last reviewed: 2026-02-24 (UTC)

## Purpose
Set non-negotiable rules for content sourcing and media usage in Mindblast to minimize legal and platform-policy risk for this hobby project.

This policy is intentionally conservative: if rights are not clear, we do not ship.

## Core Rules

1. No ambiguous rights.
   - Every source must have explicit terms/license compatible with intended usage.
2. Fail closed.
   - If license terms are unclear or conflicting, block the feature/source.
3. No "short clip" shortcut.
   - Do not assume brief excerpts are safe by default.
4. Platform terms are binding.
   - If an API/SDK policy disallows quiz/game usage patterns, do not implement those patterns.
5. Documentation required before rollout.
   - Record source terms URL, review date, usage obligations, and risk level.
6. No fabricated attribution.
   - AI-generated text/content must never be presented as if it came from a real third-party source.
   - If content is synthetic, it must be explicitly labeled as synthetic in data and UI.

## Approved Source Posture (Current)

- Preferred: CC0/public-domain or first-party owned/commissioned content.
- Conditional: CC BY / CC BY-SA only when attribution/share-alike obligations are implemented and tracked.
- Not allowed by default: scraped content, unclear-provenance datasets, or content with non-commercial restrictions for a production-facing path.

## Music Quiz Policy (Current)

Status: **Blocked by default for commercial music catalogs**.

Allowed now:
- Original/commissioned tracks where Mindblast has documented rights.
- Public-domain or permissive-licensed music (for example CC0; CC BY only with attribution implementation).

Not allowed now:
- "Play short commercial clip and guess" based on fair-use assumptions.
- Spotify-powered quiz gameplay/content usage that conflicts with Spotify policy.
- YouTube content extraction/isolation patterns that violate YouTube developer policies.
- Any catalog ingestion or playback flow without explicit rights for the intended use.

## Synthetic/AI-Generated Content Policy

Status: **Allowed for internal experimentation with strict labeling and provenance controls**.

Required:
- Clearly mark synthetic content in machine-readable fields and user-visible UI.
- Keep provenance explicit (provider/model/date/version where applicable).
- Keep synthetic entries separate from sourced attribution lists.
- Ensure synthetic entries do not include fake citation URLs.

Not allowed:
- Presenting generated distractors as sourced facts when they are not.
- Inventing or inferring source links to make synthetic content appear authoritative.
- Using ambiguous wording that hides whether an item is sourced or generated.

## Platform-Specific Guardrails (Music)

- Spotify:
  - Spotify Developer Policy states developers may not create games, including trivia quizzes, with Spotify content.
- Apple Music:
  - MusicKit usage requires compliance with Apple agreements and usage limits. Do not ship quiz clip mechanics without explicit policy/legal clearance.
- YouTube:
  - Do not implement flows that isolate/extract audio/video components outside allowed player/API behavior.

## Implementation Checklist For Any New Content Source

1. Identify intended uses:
   - display, playback, remix, training, redistribution, caching.
2. Capture primary terms URL and review date.
3. Confirm rights per use:
   - direct app use,
   - model training/fine-tuning,
   - commercial use,
   - redistribution.
4. Capture operational obligations:
   - attribution text/links,
   - share-alike duties,
   - rate limits,
   - storage/caching restrictions.
5. Assign risk level in `docs/QUIZ_CONTENT_SOURCES.md`:
   - Green / Yellow / Red.
6. Block release if any obligation is unimplemented.

## Enforcement For Agents

- Before adding new sources/features, update docs first if policy/contract changes.
- If a task requests policy-breaking behavior, propose compliant alternatives and stop short of implementation.

## References

- US Copyright Office fair use FAQ: https://www.copyright.gov/help/faq/faq-fairuse.html
- Spotify Developer Policy: https://developer.spotify.com/policy
- Spotify Developer compliance tips: https://developer.spotify.com/compliance-tips
- Apple Developer Program License Agreement: https://developer.apple.com/support/downloads/terms/apple-developer-program/Apple-Developer-Program-License-Agreement-English.pdf
- Apple MusicKit overview: https://developer.apple.com/musickit/
- YouTube Developer Policies: https://developers.google.com/youtube/terms/developer-policies
