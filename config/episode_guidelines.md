# How to write an episode script (used by the daily Claude task AND the on-demand Gemini writer)

Listener: a researcher who wants the METHOD in detail, not a pop-science summary. config/listener.md
gives their name, how to address them and the episode language. Their field and research are used ONLY
to choose papers: NEVER mention the listener's field, research or interests in an episode, and never
suggest connections to their work. The episode is a review of the paper as it is, nothing else.

## Format
- Language: as set in config/listener.md (Hebrew or English). Two hosts: Maya (speaker "A", female)
  and Daniel (speaker "B", male). Correct gendered verb
  forms for each host; address the listener by name and gender exactly as given in config/listener.md.
- A natural, coherent conversation between two knowledgeable researchers. Let it flow the way a real
  conversation would; don't force questions or interruptions where they aren't needed. Sharp and focused.
- Tone: calm, clear, informative. No superlatives or drama ("מדהים", "מטורף", "הדרמה האמיתית" etc.),
  no hype (in English: no "mind-blowing", "incredible" etc.). State things as they are.
- Length: 12–16 minutes ≈ 1,900–2,400 words.
- In Hebrew: no niqqud; keep established English terms in English where researchers would
  (e.g. "self-serving bias", "between-subjects", "Prolific", "effect size") and explain each once.
- Numbers must be speakable, e.g. "about eight hundred participants", "a d of 0.4", "p below 0.001"
  ("בערך שמונה מאות משתתפים", "d של 0.4", "p קטן מ-0.001").

## Structure (cover all of it)
1. Opening (2–3 lines): the paper's question and why it matters, in the paper's own terms.
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
9. One-sentence takeaway, short sign-off.

## Accuracy rules
- Everything comes from the paper's full text. Never invent numbers, items, or details.
  If a detail is not reported, say so.
- Interpretation must come from the paper (the authors' rationale, theory and discussion). Do not invent
  explanations. The hosts' own critique belongs only in the critical-look part and is
  clearly framed as such.

## Output files
episodes/<YYYY-MM-DD>[-suffix]/script.json:
{"lines": [{"s": "A"|"B", "text": "..."}]}   (voices are added automatically for the episode language)
episodes/<...>/meta.json:
{"title": "<original title>", "title_short": "<short title in the episode language>", "authors": "First Author et al.",
 "journal": "...", "year": 2026, "doi": "...", "link": "https://doi.org/...",
 "summary": "<3 short lines in the episode language: question, method, main finding>", "topics": ["..."],
 "source": "daily" | "request"}
