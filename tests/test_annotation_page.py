from pathlib import Path


def test_annotation_page_has_component_assignment_controls():
    page = Path("annotate/index.html").read_text(encoding="utf-8")
    assert 'id="part-list"' in page
    assert 'id="assign"' in page
    assert 'id="inside-fill"' in page
    assert 'id="marker-json"' in page
    assert 'syncFamilyAnnotations' in Path("annotate/app.js").read_text(encoding="utf-8")
    assert 'marker-fill-preview' in Path("annotate/preview.css").read_text(encoding="utf-8")
    assert 'id="download"' in page
