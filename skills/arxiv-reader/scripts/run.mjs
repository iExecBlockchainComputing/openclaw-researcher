import fs from 'node:fs';
import path from 'node:path';

// Loading SKILL.md does not register Prismer's TypeScript tools in OpenClaw.
// This adapter executes the exported functions directly with Node type stripping.
const [operation, id, ...options] = process.argv.slice(2);
const names = { abstract: 'arxiv_abstract', sections: 'arxiv_sections', fetch: 'arxiv_fetch' };
const idPattern = /^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?\/\d{7})(?:v[1-9]\d*)?$/;
function option(name) {
  const i = options.indexOf(name);
  return i < 0 ? undefined : options[i + 1];
}
try {
  if (!names[operation] || !idPattern.test(id ?? '')) {
    throw new Error('Usage: run.mjs abstract|sections|fetch ARXIV_ID [--cache-dir DIR] [--output FILE]');
  }
  if (operation !== 'abstract' && !/v[1-9]\d*$/.test(id)) {
    throw new Error('Pin an explicit arXiv version for source reads to avoid stale unversioned caches');
  }
  const cache = option('--cache-dir');
  if (cache) process.env.ARXIV_CACHE_DIR = path.resolve(cache);
  process.env.ARXIV_STANDALONE_ONLY = '1';
  const timer = setTimeout(() => {
    process.stderr.write('arXiv read exceeded 50 seconds\n');
    process.exit(1);
  }, 50_000);
  try {
    const { default: skill } = await import('../index.ts');
    const tool = skill.tools.find(t => t.name === names[operation]);
    const result = await tool.execute({ arxiv_id: id, remove_appendix: false, figure_paths: false });
    if (operation === 'fetch' && !result.content?.trim()) throw new Error('Empty source');
    const json = JSON.stringify(result, null, 2) + '\n';
    const output = option('--output');
    if (output) {
      fs.writeFileSync(output, json);
      process.stdout.write(JSON.stringify({ output, operation, arxiv_id: id, cached: result.cached }) + '\n');
    } else process.stdout.write(json);
  } finally { clearTimeout(timer); }
} catch (error) {
  process.stderr.write(error.message + '\n');
  process.exitCode = 1;
}
