from __future__ import annotations

from pathlib import Path

from PIL import Image

from mare.highlight import render_object_region_highlight


def test_render_object_region_highlight_creates_overlay_image(tmp_path: Path) -> None:
    image_path = tmp_path / "page-1.png"
    Image.new("RGB", (400, 600), color="white").save(image_path)

    output = render_object_region_highlight(
        page_image_path=image_path,
        page_number=1,
        object_type="table",
        metadata={"region_hint": "top", "label": "Table 1"},
    )

    assert output
    assert Path(output).exists()
