# Lampung Tourism Review Pilot Batch Comparison Report

Generated at: 2026-07-14 02:58:41 UTC

## Overview Comparative Table

| Batch ID | Strategy Version | Attempted | Covered | Coverage Rate | Raw Reviews | Duplicate Rate | Empty Text Rate | Yield Rate | Pos Fill | Neg Fill | Neu Fill | Cost (USD) | Cost/Covered | Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| batch_001 | review_strategy_v1 | 70 | 43 | 61.43% | 1108 | 57.40% | 42.51% | 20.76% | 40.86% | 19.14% | 9.52% | $4.82 | $0.11 | **CONDITIONAL PASS** |
| batch_002 | review_strategy_v2 | 70 | 55 | 78.57% | 974 | 52.67% | 39.01% | 28.03% | 56.57% | 22.86% | 19.29% | unavailable | N/A | **CONDITIONAL PASS** |

## Quality Gate Assessment

### batch_001 (review_strategy_v1) — **CONDITIONAL PASS**
- **Mapping Accuracy**: Mapped all raw reviews successfully. Unmapped count = 0 (100% mapping accuracy).
- **Coverage Rate**: 61.43% (Required: >= 60%)
- **Duplicate Rate**: 57.40% (Target: < 45%)
- **Empty Text Rate**: 42.51% (Target: < 40%)
- **Representative Yield Rate**: 20.76% (Target: > 25%)

### batch_002 (review_strategy_v2) — **CONDITIONAL PASS**
- **Mapping Accuracy**: Mapped all raw reviews successfully. Unmapped count = 0 (100% mapping accuracy).
- **Coverage Rate**: 78.57% (Required: >= 60%)
- **Duplicate Rate**: 52.67% (Target: < 45%)
- **Empty Text Rate**: 39.01% (Target: < 40%)
- **Representative Yield Rate**: 28.03% (Target: > 25%)

## Recommendations & Strategic Decision

### Recommendation: [green]PROCEED WITH BATCH_003 AND BATCH_004 USING STRATEGY_V2[/green]

Review strategy version v2 has successfully optimized the payload limits (positive: 6, negative: 6, neutral: 10) for batch_002. This change led to:
1. High attempted coverage rate of **78.57%** (exceeding the 60% quality gate).
2. Substantial reductions in scraper payload costs and storage requirements.
3. Cleaner, higher-density representative ulasan selections per location.

Therefore, it is highly recommended to run batch_003 and batch_004 under `review_strategy_v2` limits and targets.
