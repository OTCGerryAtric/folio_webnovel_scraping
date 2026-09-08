"""Tests for settings: CLI arguments merged over an optional TOML file."""
import pytest

from scraper.config import Settings, build_settings, load_site_config


def write_toml(tmp_path, text):
    path = tmp_path / "site.toml"
    path.write_text(text, encoding="utf-8")
    return path


# --- loading ----------------------------------------------------------------


def test_a_site_file_is_loaded(tmp_path):
    path = write_toml(
        tmp_path,
        'url_template = "http://example.com/{n}"\ncontent_selector = "#c"\ndelay = 2.5\n',
    )

    config = load_site_config(path)

    assert config["url_template"] == "http://example.com/{n}"
    assert config["content_selector"] == "#c"
    assert config["delay"] == 2.5


def test_an_unknown_key_is_rejected(tmp_path):
    path = write_toml(tmp_path, 'url_template = "http://x/{n}"\nsprocket = 3\n')

    with pytest.raises(ValueError, match="sprocket"):
        load_site_config(path)


def test_a_missing_site_file_is_reported_clearly(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_site_config(tmp_path / "nope.toml")


# --- merging ----------------------------------------------------------------


def test_settings_can_come_entirely_from_the_command_line():
    settings = build_settings({"url_template": "http://example.com/{n}", "out": "b.md"})

    assert settings.url_template == "http://example.com/{n}"
    assert settings.out == "b.md"


def test_command_line_arguments_beat_the_site_file():
    settings = build_settings(
        {"url_template": "http://cli/{n}", "out": "b.md"},
        {"url_template": "http://file/{n}", "delay": 9.0},
    )

    assert settings.url_template == "http://cli/{n}"
    assert settings.delay == 9.0, "unset CLI values fall through to the file"


def test_none_valued_arguments_do_not_override_the_file():
    settings = build_settings(
        {"url_template": None, "out": "b.md", "delay": None},
        {"url_template": "http://file/{n}", "delay": 4.0},
    )

    assert settings.url_template == "http://file/{n}"
    assert settings.delay == 4.0


def test_defaults_are_applied_when_nothing_sets_a_value():
    settings = build_settings({"url_template": "http://x/{n}", "out": "b.md"})

    assert settings.start == 1
    assert settings.step == 1
    assert settings.end is None
    assert settings.delay == 1.5
    assert settings.max_misses == 3
    assert settings.refresh is False
    assert settings.remove_selectors == []


# --- validation -------------------------------------------------------------


def test_a_missing_url_template_is_rejected():
    with pytest.raises(ValueError, match="url"):
        build_settings({"out": "b.md"})


def test_a_template_without_the_placeholder_is_rejected():
    with pytest.raises(ValueError, match=r"\{n\}"):
        build_settings({"url_template": "http://example.com/page", "out": "b.md"})


def test_a_missing_output_path_is_rejected():
    with pytest.raises(ValueError, match="out"):
        build_settings({"url_template": "http://example.com/{n}"})


def test_an_end_before_the_start_is_rejected():
    with pytest.raises(ValueError, match="end"):
        build_settings(
            {"url_template": "http://x/{n}", "out": "b.md", "start": 10, "end": 2}
        )


def test_a_non_positive_step_is_rejected():
    with pytest.raises(ValueError, match="step"):
        build_settings({"url_template": "http://x/{n}", "out": "b.md", "step": 0})


# --- derived values ---------------------------------------------------------


def test_the_url_for_a_number_is_built_from_the_template():
    settings = build_settings({"url_template": "http://x/ch-{n}", "out": "b.md"})

    assert settings.url_for(12) == "http://x/ch-12"


def test_the_cache_directory_is_derived_from_the_template_when_unset():
    a = build_settings({"url_template": "http://example.com/ch-{n}", "out": "b.md"})
    b = build_settings({"url_template": "http://other.com/ch-{n}", "out": "b.md"})

    assert a.cache_path != b.cache_path
    assert "example.com" in str(a.cache_path)


def test_an_explicit_cache_directory_is_used_as_given():
    settings = build_settings(
        {"url_template": "http://x/{n}", "out": "b.md", "cache_dir": "/tmp/mine"}
    )

    assert str(settings.cache_path).replace("\\", "/").endswith("/tmp/mine")


def test_settings_are_a_settings_instance():
    assert isinstance(build_settings({"url_template": "http://x/{n}", "out": "b.md"}), Settings)


# --- boilerplate removal ----------------------------------------------------


def test_boilerplate_defaults_are_applied():
    settings = build_settings({"url_template": "http://x/{n}", "out": "b.md"})

    assert settings.dedupe is True
    assert settings.dedupe_threshold == 0.6
    assert settings.strip_patterns == []


def test_a_threshold_outside_zero_to_one_is_rejected():
    with pytest.raises(ValueError, match="threshold"):
        build_settings(
            {"url_template": "http://x/{n}", "out": "b.md", "dedupe_threshold": 1.5}
        )


def test_a_site_file_can_supply_strip_patterns(tmp_path):
    path = write_toml(
        tmp_path,
        # TOML literal strings (single quotes) keep backslashes as written,
        # which is what a regex wants.
        """url_template = "http://x/{n}"
strip_patterns = ['^Chapter \\d+']
""",
    )

    settings = build_settings({"out": "b.md"}, load_site_config(path))

    assert settings.strip_patterns == [r"^Chapter \d+"]
