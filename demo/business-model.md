# Business model: your AI, your data

Pitch material, not a plan we're building this weekend. The one-line version:

> **Dialectic is free and open for any class. Institutions pay to run it on their own servers and their own AI, integrated with their LMS, so student data and AI use stay under their control.**

## Why institutions would want to self-host

- **Student privacy.** Annotations tied to named students are likely education records under FERPA (the US student-privacy law). Self-hosting keeps them inside the institution, and there's no new outside company processing student data to clear through procurement.
- **AI governance.** Universities are writing AI policies now. Dialectic's class charter enforces one, course by course, and self-hosting lets the institution decide which models are allowed at all.
- **AI cost and control.** Many universities already run their own models or campus AI services: open-weight models on their own GPUs, a university-owned Azure OpenAI or AWS Bedrock account, or campus-wide tools such as Michigan's U-M GPT and Harvard's AI Sandbox. Dialectic can run on those instead of a vendor's account.

## Bring your own AI: already true, not a roadmap

Dialectic talks to its AI through the standard OpenAI-compatible API that most of those services expose. **Switching to an institution's own models means changing three settings** (`DO_INFERENCE_URL`, `DO_INFERENCE_KEY`, `DO_MODEL`); no code changes, and no student text leaves campus. Web search is one function (`search.py`), so it can be swapped too, ideally for **the library's own search**, which makes "permissible sources" mean "what our library holds".

Honest caveat: our charter gate and source filter are tuned for Claude Sonnet 5.5. A smaller model may be worse at following the charter, so the product would ship a **certified-models list and a self-test** that runs the charter-gate cases against an institution's model before it's switched on.

## Licensing: open core, priced per student

| Edition | Who it's for | What they get | Price |
| --- | --- | --- | --- |
| **Community** | Any instructor or class | The full collaborative reader, charter and AI features; self-hosted | Free, open source (AGPL) |
| **Institutional** | Universities and colleges that self-host | LMS integration (LTI 1.3: Canvas, Moodle, Blackboard), campus single sign-on (SAML/Shibboleth), admin defaults for charters, models and sources across courses, the certified-models self-test, support and security updates | Annual fee per student (FTE) |
| **Hosted** | Departments without IT capacity; single-course pilots | We run it | Per course or per student |
| **Consortium** | Groups of schools, e.g. the Tri-College Consortium (Haverford, Bryn Mawr, Swarthmore) | Institutional edition across members, shared course libraries | Discounted per-student rate |

**Why AGPL for the free edition:** anyone may self-host and modify it, but a company that offers it as a hosted service must publish its changes, so competitors can't simply resell it. Faculty can try it with no purchase, adoption grows from individual classes upward, and institutions pay for what IT needs, not for the core idea.

## Precedent

- **Overleaf:** free open-source edition anyone can self-host; a paid Server Pro licence for institutions that self-host with SSO and support; hosted plans and campus-wide licences. The closest template for this model.
- **Moodle:** open source and widely self-hosted by universities; revenue from certified partners' hosting and support, plus hosted and enterprise editions.
- **Hypothesis:** open-source social annotation run as a nonprofit; institutions pay for its LMS integration. Our nearest competitor, and evidence that annotation in courses is something institutions buy.
- **Canvas, Open edX:** open-source (AGPL) core; the money is in hosting and services.
- **GitLab, Mattermost:** "open core": a free self-managed edition, enterprise features in paid tiers.

**Another route:** a nonprofit funded by grants, as Hypothesis is. Foundations such as Mellon fund digital-humanities tools, and a Du Bois demo is squarely in that territory.

## Path to institutional adoption (what the MVP doesn't have yet)

LMS integration (LTI 1.3), campus single sign-on, an accessibility statement (WCAG 2.1 AA), answers to the standard higher-ed security questionnaire (HECVAT), and the certified-models self-test. Worth one line on the slide, so judges see we know the gap.

## For the slide

1. **Free for every class** (open source).
2. **Your AI, your data:** institutions run it on their own servers and their own models; three settings, no code.
3. **Paid institutional edition:** LMS, SSO, admin, support, per student.
4. **First customer:** the Tri-College Consortium.
