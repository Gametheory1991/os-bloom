from pathlib import Path

from collector.main import build, main

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_uses_explicit_ui_path(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_PATH", str(REPO_ROOT / "config.yaml"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("SERVE_UI", "1")
    monkeypatch.setenv("UI_PATH", str(REPO_ROOT / "ui"))
    app, _scheduler = build()
    assert any(getattr(route, "name", None) == "ui" for route in app.routes)


def test_main_honors_port_env(monkeypatch):
    called = {}

    def fake_run(app, host, port):
        called["host"] = host
        called["port"] = port

    monkeypatch.setenv("PORT", "12345")
    monkeypatch.setattr("collector.main.uvicorn.run", fake_run)
    monkeypatch.setattr("collector.main.build", lambda: ("app", None))
    main()
    assert called == {"host": "0.0.0.0", "port": 12345}
