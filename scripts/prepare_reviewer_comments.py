#!/usr/bin/env python3
"""Retain the supplied reviewer wording while leaving the new replies intact."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
original = ROOT / 'releases/submission/package/Source_Files/Response_to_Reviewers.tex'
target = ROOT / 'paper/Source_Files/Response_to_Reviewers.tex'
old = original.read_text(encoding='utf-8')
new = target.read_text(encoding='utf-8')
comments = re.findall(r'\\begin\{qbox\}(.*?)\\end\{qbox\}', old, re.S)
pattern = r'\\begin\{comment\}(.*?)\\end\{comment\}'
if len(comments) != 19 or len(re.findall(pattern, new, re.S)) != 19:
    raise ValueError('Expected the editor comment, reviewer overview, and 17 numbered comments')
iterator = iter(comments)
def retain_comment(match):
    text = next(iterator).strip()
    text = re.sub(r'^Comment\s+\d+:\s*', '', text)
    return '\\begin{comment}\n' + text + '\n\\end{comment}'
new = re.sub(pattern, retain_comment, new, flags=re.S)
target.write_text(new, encoding='utf-8')
