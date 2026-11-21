# Universal Tool Page Template (Blueprint)

Use this exact structure for every new tool page. Replace every `{placeholder}`. Write all content in English. Every section must contain information specific to this tool. Do not reuse sentences from other tool pages.

---

## PAGE STRUCTURE (in this exact order)

```
1. H1: Tool name
2. Direct answer (40-43 words)
3. Tool body (the working tool)
4. About {Tool Name}
   4.1 What is {Topic}?
   4.2 How to use {Tool Name}
   4.3 Example
   4.4 Features
   4.5 Use cases
   4.6 Common mistakes and limits
   4.7 Frequently asked questions
5. Related tools
```

---

## 1. H1: TOOL NAME

```
# {Tool Name}
```

Rules:
- One H1 only.
- Use the primary search keyword in natural form.
- Maximum 6 words.

---

## 2. DIRECT ANSWER (40-43 words)

Write one paragraph directly under the H1.

Instructions:
- Exactly 40 to 43 words. Count them.
- Sentence 1: define the topic or say what the tool does.
- Sentence 2: say what this tool lets the user do and one real differentiator of this tool.
- Must make sense when copied alone as an answer.
- Include the primary keyword once.
- No hype words. No filler. No category name inside the sentence.

Format:

```
{Sentence 1: what the topic is or what the tool does.} {Sentence 2: what the user can do here, with one specific feature.}
```

---

## 3. TOOL BODY

Place the working tool directly after the direct answer. It must be visible without scrolling.

Include:
- Input area (left or top).
- Result area (right or bottom).
- Mode tabs or toggles, only if the tool needs them.
- Option controls with sensible defaults.
- Buttons: Copy, Download (if output is a file or long text), Clear.
- Clear error message for invalid input.
- Placeholder text that shows a real sample input.
- Mobile layout: input above result, buttons full width.

Small line under the tool (only if true):

```
Runs in your browser. Your input is not uploaded.
```

---

## 4. ABOUT {TOOL NAME}

```
## About {Tool Name}
```

Write every subsection below. Keep paragraphs short (2-4 sentences).

### 4.1 What is {Topic}?

```
### What is {Topic}?
```

Instructions:
- 200-400 words.
- Explain the concept the tool is built on, not the website.
- Cover: definition, how it works in simple steps, key terms, important numbers or standards, where it is used.
- Include at least 3 facts that apply only to this topic.
- If you can swap in another tool's name and the text still fits, rewrite it.

### 4.2 How to use {Tool Name}

```
### How to use {Tool Name}
```

Instructions:
- Numbered list, 3 to 6 steps.
- Describe the real buttons, tabs and options of this tool.
- One action per step.
- Last step: how to copy or download the result.

Format:

```
1. {Action}. {One short sentence of detail.}
2. {Action}. {One short sentence of detail.}
3. {Action}. {One short sentence of detail.}
```

### 4.3 Example

```
### Example
```

Instructions:
- Give 1 to 3 real examples.
- Test each example in the actual tool before publishing.
- Show input and output in code blocks.
- Add one edge case example when the tool has one.

Format:

```
**{Example label}**

Input:
{input}

Output:
{output}

{One-line note, optional.}
```

### 4.4 Features

```
### Features
```

Instructions:
- 3 to 7 bullets.
- List only features this tool really has.
- Each bullet: feature name, then one short explanation.

Format:

```
- **{Feature}:** {What it does.}
```

### 4.5 Use cases

```
### When to use {Tool Name}
```

Instructions:
- 3 to 6 real situations.
- Each item: bold title, then 1 to 2 sentences describing the scenario.

Format:

```
- **{Scenario title}:** {What the person is doing and how the tool helps.}
```

### 4.6 Common mistakes and limits

```
### Common mistakes and limits
```

Instructions:
- 2 to 5 common mistakes or edge cases specific to this topic.
- Then list real limits of the tool (input size, unsupported formats, browser limits).

Format:

```
**Common mistakes**
- **{Mistake}:** {How to avoid it.}

**Limits**
- {Limit 1}
- {Limit 2}
```

### 4.7 Frequently asked questions

```
### Frequently asked questions
```

Instructions:
- 4 to 8 questions.
- At least 75% of the questions must be unique to this tool and topic.
- Take questions from Google "People also ask" and real user questions.
- Maximum one generic question (free / privacy / no install), combined into one answer.
- Each answer: 2 to 4 sentences. First sentence answers directly.
- Use each question as an H4 or bold line, followed by the answer.

Format:

```
**{Question?}**
{Direct answer in 2-4 sentences.}
```

---

## 5. RELATED TOOLS

```
## Related tools
```

Instructions:
- 3 to 6 tools.
- Choose tools a person would use right after or alongside this task.
- Do not add unrelated tools.
- Each card: tool name, one-line description (under 15 words), category label.
- Link both ways (if A links to B, B links to A).

Format:

```
- [{Related Tool Name}](/tools/{slug}): {One-line description.}
```

---

## 6. SEO FIELDS (fill for every tool)

```
Title (50-60 chars): {Primary keyword} - {benefit} | Toolpika
Meta description (120-155 chars): {What the user gets. Action. One true differentiator.}
Slug: {primary-keyword-in-kebab-case}
Primary keyword: {keyword}
Secondary keywords: {3-8 real variations}
```

---

## 7. WRITING RULES (apply to all sections)

- Simple, direct English. Short sentences.
- No hype words. No filler sentences.
- Never write the category name inside a sentence.
- Do not repeat the tool name in every sentence. Use "the tool" or "it".
- Every number, example and feature must be correct and verified.
- No unfilled placeholders such as `{`, `}`, `undefined`, `null` in the final page.

---

## 8. FINAL CHECKLIST (before publishing)

- [ ] H1 is the only H1
- [ ] Direct answer is 40-43 words
- [ ] Tool is visible above the fold
- [ ] What-is section is 200+ words with topic-specific facts
- [ ] How-to steps match the real UI
- [ ] Examples tested in the real tool
- [ ] Features list matches the real tool
- [ ] FAQs are tool-specific (75%+ unique)
- [ ] Related tools are relevant and link back
- [ ] Title, meta description and slug filled
- [ ] No category-name leaks, no placeholders left
