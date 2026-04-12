import os
import json
import pytest
from datetime import datetime

from wiki_lib import diagnostics

@pytest.fixture
def mock_diagnostics_dir(tmpdir, monkeypatch):
    monkeypatch.setattr(diagnostics, 'DIAGNOSTICS_DIR', str(tmpdir))
    return str(tmpdir)

def test_content_hash():
    content = "Hello World"
    # Should be deterministic
    assert diagnostics._content_hash(content) == diagnostics._content_hash(content)
    assert diagnostics._content_hash(content) != diagnostics._content_hash(content + "!")

def test_save_and_load_diagnostics(mock_diagnostics_dir):
    slug, kind = "test_topic", "topic"
    data = {"hello": "world"}
    
    # Not existing initially
    assert diagnostics.load_diagnostics(slug, kind) is None
    
    diagnostics.save_diagnostics(slug, kind, data)
    loaded = diagnostics.load_diagnostics(slug, kind)
    assert loaded == data

def test_set_issue_status(mock_diagnostics_dir):
    slug, kind = "test_topic", "topic"
    data = {
        "slug": slug,
        "kind": kind,
        "issues": [
            {"id": "iss_001", "status": "open"},
            {"id": "iss_002", "status": "applied"}
        ]
    }
    diagnostics.save_diagnostics(slug, kind, data)
    
    # Update successful
    assert diagnostics.set_issue_status(slug, kind, "iss_001", "dismissed") is True
    
    loaded = diagnostics.load_diagnostics(slug, kind)
    assert loaded["issues"][0]["status"] == "dismissed"
    assert "dismissed_at" in loaded["issues"][0]
    
    # Update missing
    assert diagnostics.set_issue_status(slug, kind, "iss_003", "open") is False

def test_refresh_stale_status(mock_diagnostics_dir):
    slug, kind = "test_topic", "topic"
    data = {
        "slug": slug,
        "kind": kind,
        "content_hash": "old_hash",
        "issues": [
            {"id": "iss_001", "status": "open"},
            {"id": "iss_002", "status": "dismissed"}
        ]
    }
    diagnostics.save_diagnostics(slug, kind, data)
    
    # Matching hash, shouldn't change
    assert diagnostics.refresh_stale_status(slug, kind, "old_hash") == 0
    
    # Different hash, open issues become stale
    assert diagnostics.refresh_stale_status(slug, kind, "new_hash") == 1
    
    loaded = diagnostics.load_diagnostics(slug, kind)
    assert loaded["issues"][0]["status"] == "stale"
    assert "stale_at" in loaded["issues"][0]
    
    assert loaded["issues"][1]["status"] == "dismissed"  # Untouched

def test_get_open_issues(mock_diagnostics_dir):
    slug, kind = "test_topic", "topic"
    data = {
        "slug": slug,
        "kind": kind,
        "issues": [
            {"id": "iss_001", "status": "open"},
            {"id": "iss_002", "status": "stale"}
        ]
    }
    diagnostics.save_diagnostics(slug, kind, data)
    issues = diagnostics.get_open_issues(slug, kind)
    assert len(issues) == 1
    assert issues[0]["id"] == "iss_001"
