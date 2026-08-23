import pytest

from orche.config import ConfigError, load_models


def write(tmp_path, text):
    path = tmp_path / "models.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_bundled_default():
    models = load_models()
    assert "ox_alpha" in models
    assert models["ox_alpha"].id == "stealth/ox-alpha"


def test_loads_valid_custom_file(tmp_path):
    path = write(
        tmp_path,
        """
        [models.foo]
        id = "acme/foo"
        description = "A foo model."
        """,
    )
    models = load_models(path)
    assert models["foo"].id == "acme/foo"
    assert models["foo"].fallback is None


def test_fallback_resolves(tmp_path):
    path = write(
        tmp_path,
        """
        [models.foo]
        id = "acme/foo"
        description = "Foo."
        fallback = "bar"

        [models.bar]
        id = "acme/bar"
        description = "Bar."
        """,
    )
    models = load_models(path)
    assert models["foo"].fallback == "bar"


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="could not read"):
        load_models(tmp_path / "does-not-exist.toml")


def test_no_models_section_raises(tmp_path):
    path = write(tmp_path, "title = \"empty\"\n")
    with pytest.raises(ConfigError, match="no \\[models\\.\\*\\] entries"):
        load_models(path)


def test_missing_id_raises(tmp_path):
    path = write(tmp_path, '[models.foo]\ndescription = "no id"\n')
    with pytest.raises(ConfigError, match="missing a string 'id'"):
        load_models(path)


def test_missing_description_raises(tmp_path):
    path = write(tmp_path, '[models.foo]\nid = "acme/foo"\n')
    with pytest.raises(ConfigError, match="missing a string 'description'"):
        load_models(path)


def test_unresolved_fallback_raises(tmp_path):
    path = write(
        tmp_path,
        """
        [models.foo]
        id = "acme/foo"
        description = "Foo."
        fallback = "ghost"
        """,
    )
    with pytest.raises(ConfigError, match="unknown alias"):
        load_models(path)


def test_self_fallback_raises(tmp_path):
    path = write(
        tmp_path,
        """
        [models.foo]
        id = "acme/foo"
        description = "Foo."
        fallback = "foo"
        """,
    )
    with pytest.raises(ConfigError, match="cannot reference itself"):
        load_models(path)


def test_invalid_alias_raises(tmp_path):
    path = write(tmp_path, '[models."Not Valid"]\nid = "acme/x"\ndescription = "x"\n')
    with pytest.raises(ConfigError, match="aliases must match"):
        load_models(path)


def test_max_tokens_parsed(tmp_path):
    path = write(
        tmp_path,
        '[models.foo]\nid = "acme/foo"\ndescription = "Foo."\nmax_tokens = 4000\n',
    )
    models = load_models(path)
    assert models["foo"].max_tokens == 4000


def test_max_tokens_must_be_positive_int(tmp_path):
    path = write(
        tmp_path,
        '[models.foo]\nid = "acme/foo"\ndescription = "Foo."\nmax_tokens = -1\n',
    )
    with pytest.raises(ConfigError, match="positive integer"):
        load_models(path)


def test_agent_tools_parsed(tmp_path):
    path = write(
        tmp_path,
        '[models.foo]\nid = "acme/foo"\ndescription = "Foo."\nagent_tools = "full"\n',
    )
    models = load_models(path)
    assert models["foo"].agent_tools == "full"


def test_agent_tools_defaults_to_none(tmp_path):
    path = write(tmp_path, '[models.foo]\nid = "acme/foo"\ndescription = "Foo."\n')
    models = load_models(path)
    assert models["foo"].agent_tools is None


def test_agent_tools_rejects_unknown_tier(tmp_path):
    path = write(
        tmp_path,
        '[models.foo]\nid = "acme/foo"\ndescription = "Foo."\nagent_tools = "godmode"\n',
    )
    with pytest.raises(ConfigError, match="agent_tools must be one of"):
        load_models(path)


def test_agent_mode_flag_applies_to_all_models(tmp_path, monkeypatch):
    path = write(
        tmp_path,
        """
        [models.foo]
        id = "acme/foo"
        description = "Foo."

        [models.bar]
        id = "acme/bar"
        description = "Bar."
        """,
    )
    monkeypatch.setenv("ORCHE_AGENT_MODE", "full")
    models = load_models(path)
    assert models["foo"].agent_tools == "full"
    assert models["bar"].agent_tools == "full"


def test_agent_mode_flag_does_not_override_explicit_per_model_setting(tmp_path, monkeypatch):
    path = write(
        tmp_path,
        """
        [models.foo]
        id = "acme/foo"
        description = "Foo."
        agent_tools = "read"
        """,
    )
    monkeypatch.setenv("ORCHE_AGENT_MODE", "full")
    models = load_models(path)
    assert models["foo"].agent_tools == "read"


def test_agent_mode_flag_rejects_invalid_tier(tmp_path, monkeypatch):
    path = write(tmp_path, '[models.foo]\nid = "acme/foo"\ndescription = "Foo."\n')
    monkeypatch.setenv("ORCHE_AGENT_MODE", "godmode")
    with pytest.raises(ConfigError, match="ORCHE_AGENT_MODE must be one of"):
        load_models(path)


def test_env_var_overrides_cwd(tmp_path, monkeypatch):
    real = write(tmp_path, '[models.foo]\nid = "acme/foo"\ndescription = "Foo."\n')
    monkeypatch.setenv("ORCHE_MODELS_PATH", str(real))
    models = load_models()
    assert set(models) == {"foo"}
