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

## Markdown formatting convention

When bold text (`**word**`) is immediately followed by a Korean particle/postposition, insert a space before the particle to avoid rendering breakage, e.g. `**단어** 다` (not `**단어**다`).

# Wiki operating rules

1. Start at `03_MOC/index.md`.
2. Search `02_WIKI` for a seed note.
3. Follow only relevant links.
4. Verify claims in `01_RAWS`.
5. Separate facts from inference.
6. List notes and sources used.