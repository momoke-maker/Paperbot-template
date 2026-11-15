# Paper selection — what the daily episode should be about (fill this in)

Core area (1–2 lines): <<e.g. human–AI interaction from a psychological angle: judgment, trust, morality>>

Topics (rotate between them; don't stay on one topic more than 2 days in a row):
- <<topic 1, e.g. trust in AI advice and automation bias>>
- <<topic 2>>
- <<topic 3>>
- <<add as many as you like>>

Selection rules:
- Prefer empirical papers (experiments, field studies, well-designed surveys) with a clear method.
- VENUE PRIORITY (strict, tier by tier). Among papers that fit the topics well and have full text,
  always pick from the highest tier available. Search tier 1 first (use Undermind journal_contains
  filters per journal); go down a tier only if tier 1 has no suitable, not-yet-covered paper.
  Basis (checked Nov 2026): SCImago SJR 2024/2025 values plus expert-curated lists (FT50, Chartered ABS
  AJG 2024, CORE conference ranking). SJR alone is not used because it underrates some flagships
  (e.g. Psychological Science 2.5, JEP: General 1.9) relative to high-volume journals.
  Tier 1 — flagship / top-ranked:
          Nature, Science (SJR 10.4), Nature Human Behaviour (SJR 4.9; AJG 4), Science Advances (SJR 4.3),
          PNAS (SJR 3.3), JPSP (SJR 3.9), Psychological Science (SJR 2.5; FT50),
          Management Science (SJR 5.7), OBHDP (SJR 2.4–3.2), CHI (CORE A*)
  Tier 2 — strong, field-leading:
          JEP: General (SJR 1.9), PSPB (SJR 2.2), Cognition (SJR 1.7), Computers in Human Behavior
          (SJR 3.1, high-volume), CSCW (CORE A), Nature Communications, PNAS Nexus, Communications
          Psychology, JESP, Journal of Consumer Research, Journal of Marketing Research
          (the last six placed by reputation; values not verified)
  Tier 3 — solid peer-reviewed:
          Journal of Behavioral Decision Making (SJR 0.85), Judgment and Decision Making (SJR ~1.1),
          International Journal of Human-Computer Interaction (SJR 1.4), Collabra, Royal Society Open
          Science, Scientific Reports, PLOS ONE, other peer-reviewed journals
  Tier 4: strong preprints (PsyArXiv, arXiv, SSRN) — say in the episode it's not yet peer reviewed.
  Reviews and theory papers (Psychological Bulletin, Psychological Review, PSPR, Annual Review of
  Psychology) are top-ranked but not empirical: use them only for the weekly "classic" episode.
  Write the tier in meta.json ("tier": 1-4).
- Mostly recent (last ~18 months); about once a week a classic/foundational paper.
- Never repeat a paper already covered (check episodes/*/meta.json) and avoid papers listed in
  config/library.md (papers the listener already knows).
- Preprints are OK if clearly strong; say in the episode that it's not yet peer reviewed.
- Full text is required. If the best pick is paywalled, choose another and add the paywalled one to
  config/wishlist.md (title, DOI) so the listener can send the PDF to the bot.
