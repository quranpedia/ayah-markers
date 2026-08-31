import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_number_boxes", ROOT / "scripts" / "build_number_boxes.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_number_preview_exposes_its_marker_and_digit_for_the_placement_editor():
    markup = module.card_svg(
        "0 0 100 100",
        "",
        {"cx": 50, "cy": 50, "width": 40, "height": 40},
        "٧",
        marker_id="example-marker",
        digit_count=1,
    )

    assert 'data-marker-id="example-marker"' in markup
    assert 'data-digit-count="1"' in markup


def test_the_sheet_draws_every_digit_count_in_the_marker_s_one_box():
    import json

    collection = json.loads((ROOT / "collection.json").read_text())
    number = collection["markers"][0]["number"]
    markup = module.card_svg("0 0 100 100", "", number, "255")

    assert f'x="{number["cx"]:.1f}"' in markup and f'y="{number["cy"]:.1f}"' in markup


def test_number_preview_preserves_digit_shapes_when_fitting_its_box():
    narrow = module.card_svg("0 0 100 100", "", {"cx": 50, "cy": 50, "width": 20, "height": 40}, "255")
    wide = module.card_svg("0 0 100 100", "", {"cx": 50, "cy": 50, "width": 90, "height": 40}, "255")

    # the numeral shrinks to fit; it is never stretched or squeezed to the width
    assert "textLength" not in narrow and "lengthAdjust" not in narrow
    assert 'font-size="10.8"' in narrow
    assert float(wide.split('font-size="')[1].split('"')[0]) > 10.8


def test_number_preview_normalizes_all_marker_artwork_to_a_shared_viewbox():
    markup = module.card_svg(
        "20 -40 200 400",
        "",
        {"cx": 120, "cy": 160, "width": 80, "height": 80},
        "٧",
    )

    assert '<svg viewBox="0 0 1000 1000"' in markup
    assert 'transform="translate(250.0 0.0) scale(2.500000) translate(-20.0 40.0)"' in markup


def test_normalized_number_preview_uses_the_compact_shared_font_size():
    assert module.PREVIEW_FONT_SIZE == 320


def test_sheet_renderer_can_use_the_existing_number_metadata_without_rebuilding_it():
    assert callable(module.render_sheets)


def test_placement_editor_maps_pointer_positions_from_rendered_preview_bounds():
    assert "getBoundingClientRect" in module.PLACEMENT_EDITOR


def test_svg_contours_are_exposed_as_individually_selectable_paths():
    assert module.svg_contours("M0 0L10 0ZM20 20L30 20Z") == [
        "M0 0L10 0Z",
        "M20 20L30 20Z",
    ]
    assert 'data-align-x' in module.PLACEMENT_EDITOR
    assert 'data-align-y' in module.PLACEMENT_EDITOR


def test_placement_editor_moves_every_digit_count_from_one_shared_centre():
    assert "previewsFor(markerId).forEach" in module.PLACEMENT_EDITOR
    assert "data-apply-all-digits" not in module.PLACEMENT_EDITOR


def test_marker_contact_sheet_fits_as_many_large_cards_as_the_width_allows():
    assert "grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));" in module.CARD_CSS
    assert ".row svg { width: 100%; max-width: 150px;" in module.CARD_CSS


def test_clicking_a_preview_only_selects_and_never_places_the_number():
    assert "select(svg, contourAt(svg, sourcePoint(svg, event)));" in module.PLACEMENT_EDITOR
    # the number moves through the centring actions alone
    assert "setCentre(svg, point, contourAt(svg, point));" not in module.PLACEMENT_EDITOR


def test_placements_save_themselves_and_come_back_on_reload():
    assert "localStorage.setItem(STORAGE_KEY" in module.PLACEMENT_EDITOR
    assert "localStorage.getItem(STORAGE_KEY" in module.PLACEMENT_EDITOR
    assert "restore();" in module.PLACEMENT_EDITOR


def test_the_build_applies_the_hand_placed_centres():
    source = (ROOT / "scripts" / "build_number_boxes.py").read_text()
    assert "number_placement.json" in source
    assert '"placement": "manual"' in source


def test_every_marker_carries_a_hand_placed_centre():
    import json

    placement = json.loads((ROOT / "scripts" / "number_placement.json").read_text())
    collection = json.loads((ROOT / "collection.json").read_text())

    for marker in collection["markers"]:
        placed = placement[marker["id"]]
        number = marker["number"]
        assert number["placement"] == "manual"
        assert (number["cx"], number["cy"]) == (placed["cx"], placed["cy"])


def test_a_marker_records_one_centre_and_one_box_not_a_set_per_digit_count():
    import json

    collection = json.loads((ROOT / "collection.json").read_text())

    for marker in collection["markers"]:
        number = marker["number"]
        # where the number goes, and the widest box the marker holds
        assert {"cx", "cy", "width", "height", "r"} <= number.keys()
        assert "digits" not in number
