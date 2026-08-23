import pytest

from orche.config import ConfigError
from orche.profiles import Profile, load_profiles, save_profile


def test_load_missing_file_returns_empty_dict(tmp_path):
    assert load_profiles(tmp_path / "does-not-exist.toml") == {}


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "profiles.toml"
    profile = Profile(
        name="reviewer",
        base_alias="ox_alpha",
        system_prompt="You are a strict code reviewer.",
        reasoning_effort="high",
        agent_tools="read",
    )
    save_profile(profile, path)

    loaded = load_profiles(path)

    assert loaded["reviewer"] == profile


def test_save_creates_file_and_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "profiles.toml"
    profile = Profile(name="foo", base_alias="ox_alpha", system_prompt="Be foo.")

    save_profile(profile, path)

    assert path.is_file()


def test_save_upserts_without_disturbing_others(tmp_path):
    path = tmp_path / "profiles.toml"
    save_profile(Profile(name="a", base_alias="ox_alpha", system_prompt="A."), path)
    save_profile(Profile(name="b", base_alias="glm", system_prompt="B."), path)
    save_profile(Profile(name="a", base_alias="ox_alpha", system_prompt="A updated."), path)

    loaded = load_profiles(path)

    assert set(loaded) == {"a", "b"}
    assert loaded["a"].system_prompt == "A updated."
    assert loaded["b"].system_prompt == "B."


def test_round_trip_preserves_special_characters(tmp_path):
    path = tmp_path / "profiles.toml"
    tricky = 'Multi-line "quoted" text\nwith a backslash \\ in it.'
    save_profile(Profile(name="tricky", base_alias="ox_alpha", system_prompt=tricky), path)

    loaded = load_profiles(path)

    assert loaded["tricky"].system_prompt == tricky


def test_optional_fields_default_to_none(tmp_path):
    path = tmp_path / "profiles.toml"
    save_profile(Profile(name="plain", base_alias="ox_alpha", system_prompt="Plain."), path)

    loaded = load_profiles(path)

    assert loaded["plain"].reasoning_effort is None
    assert loaded["plain"].agent_tools is None


def test_invalid_name_raises(tmp_path):
    path = tmp_path / "profiles.toml"
    path.write_text(
        '[profiles."Not Valid"]\nbase_alias = "x"\nsystem_prompt = "y"\n', encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="aliases must match"):
        load_profiles(path)


def test_missing_base_alias_raises(tmp_path):
    path = tmp_path / "profiles.toml"
    path.write_text('[profiles.foo]\nsystem_prompt = "y"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="missing a string 'base_alias'"):
        load_profiles(path)


def test_missing_system_prompt_raises(tmp_path):
    path = tmp_path / "profiles.toml"
    path.write_text('[profiles.foo]\nbase_alias = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="missing a string 'system_prompt'"):
        load_profiles(path)


def test_invalid_reasoning_effort_raises(tmp_path):
    path = tmp_path / "profiles.toml"
    path.write_text(
        '[profiles.foo]\nbase_alias = "x"\nsystem_prompt = "y"\nreasoning_effort = "ultra"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="reasoning_effort must be one of"):
        load_profiles(path)


def test_invalid_agent_tools_raises(tmp_path):
    path = tmp_path / "profiles.toml"
    path.write_text(
        '[profiles.foo]\nbase_alias = "x"\nsystem_prompt = "y"\nagent_tools = "godmode"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="agent_tools must be one of"):
        load_profiles(path)


def test_env_var_overrides_cwd(tmp_path, monkeypatch):
    real = tmp_path / "real.toml"
    save_profile(Profile(name="foo", base_alias="ox_alpha", system_prompt="Foo."), real)
    monkeypatch.setenv("ORCHE_PROFILES_PATH", str(real))

    loaded = load_profiles()

    assert set(loaded) == {"foo"}
