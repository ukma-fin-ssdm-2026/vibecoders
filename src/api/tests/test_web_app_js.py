import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")


@pytest.mark.technical
@pytest.mark.skipif(NODE is None, reason="Node.js is required to exercise the browser JavaScript")
def test_app_date_and_retry_after_helpers_keep_their_behavior():
    app_js = Path(__file__).resolve().parents[1] / "web" / "app.js"
    script = """
const fs = require('fs');
const vm = require('vm');

const response = {
  ok: false,
  status: 429,
  statusText: 'Too Many Requests',
  headers: {
    get(name) {
      if (name === 'content-type') return 'application/json';
      if (name === 'Retry-After') return '30 seconds';
      return null;
    }
  },
  json: async () => ({ error: { code: 'RATE_LIMITED', message: 'Wait' } })
};
const context = {
  window: {},
  fetch: async () => response
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);

(async () => {
  const app = context.window.App;
  let retryAfter;
  try {
    await app.api('GET', '/test');
  } catch (error) {
    retryAfter = error.retryAfter;
  }
  console.log(JSON.stringify({
    invalidDate: app.formatDateTime('not-a-date'),
    invalidSlot: app.formatSlot('not-a-date', '90 minutes'),
    slot: app.formatSlot('2026-01-02T10:00:00', '90 minutes'),
    retryAfter
  }));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""

    completed = subprocess.run(
        [NODE, "-e", script, str(app_js)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "invalidDate": "not-a-date",
        "invalidSlot": "",
        "slot": "10:00–11:30",
        "retryAfter": 30,
    }
