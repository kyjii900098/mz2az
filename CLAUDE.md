# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This is not a software project — it is an Obsidian vault used as a personal knowledge-management (PKM) system. The content (mostly Korean) documents **SceneTrip**, a K-content filming-location travel app being pitched by team **mz2az** for the AI·SW Maestro 17th cohort. There is no build/lint/test tooling; "operating" this repo means reading and writing markdown notes according to the pipeline below.

## Wiki operating rules

1. Start at `03_MOC/index.md` (the map-of-content entry point).
2. Search `02_Wiki` for a seed note relevant to the question.
3. Follow only wikilinks (`[[...]]`) that are actually relevant — don't wander.
4. Verify any factual claim against its source in `01_Raw` before treating it as ground truth.
5. Keep facts (grounded in `01_Raw`) separate from inference/analysis in your answers.
6. When answering, list which notes and raw sources were used.

## Folder pipeline

Notes flow one direction: `01_Raw` → `02_Wiki` → `03_MOC`. `00_Inbox` holds the prompt templates that define this pipeline (see `00_Inbox/LLM Wiki.md`) plus any newly-dropped material awaiting triage.

- **`01_Raw/`** — Lossless, unedited transcriptions of source documents (PDFs, decks) plus the original files. Never summarize or interpret here; content must be verbatim, with `## p{n}` headings marking page/slide breaks. This is the only place claims can be verified against.
- **`02_Wiki/`** — Atomic notes: one concept per note (~300–500 characters of body text), each grounded only in `01_Raw` (no invented content). Standard frontmatter:
  ```yaml
  ---
  title: "..."
  type: concept
  status: draft | stable
  source: "[[raw file name]]"
  related: ["other concept", ...]
  ---
  ```
  Body starts with a `> [!summary]` one-line definition, followed by a `### 상세 내용` section. Uncertain/unverified content is flagged inline with `> [!question] 확인 필요` rather than guessed at.
- **`03_MOC/`** — `index.md` is the single entry point: topic headings (`##`) each containing an alphabetically-sorted list of wikilinks only — no prose, no descriptions. (Not yet created as of this writing; build it from the `02_Wiki` note titles when needed, following the template in `00_Inbox/LLM Wiki.md`.)

## Note lifecycle

A note is promoted from draft to stable in three steps: (1) hallucination check against `01_Raw`, (2) resolve or delete each `[!question] 확인 필요` callout, (3) flip `status: draft` → `status: stable`. Only stable notes belong in `02_Wiki`.

## JiraDocs

`JiraDocs/` is the record of deliverables per Jira story/task. The single source of truth for its format and procedure is `JiraDocs/JiraDocs.md` — when asked to create or update a JiraDocs document (e.g. "JiraDocs 스토리 MZ2AZ-NNN 작성해줘"), read that file first and follow it exactly. The `jiradocs` skill (`.claude/skills/jiradocs/`) triggers this automatically.

## Writing for the reader

These rules apply to everything written for a human — chat answers, `02_Wiki` notes, `JiraDocs` documents, meeting notes. Compression that saves the writer time but costs the reader a second pass is a net loss; err toward one more sentence.

1. **Name the subject.** Every sentence should make clear *who or what* is doing the thing. Korean drops subjects easily, so re-read each sentence and ask "이게 누구/무엇 얘기지?" — if the answer comes from the previous sentence rather than this one, write it out. e.g. "저장 후 검증한다" → "서버가 저장한 뒤 클라이언트가 응답을 검증한다".
2. **Unpack stacked nouns.** Do not chain three or more nouns into one phrase ("추천 파이프라인 캐시 무효화 정책"). Break it into a sentence with a verb: "추천 파이프라인의 캐시를 언제 비울지 정하는 규칙".
3. **Explain a term the first time it appears.** Abbreviations, internal names, and library/API names get a short gloss on first use in each document — "PostGIS(공간 데이터를 다루는 PostgreSQL 확장)". Afterwards the bare term is fine. If a plain Korean word says the same thing, use the plain word instead of the jargon.
4. **Prefer a full sentence to a fragment.** Bullet lists and tables carry facts but not reasoning. Put a sentence before or after them saying what the list means and why it matters — never end a section with a bare table.
5. **Say why, not only what.** When recording a decision or a change, add the reason in the same breath: "A를 골랐다" 대신 "B는 좌표 검색이 느려서 A를 골랐다".
6. **Keep sentences short and one-idea.** If a sentence has two `그리고`/`~하고` joints, split it.

Tone stays as it is today: chat answers are conversational and explanatory, while note bodies keep the vault's plain declarative style (`~다`). Applying these rules should make note bodies clearer, not chattier.

## Markdown formatting convention

When bold text (`**word**`) is immediately followed by a Korean particle/postposition, insert a space before the particle to avoid rendering breakage, e.g. `**단어** 다` (not `**단어**다`).