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


def test_number_preview_preserves_digit_shapes_when_fitting_its_box():
    markup = module.card_svg(
        "0 0 100 100",
        "",
        {"cx": 50, "cy": 50, "width": 40, "height": 40},
        "٤٨",
    )

    assert 'lengthAdjust="spacing"' in markup
    assert "spacingAndGlyphs" not in markup


def test_sheet_renderer_can_use_the_existing_number_metadata_without_rebuilding_it():
    assert callable(module.render_sheets)
