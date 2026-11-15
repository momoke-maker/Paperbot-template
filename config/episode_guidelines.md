# How to write an episode script (used by the daily Claude task AND the on-demand Gemini writer)

Listener: described in config/listener.md (name, field, research interests, how to address them).
The listener is a researcher: they want the METHOD in detail, not a pop-science summary.

## Format
- Hebrew, two hosts: Maya (speaker "A", female) and Daniel (speaker "B", male). Correct gendered verb
  forms for each host; address the listener by name and gender exactly as given in config/listener.md.
- A natural, coherent conversation between two knowledgeable researchers. Let it flow the way a real
  conversation would; don't force questions or interruptions where they aren't needed. Sharp and focused.
- Tone: calm, clear, informative. No superlatives or drama ("מדהים", "מטורף", "הדרמה האמיתית" etc.),
  no hype. State things as they are.
- Length: 12–16 minutes ≈ 1,900–2,400 Hebrew words.
- Hebrew without niqqud. Keep established English terms in English where researchers would
  (e.g. "self-serving bias", "between-subjects", "Prolific", "effect size"); explain each once.
- Numbers must be speakable: "בערך שמונה מאות משתתפים", "d של 0.4", "p קטן מ-0.001".

## Structure (cover all of it)
1. Hook (2–3 lines): the question and why it matters for the listener's field and interests.
2. The paper: authors, journal, year (say it once, naturally).
3. Background & theory (give it real room, ~2–3 minutes): explain the theoretical mechanism the paper
   builds on — not just names. What the key prior work showed and how; why the theory predicts what the
   authors hypothesise; the gap this paper fills. Use the theories and citations the paper itself uses.
4. Research questions & hypotheses — stated precisely.
5. METHOD, for each study (the heart of the episode — spend the most time here):
   participants (N, population, platform, exclusions), design (between/within, conditions),
   the exact manipulation (what participants saw/did, wording of key instructions or AI outputs),
   every main measure (construct, scale name, number of items, an example item, response scale),
   procedure step by step, and any pre-registration / power analysis.
6. RESULTS: main effects with the actual numbers (means, effect sizes, CIs/p), mediation/moderation,
   robustness checks, anything surprising. Say which hypotheses were supported.
   After each key result, briefly say what it means: connect it back to the theory/hypothesis using the
   authors' own rationale. Do this where it adds understanding, not as a ritual after every number.
7. Discussion — cover it properly, as the authors present it: their main conclusions and the important
   distinctions they draw, the theoretical contribution, practical implications/recommendations, and
   noteworthy additional or supplementary findings and null results they report.
8. Critical look: limitations, alternative explanations, measurement issues, generalisability.
9. Connection: open questions, and 1–2 ideas for how this could inform the listener's own research
   (see config/listener.md; keep it brief, framed as ideas).
10. One-sentence takeaway, short sign-off.

## Accuracy rules
- Everything comes from the paper's full text. Never invent numbers, items, or details.
  If a detail is not reported, say so ("הם לא מדווחים על...").
- Interpretation must come from the paper (the authors' rationale, theory and discussion). Do not invent
  explanations. The hosts' own critique and ideas belong only in the critical-look/connection parts and
  are clearly framed as such.

## Output files
episodes/<YYYY-MM-DD>[-suffix]/script.json:
{"speakers": <copy DEFAULT_SPEAKERS from scripts/make_episode.py>, "lines": [{"s": "A"|"B", "text": "..."}]}
episodes/<...>/meta.json:
{"title": "<English title>", "title_he": "<short Hebrew title>", "authors": "First Author et al.",
 "journal": "...", "year": 2026, "doi": "...", "link": "https://doi.org/...",
 "summary_he": "<3 short lines in Hebrew: question, method, main finding>", "topics": ["..."],
 "source": "daily" | "request"}
