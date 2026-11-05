"use strict";

/** Parse only review metadata from the real CodeRabbit account for this exact head. */
function hasReviewEvidence(comments, head) {
  return comments.some(comment => {
    if (comment.user?.login !== "coderabbitai[bot]") return false;
    const pattern = /final_review_risk_coverage:(\{[^\n]+\})/g;
    for (const match of (comment.body || "").matchAll(pattern)) {
      try {
        const evidence = JSON.parse(match[1]);
        if (evidence.sourceCommitId === head && evidence.coveredCommitId === head && evidence.kind === "reviewed") return true;
      } catch { /* Invalid metadata is never proof. */ }
    }
    return false;
  });
}

/** Require a completed successful CodeRabbit check from its pinned GitHub App. */
function hasSuccessfulReviewCheck(checks, head) {
  return checks.some(check => check.name === "CodeRabbit" && check.app?.id === 347564 &&
    check.head_sha === head && check.status === "completed" && check.conclusion === "success");
}

/** Read live PR head and publish a separate non-bypassable evidence status on it. */
async function publishEvidence({ github, context, core }) {
  const owner = context.repo.owner;
  const repo = context.repo.repo;
  const pull_number = context.payload.pull_request?.number || context.payload.issue?.number;
  if (!Number.isInteger(pull_number)) throw new Error("Missing PR number");
  const { data: pr } = await github.rest.pulls.get({ owner, repo, pull_number });
  if (pr.state !== "open") return;
  const head = pr.head.sha;
  if (!/^[0-9a-f]{40}$/.test(head)) throw new Error("Invalid head SHA");
  const status = async (state, description) => github.rest.repos.createCommitStatus({
    owner, repo, sha: head, state, context: "review-evidence/status", description,
    target_url: `${process.env.GITHUB_SERVER_URL}/${owner}/${repo}/actions/runs/${context.runId}`
  });
  await status("pending", "Перевіряється справжній огляд поточного head");
  try {
    const comments = await github.paginate(github.rest.issues.listComments, { owner, repo, issue_number: pull_number, per_page: 100 });
    const checks = await github.paginate(github.rest.checks.listForRef, { owner, repo, ref: head, per_page: 100 });
    const success = !pr.draft && hasReviewEvidence(comments, head) && hasSuccessfulReviewCheck(checks, head);
    const { data: current } = await github.rest.pulls.get({ owner, repo, pull_number });
    if (current.head.sha !== head) {
      await status("failure", "Head змінився під час перевірки");
      return;
    }
    await status(success ? "success" : "failure", success ? "Справжній огляд точного head підтверджено" : "Немає завершеного огляду точного head");
    if (!success) core.setFailed("CodeRabbit evidence missing, skipped, rate-limited, or not successful");
  } catch (error) {
    await status("failure", "Не вдалося перевірити доказ огляду");
    throw error;
  }
}

/** Resolve each real PR before selecting its serialization key, including forks. */
async function resolvePulls({ github, context }) {
  const direct = context.payload.pull_request?.number || context.payload.issue?.number;
  if (Number.isInteger(direct) && direct > 0) return [direct];
  if (context.eventName !== "check_run") throw new Error("Missing PR event");
  const sha = context.payload.check_run.head_sha;
  if (!/^[0-9a-f]{40}$/.test(sha)) throw new Error("Invalid check head");
  const prs = await github.paginate(github.rest.repos.listPullRequestsAssociatedWithCommit, {
    ...context.repo, commit_sha: sha, per_page: 100
  });
  return [...new Set(prs.filter(pr => pr.state === "open" && pr.head.sha === sha &&
    Number.isInteger(pr.number) && pr.number > 0).map(pr => pr.number))];
}

module.exports = { hasReviewEvidence, hasSuccessfulReviewCheck, publishEvidence, resolvePulls };
