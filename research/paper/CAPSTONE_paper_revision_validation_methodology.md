# Organizational LLM Agents for Stateful Multi-Stage Decision-Making in Construction Tendering

**Paper revision note (validation methodology update).**  
This file revises the interim report’s validation-facing sections in light of (i) the Capstone generation-validation protocol now operated in the repository and (ii) recent methodological precedents on validating LLM / generative agent simulations. Frozen archival copies of the submitted interim PDF remain unchanged under `research/references/submitted_interim.pdf`. Supporting literature extracts used for this revision are archived under `research/paper/literature/`.

Unchanged chapters (1 introduction body except the validation paragraph; 2.1–2.2; 3.1–3.4; 4.1; 5) keep the interim wording unless a local cross-reference is marked *[revised]*. New or substantially rewritten material is marked *[revised]* or *[new]*.

---

## Table of Contents *[partially revised]*

1. Introduction  
2. Literature Review  
 2.1 Construction Collaboration, Tendering, and Consortium Formation  
 2.2 Multi-Agent Systems and LLM Agents for Simulation  
 2.3 Validating LLM-Based Simulations: Outcomes, Processes, and Controls *[revised]*  
3. Methodology  
 3.1 Framework overview  
 3.2 The firm as a composite organizational agent  
 3.3 Coordination protocols  
 3.4 Package-level bidding, evaluation, and award  
 3.5 Validation methodology for decision-process fidelity *[new]*  
4. Experiments  
 4.1 Dataset and candidate-pool construction  
 4.2 Configuration and evaluation metrics *[revised]*  
5. Results  
6. Discussion  
 6.1 What the results do and do not support *[revised]*  
 6.2 Limitations and next steps *[revised]*  
References *[revised]*

---

## 1. Introduction *[local revision only]*

[… preceding paragraphs unchanged …]

Most multi-agent debate research assumes a shared correct answer and convergence, which poorly fits tendering with conflicting interests [11], [12]. Validation research likewise cautions that natural-language rationales alone do not establish realistic organizational behavior: outcome resemblance can coexist with non-human decision processes [21]; hypothesis-level effects can be recovered while response distributions still diverge from human data [22]; and prompts or visible experimental structure can pre-determine simulated outcomes [23]. Validation must therefore be designed into the simulation rather than inferred from a plausible terminal decision [13]–[15], [21]–[24].

[… remaining introduction paragraphs and RQ1–RQ3 unchanged …]

---

## 2.3 Validating LLM-Based Simulations: Outcomes, Processes, and Controls *[revised]*

Validation is the central methodological constraint on LLM-based simulation. A critical review finds that generative agent-based modeling (GABM) studies often rely on face validity or on outcome measures only loosely related to the mechanism under study [13]. Recent work sharpens that diagnosis into a sharper design requirement: **surface equivalence of outcomes is not interchangeable with fidelity of decision processes**.

In logistics and supply-chain settings, Castillo [21] separates *human-equivalence testing* of observed behaviors from *decision-process validation* of the pathways that produce those behaviors. Models can match some human outcomes while exhibiting artificial mediation structures absent from participant data—an “equivalence-versus-process” paradox that directly cautions against treating a simulated bid, award, or participation rate as sufficient evidence of organizational realism. Parallel evidence from behavioral operations management shows a related gap: across nine published experiments, LLMs often reproduce hypothesis-level effects yet miss the shape of human response distributions [22]. A plausible terminal decision, or even a correct directional effect, is therefore an incomplete validity test for a tendering simulator whose scientific object is deliberation under incomplete information.

A second cluster of precedents motivates **controlled contrasts before novel claims**. Cross et al. [14] advocate a replication-to-prediction sequence: first identify cognitive components needed to reproduce established human findings, then use the validated architecture under novel conditions. That logic maps onto construction-tender designs that contrast single-shot generation against same-role multi-step review and multi-role deliberation, and that separate settlement-linked feedback from no-feedback controls, before interpreting adaptation or process gains. Li et al. [15] further argue for behavioral-consistency checks against domain-theory predictions as agents revise strategies, reinforcing process-level rather than only terminal evaluation.

A third cluster motivates **anti-leakage and anti-circularity controls**. Zhou et al.’s PIMMUR audit of LLM society simulations finds that models often recognize the underlying experiment and that prompts frequently impose constraints that pre-determine outcomes [23]. Those findings support answer-key withholding, limited visibility of experimental arms, sealed order swaps for preference comparisons, and challenge-class coverage gates that prevent post-hoc hunting for favourable cases. Xia et al. [24] show, conversely, that empirical grounding—embedding archival demographic, routine, and spatial facts into agent initialization and decisions—improves statistical realism relative to ungrounded agents, while still leaving residual gaps. For construction tendering, the transferable lesson is not that any particular non-construction dataset should be imported, but that **archival project–firm facts, explicit missing-information conditions, and held-out historical outcomes** are preferable to purely generative vignettes or circular “model-to-model” validation [23], [24].

Taken together, the literature points to a layered validation hierarchy in place of an unfounded bid-prediction claim:

1. **Process integrity** — recoverable stages, role boundaries, outward commitments distinct from private scratchpads, and auditable provenance;  
2. **Behavioral / decision-process plausibility** — appropriateness under fixed facts and constraints, factor coverage, executability and trade-offs, and organization/feedback contrasts;  
3. **Structural comparison against historical outcomes** — only after (1)–(2), and only with baselines matched to closed-pool geometry.

Closed candidate sets still require separate treatment. If every task presents a fixed shortlist of firms and one observed answer, even a random selector can appear competitive when the pool is small. Any hit rate reported under such a design has to be read against a baseline matched to both pool size and award size. The remaining gap is therefore not a lack of validation vocabulary; it is the need for a **domain-grounded validation design** for a staged construction tender simulation that keeps process fidelity primary and historical award match secondary. Section 3.5 specifies how the present study operationalizes that design. One caveat carries through from the literature into our own claims: several of the strongest precedents use human participant data [14], [21], [22], [24]. Model-assisted credibility slices in this project are **not** substitutes for independent human expert adjudication and must not be described as such.

---

## 3.5 Validation methodology for decision-process fidelity *[new]*

Section 3.1–3.4 specify the organizational simulation objects. This subsection specifies how generated decisions are validated so that the resulting evidence remains closer to real bid/no-bid deliberation than to unconstrained text generation. The protocol complements, and does not replace, the package-level award comparison in Section 4.2. Its design choices follow the hierarchy in Section 2.3: process integrity first, decision-process scoring second, historical structural match last.

### 3.5.1 Archival task cards and withheld answer keys

Each scored micro-case is a frozen **task card** derived from real project and firm dossiers: role (contractor, supplier, designer, or supervision-service provider), material variant (`full` versus `missing_core`), supplied facts, explicit gaps (`not_supplied`), unresolved conditions, scoring factors, and examples of acceptable versus inappropriate actions. Cards are hashed so later scoring cannot silently drift. Historical awards, partner identities used as benchmarks, and settlement values are withheld from generation prompts and are never used as the micro answer key, consistent with anti-leakage guidance for LLM simulations [23] and with empirical-grounding arguments that privilege archival constraints over purely synthetic vignettes [24]. Appropriateness is therefore defined relative to the card’s facts and constraints, not relative to “who won historically.”

### 3.5.2 Outward commitments versus private reasoning

Scoring uses only the **outward public business object**—the decision-facing commitment a firm would expose (bid, no-bid, or conditional intention, with supporting public fields). Private fields such as internal `thoughts` are retained for audit but excluded from the scoring view. If no unique outward object is recoverable, no synthetic grade is invented. This separation mirrors the framework’s distinction between private member reasoning and firm-level external representation (Section 3.2) and prevents private chain-of-thought fluency from being mistaken for organizational validity [13], [21].

### 3.5.3 Controlled process arms for deliberation and feedback

To test whether organization and feedback change decisions in interpretable ways—rather than only whether a final award overlaps a benchmark—the evaluation maintains controlled arms:

- **Judgment / materials contrast.** Same card under generator versions and under full versus missing-core materials.  
- **Organization contrast.** Single-shot generation versus same-role multi-step review versus multi-role deliberation at a fixed generator version (cohort CP07).  
- **Feedback contrast.** No feedback versus settlement-linked feedback under fixed sources and windows, with invariant constraints that must not flip arbitrarily.

These arms follow the replication-to-prediction logic of validating components and contrasts before novel claims [14] and keep process validation distinct from outcome equivalence [21], [22].

### 3.5.4 Mechanical gates (eligibility, not grades)

Before business scoring, mechanical gates check (i) readability of a unique outward answer, (ii) presence of required public sections (with a soft path for compact alternate schemas), and (iii) heuristic patterns for invented facts, ungrounded promises, or scope overrun. Gates emit structured codes only; soft hits are hints. They never assign action-appropriateness or ordinal quality grades. Blocking failures remain visible in the unscored denominator of readiness reports, so “request submitted” is never equated with “valid decision evidence.” This implements a minimal-control / anti-circularity posture: tooling may triage, but it may not silently manufacture validity [23].

### 3.5.5 Citation-backed adjudication and score-sheet discipline

Eligible answers are scored against the card’s factors with **exact outward substrings** as evidence, plus a short reason. Where the protocol requires detail, ordinal grades for executability and trade-off quality are recorded. Structured score sheets separate a draft slot (second-model family) from an official adjudication slot; agreement is reported as draft–adjudicator agreement, not as human inter-rater reliability. Initial answers and later directed repairs are stored separately; repairs never overwrite first-round grades. Evidence rechecks verify that quoted spans still match the frozen response bytes.

Two adjudicator identities appear in the archive and must remain distinct in reporting: (i) author-assisted AI that participated in designing the original pipeline; and (ii) an independent second LLM provider used for later gate-eligible backlog clearance. Neither is an external human expert; neither is blind review. Stratified “expert-slice” samples are credibility slots for future human review and are not claimed as professional validation [13], [21].

### 3.5.6 Discrimination anchors, blinding helpers, and coverage gates

Before formal batches, a held-out discrimination set of constructed exemplars spans challenge classes (for example, grounded conditional plans, ungrounded commitments, grounded deferrals) across roles. Drift on anchors triggers forward recalibration only; historical grades are not rewritten. For version or organization preference comparisons, single-answer scoring precedes paired preference; arm/version fields are stripped; and sealed order-swap maps record presentation order. These helpers reduce, but do not eliminate, position and label cues identified in LLM evaluation [23]; they are not true independent blind review.

A coverage matrix over role × materials × condition × trade-off cells, together with challenge-class claim gates, constrains paper claims: empty cells narrow claims rather than inviting post-hoc item hunting. Denominators always retain unread, unscored, and gate-blocked counts.

### 3.5.7 Relation to structural award match

Package-level hit rates against hidden benchmarks (Section 4.2) remain a **supplementary** structural check under a closed candidate pool and are always reported against a size-matched random baseline. They do not validate the quality of deliberation, the handling of missing information, or the legitimacy of negotiation failure. In the vocabulary of Section 2.3, structural match is layer (3); the procedures in Sections 3.5.1–3.5.6 are layers (1)–(2).

---

## 4.2 Configuration and evaluation metrics *[revised]*

The main experiment used DeepSeek deepseek-v4-flash at temperature 0.2 with the full deliberation setting, the same candidate-pool rules and run parameters across all cases, at most three concurrent requests, and one execution per case.

Evaluation comprises three complementary levels, aligned with the hierarchy in Section 2.3:

1. **Operational performance** — completion, agent counts, messages, bid documents, recovery events;  
2. **Organizational / decision-process behavior** — participation distribution, consortium formation and failure, reconsiderations, and, under the Capstone scoring protocol (Section 3.5), citation-backed appropriateness and factor handling on outward answers, plus organization and feedback contrasts;  
3. **Structural match** — package-level hit rate, case-level any-hit rate, and the size-matched random baseline, evaluated only for packages with an observed reference company in the corresponding role and only after decision generation has finished.

A package-level hit occurred when at least one company in the simulated award matched an observed company in the same role; for a consortium, all member firms were included. A case-level any-hit occurred when at least one package in the case met that criterion. Because a consortium may contain several companies, a size-matched random baseline was used, drawing as many companies as the simulated award contained. With \(n\) candidates in the role, \(k\) observed reference companies, and \(m\) companies selected by the simulation, the probability of drawing at least one reference company is given in Formula (6):

\[
P_{\mathrm{random}} = 1 - \frac{\binom{n-k}{m}}{\binom{n}{m}} \tag{6}
\]

The difference between the system hit rate and this probability measures relative improvement; all structural metrics were computed overall and by role. Following Zhang et al. [22] and Castillo [21], structural hit rates are interpreted as outcome-similarity evidence only, not as proof that internal deliberation matched human or professional decision processes. Process-level claims rely on the Section 3.5 protocol and must keep unread, gate-blocked, and unscored denominators visible.

---

## 6.1 What the results do and do not support *[revised]*

The experiments support recoverable end-to-end simulation, differentiated role behavior, explicit negotiation conflict and reconsideration, and traceable decisions. These claims remain qualified: all cases ended as degraded, with 470 recovery events. Role differences demonstrate behavioral plausibility rather than real firms’ participation probabilities, since profiles, prompts, and role descriptions shape the results. Structural comparison supplies supplementary evidence of similarity to historical collaboration and must be read against the size-matched baseline.

The study does **not** demonstrate prediction of actual winners. The closed candidate pool guarantees that historical firms appear in their role’s candidate set, which alone pushes the random baseline to 57.6%, so 64.8% is supplementary evidence of structural similarity and not open-market accuracy. Nor does it demonstrate market discovery, since candidates are supplied before simulation. Recent validation research further implies that even a well-calibrated hit rate would be insufficient without process-level evidence: outcome equivalence can coexist with non-human decision pathways [21], and effect-level agreement can coexist with distributional divergence [22].

Accordingly, the Capstone validation layer (Section 3.5) treats citation-backed appropriateness under fixed archival cards, organization/feedback contrasts, mechanical eligibility gates, and coverage constraints as the primary warrants for decision-process claims. Author-assisted and second-provider LLM reviews increase auditability and coverage of gate-eligible answers; they do **not** constitute independent human expert validation [13], [21]. The validity of all 112 award entities means only that they passed procedural and reference-integrity checks; the framework verifies no licences, qualifications, conflicts of interest, or jurisdiction-specific regulations, and cannot substitute for legal or compliance assessment. Reproducibility of the 28-case award run is untested, since each case was executed once. The validated conclusion is therefore narrow: on cases built from real project and firm data, a heterogeneous organizational multi-agent framework can run cross-stage tendering simulations recoverably and traceably, producing role differentiation, negotiation conflict, and structural plausibility, while a separate process-validation protocol scores outward decisions against archival constraints without using historical awards as answer keys. The system should currently be regarded as a simulation and explanation tool for organizational decision processes.

---

## 6.2 Limitations and next steps *[revised]*

Nine limitations bound these results: the closed candidate pool produces a high random baseline; single-run evaluation leaves variance unreported; the absence of completed ablations means effects cannot yet be attributed to specific mechanisms; the sample is small and imbalanced (28 cases, two comparable supplier packages); all cases ended as degraded; generated prices and durations are unvalidated; construction-stage events are not fully simulated in the interim award study; a single LLM provider leaves generator-side cross-model robustness incompletely evaluated; and **process scoring remains model-assisted rather than independently human-adjudicated**, so expert-slice slots filled by a second LLM provider must not be reported as professional or blind validation [13], [21], [23].

The next steps follow directly. Ablations A1–A4 remain essential for moving from demonstrating that the system works to demonstrating that the design contributes, and repeated runs of the case set, 3–5 times with mean and standard deviation, address stochasticity. The size-matched baseline script should remain a standard reporting item. Discrimination-anchor drift checks, coverage claim gates, and sealed order-swap preference tests should precede any expanded paper claim about generator or organization effects [14], [23]. A human evaluation rubric with inter-rater agreement on the stratified expert slice would supply the missing external credibility layer. Bid-price and duration reasonableness should be validated once the corresponding benchmark fields are confirmed. The sample should continue expanding beyond the interim 28-case award set, at least two generator providers should be compared under identical cards, and award outcomes should continue to connect to event-driven construction-stage simulation where macro suitability is independently established.

---

## References *[revised; additions [21]–[24]]*

[1]–[20] remain as in the interim report, including:

- [13] M. Larooij and P. Törnberg, “Validation is the central challenge for generative social simulation: a critical review of LLMs in agent-based modeling,” *Artif. Intell. Rev.*, vol. 59, no. 1, Art. no. 15, 2026. doi: 10.1007/s10462-025-11412-6.  
- [14] L. Cross, N. Haber, and D. Yamins, “Validating Generative Agent-Based Models of Social Norm Enforcement: From Replication to Novel Predictions,” arXiv:2507.22049, 2025.  
- [15] Z. Li *et al.*, “Behavioral Consistency Validation for LLM Agents: An Analysis of Trading-Style Switching through Stock-Market Simulation,” arXiv:2602.07023, 2026.

Append:

[21] V. E. Castillo, “Validating Generative Agent-Based Models for Logistics and Supply Chain Management Research,” arXiv:2508.20234, 2025.

[22] R. Zhang, X. Zhang, and M. Zhao, “Predicting Effects, Missing Distributions: Evaluating LLMs as Human Behavior Simulators in Operations Management,” arXiv:2510.03310, 2025.

[23] J. Zhou, J. Huang, X. Zhou, M. H. Lam, X. Wang, H. Zhu, W. Wang, and M. Sap, “The PIMMUR Principles: Ensuring Validity in Collective Behavior of LLM Societies,” arXiv:2509.18052, 2025.

[24] C. Xia, Z. Kuang, and Y. Hu, “Empirical Grounding Improves the Realism of LLM Agents Simulating Human Behavior During Disruptions,” arXiv:2607.17437, 2026.

---

## Provenance

- Interim base: uploaded `CAPSTONE_Interim_Formatted_d863.pdf` (byte-identical archival copy: `research/references/submitted_interim.pdf`).  
- Literature starting point: `research/paper/literature/validation_precedents_note.md` and `research/paper/literature/elicit_validation_sources.xlsx`.  
- Capstone validation protocol: `research/generation_validation/README.md`, `research/DATA_LIFECYCLE.md`, `results/experiments/generation_validation_enhancement_20261117/`.
