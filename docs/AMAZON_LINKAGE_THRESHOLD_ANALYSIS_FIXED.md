# Amazon Linkage Threshold + Group Ranking Analysis — Fixed Patch

This patch fixes two issues in the threshold-analysis implementation:

1. The Top-K unit-test fixture previously put the positive candidate second in **both** recall groups, so Top-1 was correctly calculated as 0.0 while the test incorrectly expected 0.5. The fixture now has one positive candidate ranked first and one ranked second, matching the intended assertion.
2. The main script had an incorrect `labels["review_label".isin(...)]` expression. It now correctly uses `labels.loc[labels["review_label"].isin(...)]`.

The underlying ranking logic is unchanged.
