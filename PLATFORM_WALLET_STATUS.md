# HiDevs Passport Wallet snapshot

Captured from the supplied Passport Wallet screenshot on **2026-09-29**:

- Total agents/submissions: **44**
- Validated: **35**
- Visas earned: **525**
- Needs attention: **9**
- Visible validated submissions show **15 of 15 visas** each.

## Gap to 50 validated passports

If the leaderboard's passport count corresponds to issued/validated agents:

1. Fix the 9 attention submissions → 44 validated.
2. Validate 6 additional distinct agents → 50 validated.

The wallet proves the 35 validated agents have full visa coverage: `35 × 15 = 525`. This is stronger than simply increasing repository count.

## Next action

Open each **Needs attention** agent, copy its exact failure, fix that repository on `main`, and rerun validation. Do not create replacements until the existing 9 have been triaged.

## Score mathematics

Using the challenge formula shown on the platform:

- Each checkpoint: **50 points** × 3 = **150 points**.
- Each visa: **100 points** × 15 = **1,500 points**.
- First passport bonus: **25 points** once per account.
- A fully validated passport therefore contributes **1,650 points** after the first-passport bonus.

Projected path if every result is complete:

- 35 validated: `35 × 1,650 + 25 = 57,775`.
- Fix 9 attention agents: `44 × 1,650 + 25 = 72,625`.
- Add 6 more fully validated agents: `50 × 1,650 + 25 = 82,525`.

The last figure matches the visible rank-one score in the supplied leaderboard screenshot. It is a target calculation, not a claim about the live leaderboard or future results.
