# MARE Product Roadmap

Use this file when the goal is to reason about what MARE should solve next, not only what exists today.

## Current thesis

MARE should become the fastest way to get a trustworthy answer from a document or folder of documents, with proof.

Best sharper product sentence:

- MARE should become the fastest way to ask a question over a folder of documents and get a trustworthy answer with exact proof.

The product should stay centered on:

- grounded answers
- visible evidence
- inspectable proof
- lightweight document work

Do not let the roadmap drift toward:

- generic chatbot behavior
- model-chasing without retrieval gains
- broad agent complexity before trust is strong

## What MARE is already solving

Today MARE already solves a meaningful first slice:

- ingest a PDF or mixed local documents
- retrieve relevant pages and objects
- show snippet, citation, and visual proof when available
- support simple document work like review, compare, summary, findings extraction, and steps
- expose the same grounded evidence engine to humans and agents

That means the roadmap should mostly strengthen usefulness, trust, and retrieval quality rather than invent a new core.

## Best direction now

If choosing the single best direction for making the product feel both "wow" and genuinely useful, prefer this:

- better evidence retrieval
- tighter proof presentation
- stronger real document-work tasks

Important product guidance:

- do not optimize first for "more AI"
- optimize first for better evidence, better proof, and better usefulness
- the magic moment should be: the system found the right answer and showed exactly why it is true

Why this direction is strongest:

- stronger retrieval improves every surface
- tighter proof creates trust and delight
- document-work tasks turn retrieval into repeatable value
- folder-level usefulness is more valuable than single-file novelty

## What creates the wow

The product should feel impressive when it can do all of the following in one flow:

- find the right answer quickly
- point to the exact supporting page, region, snippet, or object
- explain why that evidence was chosen
- help the user do something concrete with the document set

The "wow" should come from grounded usefulness, not generic generation.

## Must-have next

These are the highest-leverage improvements for the product right now.

### 1. Stronger retrieval quality

Goal:

- improve answer recall without losing inspectable evidence

Focus:

- make hybrid semantic + lexical retrieval easier to use for real documents
- improve default reranking quality for top-1 evidence
- strengthen retrieval when user wording differs from document wording
- improve multi-document retrieval when evidence is spread across files

Why it matters:

- better retrieval lifts every surface: UI, chat, workflow, MCP, and integrations
- this is the highest-leverage path for improving the whole product

### 2. Better evidence precision

Goal:

- make the proof feel tighter and more trustworthy

Focus:

- more precise text-span highlighting
- stronger object-region proof for tables, figures, and sections
- better snippet selection
- clearer evidence ranking explanations
- stronger non-PDF citation quality

Why it matters:

- users trust the system more when the proof is specific, not approximate
- this is a major source of the product's "wow" factor

### 3. Better first-run clarity

Goal:

- help users understand the product in seconds

Focus:

- sharpen the `mare ui` first-run story
- make folder-first usage more obvious
- explain the evidence model simply
- reduce stack and parser confusion in the default path

Why it matters:

- a strong engine is not enough if users do not quickly understand what MARE is good at

Current status:

- the first guided onboarding slice now exists through `mare start` plus a stronger UI first-run state
- next work should make the onboarding feel even more outcome-specific, not re-invent the basic start flow

### 4. Stronger document-work tasks

Goal:

- make MARE useful for small real jobs, not only Q&A

Focus:

- stronger `review` mode
- better `:compare`
- better `:steps`
- stronger grounded summaries
- extract requirements, actions, deadlines, and risks
- answer conservatively when support is weak or missing

Why it matters:

- this is how MARE grows from retrieval into a real document evidence agent

Important examples of high-value tasks:

- compare two documents or versions
- assemble a grounded review for an operational or policy question
- extract steps or procedures
- summarize only what is supported by evidence
- pull out requirements, risks, deadlines, and actions
- detect when support is weak or missing

Current status:

- the first release-worthy grounded extraction slice is now present across chat, workflow, UI, and shared payloads
- the next iteration should improve the quality and specificity of those extracted findings rather than re-adding the same categories

## High-impact later

These are likely important, but should come after the must-have slice is solid.

### 5. Layout and visual evidence upgrades

Goal:

- make document proof stronger for scanned, structured, and visually rich documents

Focus:

- richer OCR and layout-aware parsing
- stronger table extraction
- figure and caption linkage
- section-aware region grounding
- better visual proof for camera-captured or scanned pages

Why it matters:

- this is where MARE can become much more differentiated than plain text RAG tools

### 6. Collections and operational workflows

Goal:

- make MARE valuable across folders and document sets, not just individual files

Focus:

- better cross-document comparison
- document-level filtering and grouping
- version/change detection
- contradiction or conflict detection across sources
- per-document evidence breakdowns
- multi-document review packs that explain where evidence agrees or diverges

Why it matters:

- many real user problems live at the folder or corpus level
- this is one of the clearest ways to move beyond "chat with one PDF"

### 7. Optional local intelligence

Goal:

- support privacy-sensitive and local-first usage without changing the evidence-first product shape

Focus:

- Ollama-backed local generation
- local embedding options
- clean switching between hosted and local inference

Why it matters:

- local/private workflows can widen adoption without changing the core product promise

Important nuance:

- treat local inference as optional infrastructure, not the product itself
- prefer retrieval and evidence quality wins before model fine-tuning

## Nice-to-have experiments

These are worth exploring only after the core trust loop is stronger.

- query rewriting for vague user questions
- evidence confidence or support-strength scoring
- answer drafting styles for different surfaces
- guided workflows for specific document domains
- lightweight proactive suggestions after retrieval
- richer review templates for contracts, SOPs, onboarding packets, and policy docs

## Practical prioritization

If choosing only a small number of bets, favor this order:

1. stronger retrieval quality
2. better evidence precision
3. better first-run clarity
4. stronger document-work tasks
5. visual/layout upgrades
6. collections and corpus workflows
7. optional local inference

Equivalent simple wording:

1. make retrieval smarter by default
2. make proof tighter and clearer
3. make document-work flows stronger
4. make folder workflows first-class
5. deepen visual/layout evidence

## RAG guidance

When discussing whether MARE needs "RAG," preserve this framing:

- MARE already has an evidence-first retrieval system
- the useful question is how much semantic retrieval, reranking, and layout grounding to add
- do not describe the product as needing retrieval from scratch

Best current framing:

- strengthen MARE into a hybrid evidence engine
- keep generation downstream of evidence
- make proof better, tighter, and easier to inspect

## Product north star

The best simple test for roadmap choices is:

- does this help MARE return a more trustworthy answer with clearer proof from one document or a folder of documents?

If yes, it is probably aligned.
If not, it is probably secondary for now.

Another useful test:

- does this make MARE better at answer plus proof plus useful document work?

If yes, it is likely a strong product bet.
