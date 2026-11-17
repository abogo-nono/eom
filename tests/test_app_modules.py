"""Tests for settings, theme, i18n, updater, integration, widgets helpers, workers and entry-point parsing."""

from __future__ import annotations

import json
import re
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QSize

import i18n
import integration
import main
import risk
import settings
import theme
import updater
import widgets

# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------


def test_settings_defaults_and_types() -> None:
    assert settings.get("theme") == "dark"
    assert settings.get("allow_map_tiles") is False  # privacy: network is opt-in
    assert settings.get("check_updates") is False
    settings.set("recursive", True)
    assert settings.get("recursive") is True
    settings.set("custom_categories", ["location"])
    assert settings.get("custom_categories") == ["location"]  # single-item list survives INI
    with pytest.raises(KeyError):
        settings.set("nope", 1)


def test_settings_recent(tmp_path: Path) -> None:
    files = []
    for i in range(12):
        f = tmp_path / f"{i}.jpg"
        f.touch()
        files.append(str(f))
        settings.add_recent(str(f))
    recent = settings.recent()
    assert recent[0] == files[-1] and len(recent) == settings.MAX_RECENT
    settings.add_recent(files[5])
    assert settings.recent()[0] == files[5] and recent.count(files[5]) <= 1
    assert settings.get("last_dir") == str(tmp_path)
    settings.clear_recent()
    assert settings.recent() == []


# ---------------------------------------------------------------------------
# theme / i18n
# ---------------------------------------------------------------------------


def test_every_stylesheet_token_is_defined() -> None:
    for name in ("dark", "light"):
        css = theme.render_stylesheet(name)
        assert re.findall(r"@[a-z_]+", css) == [], f"undefined token in {name} theme"
    assert set(theme.PALETTES["dark"]) == set(theme.PALETTES["light"])


def test_theme_apply(qapp) -> None:
    assert theme.apply(qapp, "light") == "light"
    assert theme.color("bg") == theme.PALETTES["light"]["bg"]
    assert theme.apply(qapp, "bogus") == "dark"
    assert theme.resolve("system") in ("dark", "light")


def test_french_translation_loads(qapp) -> None:
    from PySide6.QtCore import QCoreApplication

    assert i18n.install(qapp, "fr") == "fr"
    try:
        assert QCoreApplication.translate("risk", "High") == "Élevé"
        assert QCoreApplication.translate("profiles", "Social media sharing") == "Partage sur les réseaux sociaux"
    finally:
        i18n.install(qapp, "en")
    assert QCoreApplication.translate("risk", "High") == "High"


def test_translations_are_complete() -> None:
    import xml.etree.ElementTree as ET

    root = ET.parse(Path(__file__).parent.parent / "translations" / "eom_fr.ts").getroot()
    unfinished = [m.findtext("source") for m in root.iter("message") if m.find("translation").get("type")]
    assert unfinished == []


# ---------------------------------------------------------------------------
# updater
# ---------------------------------------------------------------------------


def test_version_comparison() -> None:
    assert updater.parse_version("v2.10.1-beta") == (2, 10, 1)
    assert updater.is_newer("v2.1.0", "2.0.0")
    assert updater.is_newer("3", "2.9.9")
    assert not updater.is_newer("v2.0", "2.0.0")
    assert not updater.is_newer("garbage", "2.0.0")


def test_parse_release() -> None:
    payload = json.dumps({"tag_name": "v9.9.9", "html_url": "https://example.org/r"}).encode()
    assert updater.parse_release(payload) == ("v9.9.9", "https://example.org/r")
    assert updater.parse_release(b"not json") is None
    assert updater.parse_release(b"[]") is None


# ---------------------------------------------------------------------------
# integration (Linux file managers)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux integration only")
def test_integration_install_uninstall(tmp_path: Path) -> None:
    assert not integration.is_installed(tmp_path)
    created = integration.install(tmp_path)
    assert integration.is_installed(tmp_path)
    script = tmp_path / ".local/share/nautilus/scripts" / integration.ACTIONS["remove"]
    assert script.stat().st_mode & 0o100
    assert "--remove" in script.read_text()
    assert len(created) == 6

    # A user file with the same name is never overwritten nor deleted.
    foreign = tmp_path / ".local/share/applications/eom.desktop"
    foreign.write_text("[Desktop Entry]\nName=Mine\n")
    integration.uninstall(tmp_path)
    assert foreign.exists() and not script.exists()


# ---------------------------------------------------------------------------
# widgets helpers
# ---------------------------------------------------------------------------


def test_map_projection_and_zoom() -> None:
    x, y = widgets.lonlat_to_pixel(0, 0, 0)
    assert (x, y) == pytest.approx((128, 128))
    assert widgets.fit_zoom([(48.85, 2.29)], 300, 200) == 15
    near = widgets.fit_zoom([(48.85, 2.29), (48.86, 2.30)], 300, 200)
    far = widgets.fit_zoom([(48.85, 2.29), (-33.8, 151.2)], 300, 200)
    assert near > far >= 0


def test_map_widget_makes_no_request_without_consent(qtbot) -> None:
    w = widgets.MapWidget()
    qtbot.addWidget(w)
    w.set_points([(48.85, 2.29)])
    w.resize(300, 200)
    w.repaint()
    assert not w.network_enabled() and not w._pending
    assert "openstreetmap.org" in w.osm_url()


def test_render_preview_image_and_pdf(qtbot, tmp_path: Path) -> None:
    img = tmp_path / "big.png"
    Image.new("RGB", (1000, 500), (1, 2, 3)).save(img)
    out = widgets.render_preview(str(img), QSize(200, 200))
    assert out is not None and out.width() == 200

    from pypdf import PdfWriter

    pdf = tmp_path / "x.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=100)
    with open(pdf, "wb") as f:
        writer.write(f)
    assert widgets.render_preview(str(pdf), QSize(100, 100)) is not None
    assert widgets.render_preview(str(tmp_path / "missing.mp3"), QSize(100, 100)) is None


def test_edit_dialog_collects_fields(qtbot) -> None:
    dlg = widgets.EditDialog("x.jpg", {"IFD0:Artist": "Bob"})
    qtbot.addWidget(dlg)
    check, edit = dlg._fields["Author"]
    assert edit.text() == "Bob"
    check.setChecked(True)
    edit.setText("Alice")
    dlg._hours.setValue(-2)
    assert dlg.fields() == {"Author": "Alice"}
    assert dlg.shift() == timedelta(hours=-2)


def test_custom_selection_dialog(qtbot) -> None:
    data = {"IFD0:Artist": "Bob", "IFD0:Make": "Canon", "System:FileSize": "1 kB"}
    dlg = widgets.CustomSelectionDialog(data, {"identity"})
    qtbot.addWidget(dlg)
    assert dlg.keys() == ["IFD0:Artist"]
    assert dlg.categories() == {"identity"}
    dlg._select({"device"})
    assert dlg.keys() == ["IFD0:Make"]
    batch = widgets.CustomSelectionDialog(None, {"location"})
    qtbot.addWidget(batch)
    assert batch.keys() is None and batch.categories() == {"location"}


# ---------------------------------------------------------------------------
# workers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def test_main_dispatches_cli(capsys) -> None:
    assert main.main(["profiles"]) == 0
    assert "social" in capsys.readouterr().out


def test_parse_gui_args(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main.parse_gui_args([]) == []
    assert main.parse_gui_args(["--remove", "a.jpg", "b.pdf"]) == [str(tmp_path / "a.jpg"), str(tmp_path / "b.pdf")]


def test_icons_render_every_shape(qapp) -> None:
    import icons

    for name in icons.SHAPES:
        assert not icons.pixmap(name, 16).isNull(), name
    assert set(icons.CATEGORY_ICONS) == set(risk.CATEGORIES)
    assert icons.for_file("x.MP3") == "music" and icons.for_file("x.docx") == "file-text"
