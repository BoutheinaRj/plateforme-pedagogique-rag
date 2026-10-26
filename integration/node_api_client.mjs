#!/usr/bin/env node
/**
 * Simple Node client for Astro KB FastAPI /api/answer endpoint.
 *
 * Usage:
 *   node integration/node_api_client.mjs --question "Comment conjuguer avoir?" --grade 3 --language fr --subject francais --age 8
 */

const DEFAULT_BASE_URL = process.env.ASTRO_API_BASE_URL || "http://127.0.0.1:8000";

function parseArgs(argv) {
  const out = {
    baseUrl: DEFAULT_BASE_URL,
    question: null,
    grade: undefined,
    language: "auto",
    subject: undefined,
    age: undefined,
    timeoutMs: 60000,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const k = argv[i];
    const v = argv[i + 1];
    if (!k.startsWith("--")) {
      continue;
    }

    if (k === "--question") out.question = v;
    if (k === "--base-url") out.baseUrl = v;
    if (k === "--grade") out.grade = Number(v);
    if (k === "--language") out.language = v;
    if (k === "--subject") out.subject = v;
    if (k === "--age") out.age = Number(v);
    if (k === "--timeout-ms") out.timeoutMs = Number(v);
  }

  if (!out.question) {
    throw new Error("Missing --question");
  }

  return out;
}

async function askApi({ baseUrl, question, grade, language, subject, age, timeoutMs }) {
  const payload = {
    question,
    grade,
    language,
    subject,
    age,
    conversation: [],
  };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const text = await response.text();
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${text}`);
    }

    return JSON.parse(text);
  } finally {
    clearTimeout(timer);
  }
}

function printResult(result) {
  console.log("=".repeat(80));
  console.log("API RESPONSE");
  console.log("=".repeat(80));
  console.log(`Mode: ${result.mode}`);
  console.log(`Retrieval mode: ${result.retrieval_mode}`);
  console.log("\nAnswer:");
  console.log(result.answer || "");

  const sources = result.sources || [];
  console.log(`\nSources count: ${sources.length}`);
  sources.slice(0, 5).forEach((src, idx) => {
    console.log(
      `  [${idx + 1}] ${src.source_file} | grade=${src.grade} | subject=${src.subject} | score=${src.score}`
    );
  });
}

async function main() {
  try {
    const args = parseArgs(process.argv);
    const result = await askApi(args);
    printResult(result);
  } catch (err) {
    console.error(`ERROR: ${err.message}`);
    process.exitCode = 1;
  }
}

main();
