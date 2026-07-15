#!/usr/bin/env node
/**
 * Batch-install all VidAU Email Agent skills.
 *
 * Local mode (default): copy skill dirs into ~/.hermes/skills/vidau-email/
 *   and write EMAIL_AGENT_ROOT into ~/.hermes/.env (points at this clone).
 * Remote mode (--remote): hermes skills install + GitHub identifier.
 * From-GitHub (--from-github): fetch _manifest.yaml via GitHub API (no raw CDN).
 *
 * Usage:
 *   node scripts/install-skills.mjs --force
 *   node scripts/install-skills.mjs --remote --force
 *   node scripts/install-skills.mjs --from-github --force
 */
import { spawnSync } from "node:child_process";
import { appendFile, cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = (process.env.SKILLS_GITHUB_REPO ?? "vidaudeveloper/email-agent").replace(/\/+$/, "");
const category = process.env.SKILLS_INSTALL_CATEGORY ?? "vidau-email";
const force = process.argv.includes("--force") || process.env.SKILLS_INSTALL_FORCE === "1";
const remote = process.argv.includes("--remote") || process.env.SKILLS_INSTALL_REMOTE === "1";
const fromGithub =
  process.argv.includes("--from-github") || process.env.SKILLS_INSTALL_FROM_GITHUB === "1";
const cli = process.env.SKILLS_CLI?.trim() || "hermes";
const hermesHome = process.env.HERMES_HOME?.trim() || join(homedir(), ".hermes");

async function parseManifestFromRaw(raw) {
  const skills = [];
  let current = null;
  for (const line of raw.split("\n")) {
    const idMatch = line.match(/^\s+-\s+id:\s+(\S+)/);
    const pathMatch = line.match(/^\s+path:\s+(\S+)/);
    if (idMatch) {
      current = { id: idMatch[1] };
      skills.push(current);
    } else if (pathMatch && current && !current.path) {
      current.path = pathMatch[1];
    }
  }
  return skills.filter((s) => s.id && s.path);
}

async function parseManifest() {
  const raw = await readFile(join(repoRoot, "_manifest.yaml"), "utf8");
  return parseManifestFromRaw(raw);
}

async function fetchManifestFromGitHub() {
  const branch = process.env.SKILLS_GITHUB_BRANCH ?? "main";
  const url = `https://api.github.com/repos/${repo}/contents/_manifest.yaml?ref=${branch}`;
  const resp = await fetch(url, {
    headers: {
      Accept: "application/vnd.github+json",
      "User-Agent": "vidau-email-agent-skill-install",
      ...(process.env.GITHUB_TOKEN
        ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` }
        : {}),
    },
  });
  if (!resp.ok) {
    throw new Error(`GitHub API returned ${resp.status} for _manifest.yaml`);
  }
  const data = await resp.json();
  const raw = Buffer.from(data.content, "base64").toString("utf8");
  return parseManifestFromRaw(raw);
}

async function ensureEmailAgentRootEnv() {
  await mkdir(hermesHome, { recursive: true });
  const envPath = join(hermesHome, ".env");
  const line = `EMAIL_AGENT_ROOT=${repoRoot.replace(/\\/g, "/")}`;
  if (!existsSync(envPath)) {
    await writeFile(envPath, `${line}\n`, "utf8");
    console.info(`[skills:install] wrote ${envPath}`);
    return;
  }
  const cur = await readFile(envPath, "utf8");
  if (/^EMAIL_AGENT_ROOT=/m.test(cur)) {
    await writeFile(
      envPath,
      cur.replace(/^EMAIL_AGENT_ROOT=.*$/m, line),
      "utf8",
    );
  } else {
    await appendFile(envPath, `\n${line}\n`, "utf8");
  }
  console.info(`[skills:install] EMAIL_AGENT_ROOT → ${repoRoot}`);
}

async function installLocal(skill) {
  const src = join(repoRoot, skill.path);
  const dest = join(hermesHome, "skills", category, skill.id);
  await rm(dest, { recursive: true, force: true });
  await mkdir(dirname(dest), { recursive: true });
  await cp(src, dest, { recursive: true });
}

function installRemote(skill) {
  const identifier = `${repo}/${skill.path}`;
  const args = ["skills", "install", identifier, "--yes", "--category", category];
  if (force) args.push("--force");
  return spawnSync(cli, args, { stdio: "inherit", encoding: "utf8" });
}

async function main() {
  const skills = fromGithub ? await fetchManifestFromGitHub() : await parseManifest();
  const mode = fromGithub
    ? "GitHub API manifest + remote install"
    : remote
      ? "remote (GitHub API)"
      : "local copy";
  console.info(
    `[skills:install] ${mode}: ${skills.length} skill(s) → ${hermesHome}/skills/${category}/\n`,
  );

  if (!fromGithub && !remote) {
    await ensureEmailAgentRootEnv();
  }

  let failed = 0;
  const useRemote = remote || fromGithub;
  for (const skill of skills) {
    console.info(`→ ${skill.id}`);
    if (useRemote) {
      const r = installRemote(skill);
      if (r.status !== 0) {
        console.error(`✗ ${skill.id} failed (exit ${r.status})`);
        failed += 1;
      } else {
        console.info(`✓ ${skill.id}\n`);
      }
    } else {
      try {
        await installLocal(skill);
        console.info(`✓ ${skill.id}\n`);
      } catch (err) {
        console.error(`✗ ${skill.id}: ${err.message}`);
        failed += 1;
      }
    }
  }

  if (failed) {
    console.error(`[skills:install] done with ${failed} failure(s)`);
    process.exit(1);
  }
  console.info("[skills:install] all skills installed");
  console.info(
    "[skills:install] send path: python3 \"$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py\" … (SMTP first, else Resend)",
  );
  console.info(
    "[skills:install] prefer isolated runtime: bash hermes/install.sh && bash hermes/run.sh chat",
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
