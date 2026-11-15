"""Repair only text labels in the retained R1 and threshold figures.
The plotted points, intervals, confusion counts and axes are unchanged.
Run from the manuscript directory after regenerating any original figure.
"""
from pathlib import Path
import pymupdf as fitz


def save(doc, path):
    target = path.with_name(path.stem + '.tmp.pdf')
    doc.save(target, garbage=4, deflate=True)
    doc.close()
    target.replace(path)


def repair_frontier():
    path = Path('figures/r1_energy_security_frontier.pdf')
    doc = fitz.open(path)
    page = doc[0]
    text = page.get_text()
    if 'R1 labels separated' in (doc.metadata.get('keywords') or ''):
        doc.close()
        return
    a = page.search_for('Static MedRF')
    b = page.search_for('Confidence Cascade')
    if len(a) != 1 or len(b) != 1:
        raise RuntimeError('Expected two unique R1 labels')
    print('R1 label boxes:', page.rect, a[0], b[0])
    for rect in (a[0], b[0]):
        page.add_redact_annot(rect, fill=False)
    page.apply_redactions(images=0, graphics=0)
    size = 8.0
    labels = [('Static MedRF', a[0], -5), ('Confidence Cascade', b[0], 20)]
    for label, rect, shift in labels:
        width = fitz.get_text_length(label, fontname='helv', fontsize=size)
        x = min(rect.x0, page.rect.width-width-8)
        y = rect.y1+shift
        page.insert_text((x, y), label, fontsize=size, fontname='helv')
    meta = doc.metadata
    meta['keywords'] = (meta.get('keywords', '') + '; R1 labels separated').strip('; ')
    doc.set_metadata(meta)
    save(doc, path)


def repair_threshold():
    path = Path('figures/r4_threshold_shift.pdf')
    doc = fitz.open(path)
    page = doc[0]
    matches = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            full = ''.join(span['text'] for span in line['spans'])
            if 'validation-selected' in full:
                matches.append((full, fitz.Rect(line['bbox'])))
    if not matches and 'Validation-selected' in page.get_text():
        doc.close()
        return
    if len(matches) != 1:
        raise RuntimeError('Expected one validation-selected panel title')
    label, rect = matches[0]
    print('R4 panel title:', repr(label), rect)
    page.add_redact_annot(rect, fill=False)
    page.apply_redactions(images=0, graphics=0)
    # A short two-line title keeps the threshold visible without entering the third panel.
    page.insert_text((rect.x0+12, rect.y0+3), 'Validation-selected', fontsize=8, fontname='hebo')
    page.insert_text((rect.x0+12, rect.y0+12), 'threshold = 0.6468', fontsize=8, fontname='helv')
    save(doc, path)


if __name__ == '__main__':
    repair_frontier()
    repair_threshold()
