from orche.redact import redact


def test_redacts_openrouter_key():
    text = "here's my key: sk-or-v1-" + "a" * 60
    assert "sk-or-v1-" not in redact(text)
    assert "[REDACTED]" in redact(text)


def test_redacts_anthropic_key():
    text = "ANTHROPIC_API_KEY=sk-ant-" + "b" * 30
    assert "sk-ant-" not in redact(text)


def test_redacts_github_token():
    text = "token: ghp_" + "c" * 40
    assert "ghp_" not in redact(text)


def test_redacts_aws_access_key():
    text = "AWS_ACCESS_KEY_ID=AKIAABCDEFGHIJKLMNOP"  # gitleaks:allow
    assert "AKIA" not in redact(text)


def test_redacts_slack_token():
    text = "SLACK_TOKEN=xoxb-" + "1234567890"
    assert "xoxb-" not in redact(text)


def test_redacts_private_key_block():
    text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"  # gitleaks:allow
        "MIIEpAIBAAKCAQEA...\nmore lines here\n"
        "-----END RSA PRIVATE KEY-----"
    )
    result = redact(text)
    assert "MIIEpAIBAAKCAQEA" not in result
    assert "[REDACTED]" in result


def test_leaves_ordinary_text_untouched():
    text = "def foo():\n    return 42\n"
    assert redact(text) == text


def test_leaves_short_sk_prefix_untouched():
    # "sk-" alone or with a short suffix shouldn't false-positive on ordinary words
    text = "the sk-8 bus route was late"
    assert redact(text) == text
