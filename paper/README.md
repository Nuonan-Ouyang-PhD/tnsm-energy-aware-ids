# Paper

**Model Selection for Energy-Aware Edge Intrusion Detection: A Controlled Measurement Study**

Nuonan Ouyang, Adrian Shatte, Zhigang Lu, Chao Chen, and Wei Xiang.

## Submission files

[Download the complete package](TNSM_Submission.zip)

The package contains `Manuscript.pdf`, `Supplementary_Material.pdf`, `Response_to_Reviewers.pdf`, `Cover_Letter.pdf`, and one `Source_Files/` directory. There are no nested ZIP files. The source directory includes the required tables, figures, bibliography, and IEEE LaTeX files.

## Build from repository data

On Ubuntu:

```bash
sudo apt-get install latexmk texlive-latex-base texlive-latex-recommended \
  texlive-latex-extra texlive-fonts-recommended texlive-science cm-super \
  poppler-utils python3-numpy python3-scipy python3-matplotlib
/usr/bin/python3 scripts/build_paper.py
```

Run the final command from the repository root. It generates tables from the recorded physical run metrics, reproduces all exported paired comparisons, builds the four PDFs, and creates `paper/TNSM_Submission.zip`. No policy training or hardware measurement is launched. Build logs are written outside the submission ZIP.

## Compile the supplied LaTeX only

After extracting the submission package, change to `Source_Files/` and run:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error Supplementary_Material.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error Response_to_Reviewers.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error Cover_Letter.tex
```

The same directory can be uploaded to Overleaf with `main.tex` selected as the main document. The supplementary material and correspondence can each be selected and compiled separately.

## Results

The main tables use the [paired physical experiment](../releases/supplemental-followup-20261113/). The supplement reports every method pair, all three block sets, and raw/idle-adjusted outcomes. Its separately identified fixed-rate software experiments use their own state and objective definitions and are not pooled with the main physical study.
