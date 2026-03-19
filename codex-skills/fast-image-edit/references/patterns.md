# Fast Image Challenge Patterns

## Recognize
- Objective asks to edit a provided image.
- Instructions include region-targeted edits (faces, objects, text regions).
- Evaluation focuses on edited output quality and required report fields.

## Execute
- Run `image_edit` first with a concise explicit instruction.
- Skip extra tool hops unless needed for required reporting.
- Keep one-pass output quality high to minimize latency.

## Face Privacy Example
- Blur all visible faces strongly.
- Preserve background and non-face body regions.
- If report required: include count and rough bounding boxes in short form.
