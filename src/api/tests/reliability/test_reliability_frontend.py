"""Тести надійності фронтенду (R-12, R-13): тайм-аут запиту та розрізнення помилок у getMe.

Справжній app.js виконується в Node.js у ізольованому контексті з підміненими fetch і сховищем,
тож тести є ін'єкцією збою на мережевому рівні. Без Node.js вони пропускаються
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
APP_JS = Path(__file__).resolve().parents[2] / "web" / "app.js"

HARNESS = """
const fs = require('fs');
const vm = require('vm');

function makeStorage() {
  const data = {};
  return {
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => { data[key] = String(value); },
    removeItem: (key) => { delete data[key]; }
  };
}

const activeTimers = new Set();
const logged = [];

function load(overrides) {
  const context = Object.assign({
    window: { location: { pathname: '/app/games.html', href: '' } },
    localStorage: makeStorage(),
    sessionStorage: makeStorage(),
    AbortController,
    setTimeout: (fn, ms) => { const id = setTimeout(fn, ms); activeTimers.add(id); return id; },
    clearTimeout: (id) => { activeTimers.delete(id); clearTimeout(id); },
    console: { error: (...args) => logged.push(args.join(' ')) }
  }, overrides);
  vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
  return { app: context.window.App, context };
}

function jsonResponse(status, payload) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'stub',
    headers: { get: (name) => (name === 'content-type' ? 'application/json' : null) },
    json: async () => payload,
    text: async () => JSON.stringify(payload)
  };
}

function abortable(opts) {
  return new Promise((resolve, reject) => {
    opts.signal.addEventListener('abort', () => reject(new Error('aborted')));
  });
}

async function outcome(promise) {
  try {
    return { value: await promise };
  } catch (error) {
    return { error: { code: error.code, status: error.status, message: error.message } };
  }
}
"""


def run_node(body, *args):
    completed = subprocess.run(
        [NODE, "-e", HARNESS + body, str(APP_JS), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


needs_node = pytest.mark.skipif(NODE is None, reason="Node.js is required to exercise the browser JavaScript")


@pytest.mark.technical
@needs_node
def test_request_to_unresponsive_server_fails_with_timeout_error():
    result = run_node("""
(async () => {
  const { app } = load({ fetch: (url, opts) => abortable(opts) });
  app.API_TIMEOUT_MS = 30;
  const started = Date.now();
  const result = await outcome(app.api('GET', '/games'));
  console.log(JSON.stringify({ result, elapsed: Date.now() - started, timers: activeTimers.size }));
})();
""")

    assert result["result"]["error"]["code"] == "TIMEOUT"
    assert result["result"]["error"]["status"] == 0
    assert result["elapsed"] < 5000
    assert result["timers"] == 0


@pytest.mark.technical
@needs_node
def test_timeout_also_covers_reading_the_response_body():
    result = run_node("""
(async () => {
  const fetchStub = (url, opts) => Promise.resolve({
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: () => abortable(opts)
  });
  const { app } = load({ fetch: fetchStub });
  app.API_TIMEOUT_MS = 30;
  const result = await outcome(app.api('GET', '/games'));
  console.log(JSON.stringify({ result, timers: activeTimers.size }));
})();
""")

    assert result["result"]["error"]["code"] == "TIMEOUT"
    assert result["timers"] == 0


@pytest.mark.technical
@needs_node
@pytest.mark.parametrize("status, payload", [(200, {"ok": True}), (503, {"error": {"code": "SERVICE_UNAVAILABLE"}})])
def test_timer_is_cleared_after_a_fast_response_and_errors_keep_their_code(status, payload):
    result = run_node(
        """
(async () => {
  const status = Number(process.argv[2]);
  const payload = JSON.parse(process.argv[3]);
  const { app } = load({ fetch: async () => jsonResponse(status, payload) });
  const result = await outcome(app.api('GET', '/games'));
  console.log(JSON.stringify({ result, timers: activeTimers.size }));
})();
""",
        str(status),
        json.dumps(payload),
    )

    assert result["timers"] == 0
    if status == 200:
        assert result["result"]["value"] == {"ok": True}
    else:
        assert result["result"]["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert result["result"]["error"]["status"] == 503


@pytest.mark.technical
@needs_node
def test_network_failure_is_still_reported_as_network_error_not_timeout():
    result = run_node("""
(async () => {
  const { app } = load({ fetch: async () => { throw new Error('connection reset'); } });
  const result = await outcome(app.api('GET', '/games'));
  console.log(JSON.stringify({ result }));
})();
""")

    assert result["result"]["error"]["code"] == "NETWORK_ERROR"
    assert "connection reset" in result["result"]["error"]["message"]


GET_ME_SCENARIOS = ["no_session", "unauthorized", "server_unavailable", "timeout", "success"]


@pytest.mark.technical
@needs_node
@pytest.mark.parametrize("scenario", GET_ME_SCENARIOS)
def test_get_me_distinguishes_missing_session_from_server_failure(scenario):
    result = run_node(
        """
(async () => {
  const scenario = process.argv[2];
  const { app, context } = load({});
  let apiCalls = 0;
  if (scenario !== 'no_session') {
    context.localStorage.setItem('access_token', 'token');
    context.localStorage.setItem('user_role', 'player');
  }
  app.api = async () => {
    apiCalls += 1;
    const errors = {
      unauthorized: { status: 401, code: 'UNAUTHORIZED', message: 'Недійсний токен' },
      server_unavailable: { status: 503, code: 'SERVICE_UNAVAILABLE', message: 'Сервіс недоступний' },
      timeout: { status: 0, code: 'TIMEOUT', message: 'Сервер не відповів вчасно' }
    };
    if (errors[scenario]) {
      throw Object.assign(new Error(errors[scenario].message), errors[scenario]);
    }
    return { id: 'user_2', name: 'Марія' };
  };
  const result = await outcome(app.getMe());
  console.log(JSON.stringify({
    result,
    apiCalls,
    logged,
    cached: context.sessionStorage.getItem('user_me')
  }));
})();
""",
        scenario,
    )

    if scenario == "no_session":
        assert result["result"]["value"] is None
        assert result["apiCalls"] == 0
    elif scenario == "unauthorized":
        # 401 означає «немає користувача»: це штатний результат, у лог не пишемо
        assert result["result"]["value"] is None
        assert result["logged"] == []
    elif scenario == "success":
        assert result["result"]["value"] == {"id": "user_2", "name": "Марія"}
        assert json.loads(result["cached"])["id"] == "user_2"
    else:
        # збій сервера не маскується під null: помилка доходить до викликача й потрапляє в лог
        expected_code = "SERVICE_UNAVAILABLE" if scenario == "server_unavailable" else "TIMEOUT"
        assert "value" not in result["result"]
        assert result["result"]["error"]["code"] == expected_code
        assert len(result["logged"]) == 1
        assert expected_code in result["logged"][0]
        assert result["cached"] is None
