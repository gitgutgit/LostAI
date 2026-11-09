# MOAI design concepts: text pack for external model tests (2026-11-09 10:22)

> 쓰는 법(Eric용 메모): 아래 블록을 ChatGPT, Gemini 등에 그대로 붙여 넣는다. A절은 맥락 없는 판독용이라 **새 대화에서, 다른 블록 없이** 하나씩 붙인다(제품 설명이 먼저 들어가면 판독이 오염된다). B절은 맥락을 준 뒤 그려 보게 하는 생성용이다. 답은 이 파일 맨 아래 C절 표에 모델 이름과 함께 붙여 두면 우리 `claude -p` 결과(/Users/eric.j.park/Documents/GitHub/meeting-agent-poc/design/brand/judge_backronym/out/)와 나란히 비교할 수 있다.
> 시안 그림: /Users/eric.j.park/Documents/GitHub/meeting-agent-poc/design/brand/logo/png/sheet_v1.png , /Users/eric.j.park/Documents/GitHub/meeting-agent-poc/design/brand/logo/png/_check_favicon.png (외부 모델에 그림을 같이 올려도 된다. 단 A절에는 올리지 않는다)

---

## A. Blind judge prompts (paste each into a NEW chat, alone)

### A1. Backronym judge (repeat once per expansion, 3 new chats each)

```
A team is naming a new software product. The name is MOAI. The letters stand for: "<EXPANSION>".
Answer in English, in exactly 3 lines, no other text:
1. In one sentence, what do you think this product does?
2. Corporate-jargon smell, from 1 (playful, human) to 5 (sounds like enterprise business jargon). Give only the number.
3. Would you still remember what the letters stand for after hearing it once in a 2-minute video? Answer yes or no.
```

Expansions to test (swap into <EXPANSION>):

```
Mostly Observes, Asks Instead
Meet, Object, Agree, Ink
Mumble, Object, Agree, Ink
Many Opinions, Agreed In ink
Mouths Open, Answers Inked
My Objection, Acknowledged, Inked
Make Our Arguments Ink
Mark Our Agreements Inline
Mouths, Opinions, Ayes, Ink
Minority Opens, All In
Mic On, Arguments Inked
Many Opinions, AI Inks
Mouths Open, AI Inks
Moments Of Agreement, Inked
Mull, Object, Agree, Ink
Maximize Operational Alignment Insights   (control: deliberately corporate, should score 4 or 5)
```

### A2. Spelling from sound

```
You heard a new app name spoken aloud once in a video. It sounded like "MOH-eye". How would you spell it? Give only your single best spelling, nothing else.
```

### A3. Word association

```
What does the word "Moai" make you think of? Answer in one line.
```

### A4. Logo-only read (attach ONE logo image, no name, no text)

```
This is a logo for a new software product. Without guessing a brand name, answer in 2 lines:
1. In one sentence, what do you think this product does?
2. What is the figure in the logo, and what mood does it give (one or two words)?
```

### A5. Name plus logo read (attach the wordmark image)

```
This is the name and logo of a new software product. Answer in one sentence: what do you think this product does?
```

---

## B. Concept descriptions (context given; for generation or critique)

### B0. Product brief (paste first in a generation chat)

```
Product: MOAI, a meeting agent.
One line: "It writes the doc while you talk. When the room disagrees, it stops writing and makes the room decide."
What it does:
- During a meeting it edits the team's existing document (a project plan sheet) live from what people say.
- Every edited cell shows who said it and which transcript line, and can be undone.
- When two people's instructions conflict, it stops writing and opens a question.
- The room decides by a simultaneous hand vote (thumb up, palm, finger count). The minority speaks first. The agent restates their reason.
- The agent never recommends an option. It only shows each option's cost, computed from the team's plan.
- The decision is written back into the doc and dependent cells recompute.
Not this: a post-meeting summarizer (Otter, Granola, Fireflies, Circleback). It works inside the meeting.
Audience: hackathon judges, English speakers, who will see a 2-minute video once.
Visual system (from the product screens):
- Colors by screen area: white #FFFFFF 47%, grey-green wall #CDD6D0 16%, navy #1D2733 15% (full-screen vote reveal), yellow #F3C316 8% (conflicts, highlights, transcript-line chips), ink #17212B 4% (text). Green is almost unused.
- Fonts: Barlow Condensed 700 for headings, Atkinson Hyperlegible for body.
- Style: flat, pictogram, no gradients, no human faces that show race or gender.
```

### B1. App icon and favicon mark

```
Concept: a front-view Moai (Easter Island stone head) pictogram as the app mark.
Shape on a 64 x 64 grid: tall rectangular head (x 20 to 44, y 4 to 48), long ears as two thin vertical bars on both sides, a trapezoid of shoulders at the bottom.
Face is cut out of the solid shape: a T made of the brow bar and the long nose, plus one short mouth bar.
For 16 px, every stroke sits on a 4-unit grid so each stroke is exactly 1 pixel.
Color versions: ink #17212B figure on yellow #F3C316 tile; white figure on navy #1D2733 tile; one-color black.
Why a Moai: it does not speak (the agent never talks out loud), it has long ears (its job is listening), it is not a person (no race or gender), and Moai stand in a row (like meeting participants).
Task: critique this mark at 16, 32 and 512 px, or draw 3 variations that keep it readable at 16 px.
```

### B2. Wordmark W1, "AI" inside the name

```
Concept: the word MOAI in Barlow Condensed 700, all caps. "MO" in ink #17212B, "AI" in ink on a yellow #F3C316 block, the same highlight style the product uses for transcript-line chips.
Idea: the name already contains "AI"; the highlight shows it without adding a word.
Task: critique, or draw variations of letter spacing and block shape.
```

### B3. Wordmark W2, the last "I" is the statue

```
Concept: MOA in Barlow Condensed 700, and the final "I" is replaced by the tall Moai mark (B1). The Moai's tall narrow body reads as the letter I.
Versions: ink on white, white on navy #1D2733.
Task: critique legibility (does it still read as MOAI?), or draw variations.
```

### B4. Wordmark W3, vertical acrostic for the end card

```
Concept: M, O, A, I stacked vertically in bold, each followed by the rest of a word in medium weight, for the video's end card.
Current text: Meet / Object / Agree / Ink (the product's flow: people meet, someone objects, the room agrees, the agent writes it in).
Task: suggest which expansion reads best stacked, keeping it human and not corporate.
```

### B5. Mascot with five states (face changes only brows, eyes, mouth)

```
Concept: the Moai mark is also the agent's mascot. One fixed head; only brows, eyes and mouth change, one state per product state:
1. Listening: neutral, flat brows, open eyes. Default, says nothing.
2. Writing: eyes lowered to the document.
3. Paused, conflict detected: one brow raised, shown in yellow #F3C316; it stops writing.
4. Vote in progress: eyes shut. It does not look and does not recommend.
5. Decided: one nod (small forward tilt) and content eyes, then it writes the decision back.
Rules: pictogram, ink #17212B on white or wall #CDD6D0; expressions only from 32 px up; at 16 px only the silhouette and T face.
Cultural note: Moai are sacred ancestor figures for the Rapa Nui people; never show the mascot falling, broken, or as a joke prop.
Task: critique whether each state is readable at 64 px and distinct from the others, or draw the five states.
```

### B6. Name rationale (for critique of the name itself)

```
Name: MOAI (pronounced MOH-eye).
Origins: Korean pun "moa" = gather (ideas gathered together); Okinawan "moai" = a lifelong mutual-support group; the Easter Island statues that silently watch.
Risks we know: English speakers may first think of the stone-head emoji used as a deadpan meme; Korean pun is lost on English speakers; mo.ai and moai.ai domains are already registered by others.
Task: as an English-speaking startup judge, say in 3 bullet points what the name makes you expect, and one risk we missed.
```

---

## C. External results (paste answers here)

| Prompt | Model | Run | Answer (verbatim) |
|---|---|---|---|
| | | | |
