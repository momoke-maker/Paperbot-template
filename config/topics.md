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
  Tier 1: Nature, Science, Nature Human Behaviour, PNAS, Psychological Science, JPSP (Journal of
          Personality and Social Psychology), JEP: General, Psychological Bulletin, Psychological Review,
          Management Science
  Tier 2: Science Advances, Nature Communications, PNAS Nexus, Communications Psychology, Nature Machine
          Intelligence, OBHDP, PSPB, JESP, Cognition, JEP: Applied, Journal of Consumer Research,
          Journal of Marketing Research, Organization Science, CHI, CSCW
  Tier 3: Computers in Human Behavior, International Journal of Human-Computer Studies, Journal of
          Behavioral Decision Making, Judgment and Decision Making, Collabra, Royal Society Open Science,
          Scientific Reports, PLOS ONE, other peer-reviewed journals
  Tier 4: strong preprints (PsyArXiv, arXiv, SSRN) — say in the episode it's not yet peer reviewed.
  Write the tier in meta.json ("tier": 1-4).
- Mostly recent (last ~18 months); about once a week a classic/foundational paper.
- Never repeat a paper already covered (check episodes/*/meta.json) and avoid papers listed in
  config/library.md (papers the listener already knows).
- Preprints are OK if clearly strong; say in the episode that it's not yet peer reviewed.
- Full text is required. If the best pick is paywalled, choose another and add the paywalled one to
  config/wishlist.md (title, DOI) so the listener can send the PDF to the bot.
