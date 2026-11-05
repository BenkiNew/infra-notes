"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { hasReviewEvidence, hasSuccessfulReviewCheck, publishEvidence, resolvePulls } = require("../scripts/review_evidence.cjs");
const head = "a".repeat(40);
const proof = (user = "coderabbitai[bot]", sha = head, kind = "reviewed") => ({
  user: { login: user }, body: `<!-- final_review_risk_coverage:${JSON.stringify({ sourceCommitId: sha, coveredCommitId: sha, kind })} -->`
});
const check = changes => ({ name: "CodeRabbit", app: { id: 347564 }, head_sha: head,
  status: "completed", conclusion: "success", ...changes });
test("only exact head and real bot metadata are accepted", () => {
  assert.equal(hasReviewEvidence([proof()], head), true);
  for (const item of [proof("contributor"), proof(undefined, "b".repeat(40)), proof(undefined, head, "skipped")])
    assert.equal(hasReviewEvidence([item], head), false);
});
test("rate-limited passing check has no review proof", () => {
  assert.equal(hasReviewEvidence([{ user: { login: "coderabbitai[bot]" }, body: "Review rate limited" }], head), false);
});
test("neutral, skipped, wrong app or wrong head are refused", () => {
  assert.equal(hasSuccessfulReviewCheck([check()], head), true);
  for (const c of [check({ conclusion: "neutral" }), check({ conclusion: "skipped" }),
    check({ app: { id: 15368 } }), check({ head_sha: "b".repeat(40) })])
    assert.equal(hasSuccessfulReviewCheck([c], head), false);
});
test("malformed metadata is not accepted", () => {
  assert.equal(hasReviewEvidence([{ user: { login: "coderabbitai[bot]" }, body: "final_review_risk_coverage:{broken}" }], head), false);
});
function harness(comments, checks, changed = false) {
  const statuses = []; let reads = 0; const failures = [];
  const get = async () => ({ data: { state: "open", draft: false, head: { sha: changed && ++reads > 1 ? "b".repeat(40) : head } } });
  const listComments = () => {}; const listForRef = () => {};
  return { statuses, failures, args: { context: { repo: { owner: "synthetic", repo: "audit" },
    payload: { issue: { number: 1 } }, runId: 1 }, core: { setFailed: msg => failures.push(msg) },
    github: { rest: { pulls: { get }, issues: { listComments }, checks: { listForRef },
      repos: { createCommitStatus: async data => statuses.push(data) } },
      paginate: async method => method === listComments ? comments : checks } } };
}
test("head change during verification cannot produce success", async () => {
  const h = harness([proof()], [check()], true); await publishEvidence(h.args);
  assert.equal(h.statuses.at(-1).state, "failure");
  assert.equal(h.statuses.some(x => x.state === "success"), false);
});
test("passing CodeRabbit without proof is an explicit failure", async () => {
  const h = harness([], [check()]); await publishEvidence(h.args);
  assert.equal(h.statuses.at(-1).state, "failure"); assert.equal(h.failures.length, 1);
});
test("real successful review publishes exact head status", async () => {
  const h = harness([proof()], [check()]); await publishEvidence(h.args);
  assert.equal(h.statuses.at(-1).state, "success"); assert.equal(h.statuses.at(-1).sha, head);
});

test("fork check without payload PRs resolves exact real PR before locking", async () => {
  const github = { rest: { repos: { listPullRequestsAssociatedWithCommit() {} } },
    paginate: async () => [{ number: 12, state: "open", head: { sha: head } },
      { number: 12, state: "open", head: { sha: head } },
      { number: 13, state: "closed", head: { sha: head } },
      { number: 14, state: "open", head: { sha: "b".repeat(40) } }] };
  const context = { eventName: "check_run", repo: { owner: "synthetic", repo: "audit" },
    payload: { check_run: { head_sha: head, pull_requests: [] } } };
  assert.deepEqual(await resolvePulls({ github, context }), [12]);
});

test("comment and check events resolve the same per-PR lock number", async () => {
  assert.deepEqual(await resolvePulls({ github: {}, context: { payload: { issue: { number: 12 } } } }), [12]);
});
