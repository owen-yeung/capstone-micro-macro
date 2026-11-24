# External baseline comparison

Three comparisons were run on the frozen 28-case tender set. No model was called, and the historical awards, bids, and scores were not changed. The three results are separate.

## Award ranking (pymcdm TOPSIS)

TOPSIS was applied to every package that has declared percentage weights and at least two priced bids. It used price, and duration only when every eligible bid stated one total duration in the same unit. Work-plan, experience, and quality weights were left unused because the frozen bids have no numeric score for them. Technical-fit scores were not filled in.

Packages ranked: 28. Packages whose awarded bidder is in that matrix: 28. The awarded bidder is in the TOPSIS top group on 8 of 28. Where the top group is a single bidder (26 packages), the winner matches on 6.

Price was the only applied criterion on 19 packages. On each of those, the top group is the lowest price (19 of 19), and the awarded bidder is in that group on 4. Duration was applied with price on 9 packages, and the awarded bidder is in the top group on 4 of those.

A match means the owner's awarded bidder is in the highest TOPSIS group. The owner record does not publish a full order, so there is no second ranking to compare beyond the winner.

## Bid documents (framework rubric)

The countable bid-rubric levels were applied to 295 frozen bid documents. R2 follows the seven-item checklist. R3 follows the five executable aspects. R6 is 2 when the price lines do not add up to the total, and 3 when they add up but the plan states a different duration. R1, R4, and R5 are blank: those levels need a reader to judge fit, tradeoff, and invented facts.

R2 levels: {'1': 0, '2': 0, '3': 0, '4': 275, '5': 20}. The bids that are not level 5 miss a checklist item here: {'假设或除外:missing': 275}. R3 levels: {'1': 0, '2': 44, '3': 75, '4': 114, '5': 62}. Price lines add up on 295 bids and fail to add up on 0.

The shared tender packet is case-0005 contractor_package (bid_documents/shared_tender_packet). It contains the package text and each bidder's company file, which is the input a bid-document generator would be given. Framework bids scored for that packet: 4. Bid-gen documents scored: 0. No bid-gen document was generated. Its planning step needs a live model, and this comparison does not call one. A missing document has no rubric score.

## Consortium agreement (LLM-Deliberation scores)

The translated game is case-0150 contractor_package (consortium_contractor_package_001). Formed consortium whose member files state the most package-requirement stems. Ties break by case id, then package id. Member files state 2 of the package requirements. Issues placed in the game: 2. Requirements that no member file states were left out of the scores.

Secret scores were written before the agreement text was used. A party scores 10 for taking a capability its own file states, and 5 when another firm whose file states it takes that capability. The minimum score is 10. The frozen role split was then read only to see which firm the agreement names for each issue.

Agreement success under that rule: False. Utilities: {'COMP-0199': 10, 'COMP-0366': 5, 'COMP-0491': 5}. A party clears the minimum only when every included issue is given to a firm whose file states it. Assignments: [{'requirement': '安全管理能力', 'stems': ['安全管理'], 'supported_by': ['COMP-0199', 'COMP-0366', 'COMP-0491'], 'assignee': 'COMP-0199', 'assignee_is_supported': True}, {'requirement': '进度控制能力', 'stems': ['进度控制'], 'supported_by': ['COMP-0199', 'COMP-0366', 'COMP-0491'], 'assignee': None, 'assignee_is_supported': False}]. Where an assignee is empty, the role text does not contain the requirement stem. The dialogue was not run.

## What these numbers are

The award figure is winner overlap on the numeric criteria the files already contain. The document figure is a checklist score of this framework's own bids. The consortium figure is whether one frozen agreement meets preferences written from the company files. They are not one combined baseline score, and none of them is a project-cost or project-quality result.

## Metrics for reporting

The unit for the award and document metrics is the case. Packages or bids inside a case are averaged first, then the cases are averaged. The interval resamples those cases. The consortium figures describe the one translated deal and have no interval.

### Award: owner decision against pymcdm TOPSIS

Case-equal top-group agreement is 0.292 (95% interval 0.260 to 0.323), from 8 cases and 28 packages. The package-pooled count is 0.286.

A uniform draw among the eligible bidders would land in the top group at a case-equal rate of 0.395. Agreement minus that chance rate is -0.103 (95% interval -0.154 to -0.048).

Case-equal mean reciprocal rank of the awarded bidder is 0.632 (95% interval 0.618 to 0.648). Across packages, the award's TOPSIS rank counts are {'1': 8, '2': 18, '3': 2}. Rank 1 is the top group, and bidders in the same group share that rank.

Where the top group is one bidder (26 packages), the median relative price of the award versus that bidder is 0.113 (95% interval 0.060 to 0.230). Where they differ (20 packages), the median relative price is 0.186. A positive value means the awarded price is higher than the TOPSIS top price.

Matches by package type, pooled across cases: contractor_package 4/8, design_package 0/4, supervision_package 0/8, supplier_package 4/8.

### Bid document: framework checklist, external arm not estimated

Case-equal mean R2 is 4.068 (95% interval 4.044 to 4.093). Case-equal mean R3 is 3.663 (95% interval 3.531 to 3.788). The share of the seven checklist items with specific content is 0.867 (95% interval 0.863 to 0.870). Price lines close on 1.000 of bids at the case-equal rate. The plan and the schedule state different durations on 0.026.

The paired contrast is the mean, on the shared tender packet, of the framework rubric level minus the external rubric level, separately for R2 and R3. That contrast is not estimated: the external arm has no document.

### Consortium: one deal under LLM-Deliberation scores

Supported issues named by the role text: 0.500 (2 issues). Parties at or above the pre-written minimum: 0.000. Mean utility divided by that minimum: 0.667. Lowest utility divided by that minimum: 0.500. Deal success: False.

## Follow-on dialogue package

To generate the missing LLM-Deliberation dialogue and paired Capstone decision dialogues, use the PIC package at `experiment4/external_dialogue_pic_20261125/` (`bash scripts/external_dialogue_generation.sh all`). That live experiment does not rewrite this offline summary.
