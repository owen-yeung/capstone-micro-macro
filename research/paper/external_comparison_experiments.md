# External comparisons — paper drop-in (§4.6 Experiments, §5.9 Results)

Numbering continues the OrgBid report after Experiment 3 / §5.8. Quantitative cells stay empty until those runs are authorized. Do not invent scores.

Voice: academic, non-developer. Name actors by what they are in the tender (owner, firm, members, representative, bids, packages).

---

## 4.6 External comparisons at four tendering moments

Experiments 1–3 vary how a firm is organized while keeping OrgBid’s tendering protocol fixed. They show that the organizational layer improves decisions relative to one-shot and serial self-review. They do not show whether that layer is doing work that established methods from adjacent literatures already do. The four comparisons below therefore hold the **project, the firms, the members, and the information each actor is allowed to see** fixed, and replace **one** decision mechanism at a time. Observed partner identities, winning bids, contract values, and actual durations remain withheld from every actor, as in §4.1; they are used only afterwards, and only where a ranking or an award can be compared with the historical record.

No comparison re-runs the whole lifecycle. Each one corresponds to a familiar moment in construction tendering. Following the stage-isolated design of Experiment 1, every alternative receives the same upstream artifacts from the organizational arm of the same project (who is invited, who has already decided to bid, which bids have been opened). Only those artifacts cross stage boundaries; no alternative sees another alternative’s internal discussion. Differences cannot then be attributed to a different project brief or a different bidder list.

**What is never replaced.** The case itself; the owner’s packaging of the works; the rule that a firm speaks with one external voice; the rule that a written participation decision changes only after a recorded joint-bid failure, and then only to a solo bid or a withdrawal; the opening of bids (who remains admissible); and the project-environment execution of signed contracts.

The four comparisons are not pooled with one another or with Experiments 1–3. Each answers a different question about a different real-world act. Computational cost is reported beside every outcome, as in Experiment 1: an organizational layer that matches a simpler method at several times the number of model calls is a negative result unless the quality gap is large enough to justify it.

**Table. Overview of the four external comparisons.**

| Experiment | Tendering moment | What is replaced | What the alternative is | Primary question |
|---|---|---|---|---|
| 4 | After opening | Owner ranking and award | Transparent numerical ranking of the same admissible bids | Does owner-side deliberation change **who is awarded**? |
| 5 | Joint bidding | The inter-firm negotiation floor only | A generic language-model negotiator, and a classical automated negotiator with explicit utilities | Does an organizational floor reach agreement more often, or on fairer shares? |
| 6 | Inside the firm | How members communicate on bid/no-bid | Generic hub-and-spoke, chain, and fully connected discussion, on the same members and facts | Do a decision-holding member and bounded visibility outperform generic multi-speaker structures? |
| 7 | Bid documents | How the submission is written | A dedicated construction technical-proposal procedure | Does organizational drafting (draft, review, submit) improve the document? |

**Sample.** Unless a later protocol specifies otherwise, Experiments 4–7 reuse the twelve projects and the frozen upstream artifacts of Experiment 1. Award comparisons use the evaluation-and-award tasks; joint-bid comparisons use packages in which at least one firm sought partners; intra-firm comparisons use the participation (bid/no-bid) tasks; document comparisons use the bid-document tasks of firms that remain eligible to submit.

### 4.6.1 Experiment 4 — Ranking and award of opened bids

Once complete bids are on the table, the owner must rank them and name a winner. In OrgBid this is an organizational act: members of the owner firm discuss technical, cost, and control concerns, and the decision-holding member issues the evaluation report and the award. Experiment 4 asks whether that deliberation changes **who wins**, relative to a transparent numerical rule of the kind already used in procurement practice.

The alternative ranks the **same admissible bids** on attributes already on the opened record: price, programme tightness, declared risk, and publicly known capability. Price is a cost criterion and capability a benefit. Weights are equal in the primary specification; a second specification lets the observed spread of the bids set the weights. The ranking method is closeness to an ideal solution (TOPSIS); a weighted-sum ranking is a sensitivity check. An empty bid set still produces no award.

The numerical rule never sees bids that failed opening, never sees any firm’s internal discussion, and never sees the historical winner while it is ranking.

**Outcomes.** (i) Whether the numerical rule and OrgBid name the same winner on each package. (ii) Agreement of the full ranking (rank correlation). (iii) After-the-fact alignment with the historical winner, which is not a claim that either method predicts the market—only whether organizational evaluation and a numerical rule differ in the same direction relative to the record. (iv) Time and number of model calls (the numerical rule uses none).

### 4.6.2 Experiment 5 — Forming a joint bid

When a firm cannot, or prefers not to, bid alone, it must find partners and agree leadership, work shares, price split, and risk allocation. In OrgBid each firm first discusses the joint bid internally; only the designated representative then speaks on a shared negotiation floor; a failed joint bid may be revised only to a solo bid or a withdrawal.

Experiment 5 replaces **only the floor**. Internal discussion and the licensed revision rule stay as in OrgBid. Two alternatives are used.

- A **language-model negotiation** among stakeholder speakers with private scoring sheets, taken from a published multi-issue negotiation testbed. Each firm is one speaker. The issues are leadership, work share, price split, and risk. Private reservations come from the firm’s own profile and the package budget, not from historical outcomes.
- A **classical automated negotiation** with explicit utilities over the same four issues. Preferences are written down in advance; there is no prose discussion.

If the floor produces no acceptable deal, OrgBid’s reconsideration step still runs. That isolates whether an organizational floor reaches agreement more often, or on fairer shares, than a generic negotiator—without confounding the comparison with a different bid/no-bid rule.

**Outcomes.** Whether a joint bid forms; joint value and the worst-off partner’s value relative to walking away; distance of agreed work shares from a capacity-weighted split; whether private reservations appear in public speech; number of rounds and model calls.

### 4.6.3 Experiment 6 — Deliberation inside the firm

The participation (bid/no-bid) decision is taken inside the firm. OrgBid uses role-specialized members (technical, commercial, delivery, and so on) and a decision-holding member who alone issues the firm’s external decision. Experiments 1–3 already compare one-shot, same-role multi-step, and multi-member forms **within** OrgBid. Experiment 6 asks whether those forms outperform **generic communication structures** that are not built for tendering.

The alternative places the **same members**, with the **same facts**, in three communication structures taken from a published multi-agent collaboration benchmark: a hub-and-spoke (members speak to a centre—closest to OrgBid’s decision-holding member), a chain (serial revision—closest to same-role multi-step review), and a fully connected discussion. Only the decision-holding member’s final statement is recorded as the firm’s bid/no-bid. Members’ remarks remain advice, not evidence.

The benchmark’s built-in research, coding, and bargaining games are not used. Using them would compare different tasks, not different ways of organizing the same tendering decision.

**Outcomes.** The same six criteria as Experiment 1 (decision appropriateness, key-issue coverage, executability, risk and trade-off, evidence fidelity, internal consistency), as paired differences on identical firm–package units; model-call budget matched to OrgBid’s organizational form; how often the decision flips relative to a single decision-holding member; how often a member uses facts they were not entitled to see.

### 4.6.4 Experiment 7 — Preparing the bid document

Once a firm or a consortium will bid, it must produce a technical and commercial submission (price, programme, method, and risk response). OrgBid drafts this in three internal rounds: draft, review, and submit. Experiment 7 asks whether that organizational drafting improves **document quality** over a dedicated procedure whose only job is to write construction technical proposals.

The alternative extracts requirements, plans the document, writes it, and checks compliance. **Who is allowed to submit** remains OrgBid’s: firms that declined, and joint bids that never formed, still do not submit. Only the writing of the document is replaced. The resulting text is scored with the same key-issue coverage, executability, and evidence-fidelity criteria used for OrgBid bid documents, plus mechanical compliance (required sections present; invented standards; programme inconsistencies).

**Outcomes.** Rubric scores on the bid document; required-section hit rate and compliance flags; number of model calls relative to OrgBid’s three rounds.

---

## 5.9 External comparisons: how the results are to be read

These four comparisons have not been run in the present report. The numerical award ranking is designed to use no model calls, so it can be filled first from the same frozen artifacts. The subsections below state, in advance, how each stage will be read. A better award ranking will not license a claim about joint-bid formation, and a cheaper bid document will not license a claim about bid/no-bid quality. The scales of the experiments will differ, and their scores will not be pooled, as in §5.8.

### 5.9.1 Ranking and award

The primary table is winner agreement: for each package, whether OrgBid and the numerical rule name the same contractor, consultant, or supplier. Rank correlation describes the rest of the list. A third column, filled only after ranking, records whether either winner matches the historical record.

If winners almost always coincide, owner-side deliberation is not changing the award relative to a transparent rule, and its computational cost is hard to justify at this stage. If they diverge, the Experiment 1 rubric on the evaluation report, and the (post-hoc) historical column, say whether the divergence is disciplined or arbitrary. Alignment with history is not accuracy; the study does not claim to predict real awards.

### 5.9.2 Joint bids

The primary table is whether a joint bid forms, and whether the agreed shares sit above each party’s walk-away point.

If the generic language-model floor matches OrgBid’s agreement rate, the value of OrgBid at this stage is the internal discussion and the revision rule, not the floor. If classical utility negotiation agrees more often but on shares that ignore unmodelled constraints (qualifications, workload), that is a reminder that explicit utilities omit what the organizational floor is meant to keep. Leakage of private reservations is a process failure even when a deal forms.

### 5.9.3 Deliberation inside the firm

The primary table is paired rubric differences on the same bid/no-bid units, at matched model-call budgets, between OrgBid’s organizational form and the hub-and-spoke, chain, and fully connected structures.

A gain that appears only against the fully connected structure, and disappears against the hub-and-spoke, supports the claim that **a designated decision-holding member and bounded visibility** matter more than the mere presence of several speakers. A gain that disappears once the chain (serial self-review) is used supports Experiments 1 and 2: multi-step structure, not role labels, carries most of the quality difference. Flips relative to a lone decision-holding member, without rubric gains, are instability, not benefit.

### 5.9.4 Bid documents

The primary table is key-issue coverage, executability, and evidence fidelity of the submission, plus mechanical compliance.

If the dedicated proposal procedure matches or beats OrgBid on coverage and compliance at similar cost, organizational drafting is not the right place to spend extra model calls; the organizational layer should be reserved for bid/no-bid, joint bidding, and award. If OrgBid wins on evidence fidelity and risk response while losing on formatting compliance, the two tools are complementary rather than substitutes.

### 5.9.5 Cross-stage discipline

Three quantities are reported for every comparison and never averaged into a system score: the stage-specific outcome; model calls, tokens, and time; and information integrity (no use of withheld historical outcomes; no use of another firm’s internal discussion; a single external voice per firm). Integrity failures count against a method even when its headline outcome looks better.
