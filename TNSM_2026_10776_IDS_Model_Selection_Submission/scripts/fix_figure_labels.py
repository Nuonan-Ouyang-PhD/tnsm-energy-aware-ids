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
        page.insert_text((x, rect.y1+shift), label, fontsize=size, fontname='helv')
    meta = doc.metadata
    meta['keywords'] = (meta.get('keywords', '') + '; R1 labels separated').strip('; ')
    doc.set_metadata(meta)
    save(doc, path)


def repair_threshold():
    path = Path('figures/r4_threshold_shift.pdf')
    doc = fitz.open(path)
    page = doc[0]
    lines = [line for block in page.get_text('dict')['blocks']
             for line in block.get('lines', [])]
    targets = [(i, ''.join(span['text'] for span in line['spans']), fitz.Rect(line['bbox']))
               for i, line in enumerate(lines)
               if 'validation-selected' in ''.join(span['text'] for span in line['spans'])]
    if not targets and 'Validation-selected' in page.get_text():
        doc.close()
        return
    if len(targets) != 1:
        raise RuntimeError('Expected one validation-selected panel title')
    target_index, label, rect = targets[0]
    print('R4 panel title:', repr(label), rect)
    # The old title crosses the neighbouring 1.0 tick. Preserve any collateral
    # text in full before removing the overlapping title, including tick glyphs.
    restore = []
    for i, line in enumerate(lines):
        if i == target_index:
            continue
        for span in line['spans']:
            box = fitz.Rect(span['bbox'])
            if box.intersects(rect):
                restore.append(span)
                page.add_redact_annot(box, fill=False)
    page.add_redact_annot(rect, fill=False)
    page.apply_redactions(images=0, graphics=0)
    for span in restore:
        col = span.get('color', 0)
        color = ((col >> 16 & 255)/255, (col >> 8 & 255)/255, (col & 255)/255)
        page.insert_text(span['origin'], span['text'], fontsize=span['size'],
                         fontname='helv', color=color)
        print('Preserved neighbouring label:', repr(span['text']))
    page.insert_text((rect.x0+12, rect.y0+3), 'Validation-selected', fontsize=8, fontname='hebo')
    page.insert_text((rect.x0+12, rect.y0+12), 'threshold = 0.6468', fontsize=8, fontname='helv')
    save(doc, path)


if __name__ == '__main__':
    repair_frontier()
    repair_threshold()
