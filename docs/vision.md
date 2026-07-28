# SkillForge AI — Vision Document

## 1. Summary

SkillForge AI is a web platform that runs realistic, AI-driven mock technical interviews for software engineering candidates. A user picks a programming language and a difficulty level, and the platform conducts a structured interview: it asks questions one at a time, evaluates each answer, gives feedback and a score, and stores the full session for later review.

## 2. Problem

Mock technical interviews are one of the highest-leverage ways to prepare for real interviews, but access to a good practice partner is unevenly distributed:

- Peer mock interviews depend on having a network of engineers willing to spend an hour, on a schedule that matches yours.
- Paid mock-interview services are expensive per session and don't scale to daily practice.
- Static question banks (LeetCode-style lists) test whether you can solve a problem, not whether you can communicate a solution under interview conditions, and they give no personalized feedback.

There is no low-friction way to get realistic, on-demand, judged practice at 2 a.m. before a 9 a.m. interview.

## 3. Solution

SkillForge AI acts as an on-demand interviewer:

1. The candidate selects a language and difficulty.
2. The system generates a question appropriate to that combination and to the candidate's history (so it doesn't repeat what they've already seen).
3. The candidate answers in free text.
4. The system evaluates the answer for correctness, completeness, and clarity, returns feedback, and either asks a follow-up or moves to the next question.
5. At the end of the session the candidate gets a score and a breakdown of strong and weak topics, and the session is saved to their history for later review.

## 4. Target Users

- Final-year CS students and bootcamp graduates preparing for their first junior/middle backend role.
- Self-taught developers without a network of senior engineers to practice with.
- Anyone who wants repeatable, judged practice on a schedule that doesn't depend on another person's availability.

## 5. Product Goals (v1)

- A candidate can complete a full mock interview (question → answer → feedback, repeated) without any human involvement.
- Every session is scored and stored, and the candidate can see how their scores trend over time and which topics are weak.
- The system works for four languages (Python, Java, C++, JavaScript) at three difficulty levels (Junior, Middle, Senior).

## 6. Success Metrics (v1, self-hosted / demo)

- A new user can register, start an interview, and receive scored feedback on an answer in under 2 minutes end-to-end.
- Interview evaluation returns in under 8 seconds per answer under normal load.
- Dashboard stats (average score, strong/weak topics) are correct against the underlying interview data — verified by integration tests, not just eyeballing.

## 7. Out of Scope for v1

- Live video/voice interviews — text-only for v1.
- Peer-to-peer (human) interviews.
- Payments / subscriptions.
- Multi-language UI (interface is English-only for v1; the AI can evaluate answers in the four supported programming languages regardless of UI language).
- Team/enterprise accounts.

These are natural v2 candidates once the core loop is proven.

## 8. Comparable Products

Pramp and interviewing.io solve the "find a human to practice with" problem via peer matching; LeetCode and similar platforms solve "practice solving problems" but not "practice explaining and defending a solution out loud under evaluation." SkillForge AI is closer to the second category but adds judged, conversational feedback instead of just a pass/fail test runner.
