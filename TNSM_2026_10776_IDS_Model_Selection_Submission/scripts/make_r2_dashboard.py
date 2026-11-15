"""Regenerate original-style R2 figures from the corrected frozen JSON.\nNo training, hardware access or new measurements.\n"""
import json
from io import BytesIO
from pathlib import Path
import numpy as np
import pymupdf

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

plt.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,          # TrueType, no Type 3 fonts
    "font.family": "DejaVu Sans", "font.size": 7,
    "axes.titlesize": 7.5, "axes.labelsize": 7, "xtick.labelsize": 6.5,
    "ytick.labelsize": 7, "legend.fontsize": 6.5, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 0,
})

DATA = json.loads((Path(__file__).parent / "r2_plot_data.json").read_text())
def avg(values):
    return sum(values)/len(values)
full_methods = DATA["methods"]
methods = ["Cascade" if m == "ConfidenceCascade_0p3_0p7" else m for m in full_methods]
rows = DATA["rows"]
extra = DATA["extra"]
occ = {name: {("Cascade" if full == "ConfidenceCascade_0p3_0p7" else
              "MedRF" if full in ("DeadlineGuard", "Static-MedRF") else "LightLR"): 5000}
       for name, full in zip(methods, full_methods)}
runtime_sw = [avg([extra[r["run_id"]]["runtime_switches"] for r in rows if r["method"] == m]) for m in full_methods]
states = [avg([extra[r["run_id"]]["unique_states"] for r in rows if r["method"] == m]) for m in full_methods]
misses = [sum(r["deadline_miss_windows"] for r in rows if r["method"] == m) for m in full_methods]
p95 = [avg([extra[r["run_id"]]["completion_p95"] for r in rows if r["method"] == m]) for m in full_methods]
f1 = [avg([r["f1"] for r in rows if r["method"] == m]) for m in full_methods]

C = {"LightLR": "#0072B2", "MedRF": "#E69F00", "TinyDT": "#D55E00", "Cascade": "#009E73"}
bar_c = "#52606D"
hl = "#B45309"

fig = plt.figure(figsize=(7.16, 2.25))
outer = fig.add_gridspec(1, 2, width_ratios=[3.55, 1.75], left=0.118, right=0.995,
                         bottom=0.185, top=0.80, wspace=0.17)
inner = outer[0].subgridspec(1, 4, width_ratios=[1.25, 0.72, 0.72, 0.86], wspace=0.2)
gs = [inner[0], inner[1], inner[2], inner[3], outer[1]]
y = list(range(len(methods)))[::-1]

def style(ax, sharey=True):
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_yticks(y)
    if sharey:
        ax.set_yticklabels([])
    ax.set_ylim(-0.6, len(methods) - 0.4)
    ax.grid(axis="x", color="#D9DEE3", lw=0.5)
    ax.set_axisbelow(True)

# (a) occupancy
ax = fig.add_subplot(gs[0]); style(ax, sharey=False)
ax.set_yticklabels(methods)
for yi, m in zip(y, methods):
    left = 0
    for k in ["LightLR", "MedRF", "TinyDT", "Cascade"]:
        v = occ[m].get(k, 0)
        if v:
            ax.barh(yi, v, left=left, color=C[k], height=0.62, lw=0)
            left += v
ax.set_xlim(0, 5000); ax.set_xticks([0, 2500, 5000]); ax.set_xticklabels(["0", "2.5k", "5k"])
ax.set_xlabel("Windows (of 5,000)")
ax.set_title("(a) Executed detector", loc="left")
handles = [Patch(color=C[k], label=l) for k, l in
           [("LightLR", "LightLR"), ("MedRF", "MedRF"), ("TinyDT", "TinyDT"),
            ("Cascade", "Cascade (LightLR + deferred MedRF)")]]
fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.112, 1.005), ncol=4,
           frameon=False, handlelength=1.0, columnspacing=1.1, handletextpad=0.4)

# (b) runtime switches
ax = fig.add_subplot(gs[1]); style(ax)
ax.barh(y, runtime_sw, color=bar_c, height=0.62)
for yi, v in zip(y, runtime_sw):
    ax.text(v + 0.12, yi, f"{v:.1f}", va="center", fontsize=6.5)
ax.set_xlim(0, 6.2); ax.set_xticks([0, 2, 4])
ax.set_xlabel("Switches / run")
ax.set_title("(b) Switching", loc="left")

# (c) unique states
ax = fig.add_subplot(gs[2]); style(ax)
ax.barh(y, states, color=bar_c, height=0.62)
for yi, v in zip(y, states):
    ax.text(v + 0.3, yi, f"{v:.1f}", va="center", fontsize=6.5)
ax.set_xlim(0, 21); ax.set_xticks([0, 10, 20])
ax.set_xlabel("States / run")
ax.set_title("(c) Support", loc="left")

# (d) deadline misses
ax = fig.add_subplot(gs[3]); style(ax)
ax.barh(y, misses, color=[hl if v else bar_c for v in misses], height=0.62)
for yi, v in zip(y, misses):
    ax.text(v + 12, yi, f"{v}", va="center", fontsize=6.5)
ax.set_xlim(0, 720); ax.set_xticks([0, 250, 500])
ax.set_xlabel("Missed windows")
ax.set_title("(d) Deadline misses", loc="left")

# (e) security-timeliness operating points
ax = fig.add_subplot(gs[4])
ax.spines[["top", "right"]].set_visible(False)
ax.grid(color="#D9DEE3", lw=0.5); ax.set_axisbelow(True)
ax.axvline(1.0, color=hl, lw=0.8, ls="--")
ax.text(0.985, 0.980, "1-s deadline", color=hl, ha="right", fontsize=6.3)

mk = {"Static-LightLR": ("o", C["LightLR"]), "Cascade": ("D", C["Cascade"]),
      "DeadlineGuard": ("s", "#1F2933"), "Tabular-Q": ("v", C["LightLR"]),
      "DQN": ("^", "#56B4E9"), "Static-MedRF": ("o", C["MedRF"])}
for m, xv, yv in zip(methods, p95, f1):
    s, c = mk[m]
    ax.scatter(xv, yv, marker=s, s=18, color=c, edgecolor="white", lw=0.4, zorder=3)
ax.annotate("Static-LightLR / Q / DQN", xy=(p95[0], f1[0]), xytext=(0.12, 0.979),
            fontsize=6.0, arrowprops=dict(arrowstyle="-", lw=0.5, color="#52606D"))
ax.annotate("Cascade / MedRF / DeadlineGuard", xy=(p95[1], f1[1]), xytext=(0.28, 0.986),
            fontsize=5.7, arrowprops=dict(arrowstyle="-", lw=0.5, color="#52606D"))
ax.set_xlim(0, 1.1); ax.set_ylim(0.972, 0.995)
ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
ax.set_xlabel("Completion p95 (s)"); ax.set_ylabel("F1", labelpad=1)
ax.tick_params(axis="y", length=2.5, labelsize=6.5)
ax.set_title("(e) Security vs. timeliness", loc="left")

fig.savefig("figures/r2_operational_dashboard.pdf")
print("wrote figures/r2_operational_dashboard.pdf")

# The three supplementary R2 views retain their original panel organization.
plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
                     "xtick.labelsize": 8, "ytick.labelsize": 8})
palette = ["#4C78A8", "#59A14F", "#B279A2", "#E15759", "#76B7B2", "#F28E2B"]
short = ["LightLR", "Cascade", "DeadlineGuard", "Tabular-Q", "DQN", "MedRF"]
fig2, axes = plt.subplots(1, 2, figsize=(7.05, 2.5), layout="constrained")
for i, (m, col) in enumerate(zip(full_methods, palette)):
    vals = [r["energy_joules"] for r in rows if r["method"] == m]
    axes[0].scatter(i + np.linspace(-.08, .08, len(vals)), vals, s=11, color=col, alpha=.65)
    axes[0].errorbar(i, np.mean(vals), yerr=2.2621571628540993*np.std(vals,ddof=1)/np.sqrt(10),
                     marker="D", color="black", capsize=3, markersize=3, linewidth=1)
axes[0].set_ylabel("500-s energy (J)")
right = axes[1].twinx()
axes[1].bar(np.arange(6)-.15, f1, .30, color="#4C78A8")
fpr = [100*avg([r["fpr"] for r in rows if r["method"] == m]) for m in full_methods]
right.bar(np.arange(6)+.15, fpr, .30, color="#E15759")
axes[1].set_ylim(0,1.02); right.set_ylim(0,2.0)
axes[1].set_ylabel("F1"); right.set_ylabel("FPR (%)")
axes[1].set_title("Security operating points")
for ax in axes:
    ax.set_xticks(range(6),short,rotation=35,ha="right")
    ax.spines[["top","right"]].set_visible(False); ax.grid(axis="y",alpha=.2);ax.set_axisbelow(True)
fig2.savefig("figures/r2_energy_security.pdf")

dqn = {r["block"]:r["energy_joules"] for r in rows if r["method"]=="DQN"}
lr = {r["block"]:r["energy_joules"] for r in rows if r["method"]=="Static-LightLR"}
diff = [dqn[b]-lr[b] for b in range(1,11)]
fig3, ax = plt.subplots(figsize=(5.2,2.9),layout="constrained")
ax.scatter(range(1,11),diff,s=24);ax.axhline(0,ls="--",lw=.8)
ax.axhline(np.mean(diff),ls=":",lw=.8,color="#52606D")
ax.set_xticks(range(1,11));ax.set_xlabel("Paired block");ax.set_ylabel("DQN - Static-LightLR energy (J)")
ax.set_title("R2 raw paired energy differences")
ax.text(.02,.96,"Mean +0.60 J; paired 95% CI [-4.12, 5.32] J",transform=ax.transAxes,va="top",fontsize=8)
fig3.savefig("figures/r2_dqn_block_energy_differences.pdf")

# Update only the R2 half: preserve the original R1 vector panel byte-for-byte as a clipped form.
fig4, ax = plt.subplots(figsize=(3.5,2.47),layout="constrained")
for i,(m,col) in enumerate(zip(full_methods,palette)):
    vals = [1000*r["idle_adjusted_mean_watts"] for r in rows if r["method"]==m]
    ax.scatter(i+np.linspace(-.08,.08,10),vals,s=10,color=col,alpha=.65)
    ax.errorbar(i,np.mean(vals),yerr=2.2621571628540993*np.std(vals,ddof=1)/np.sqrt(10),
                marker="D",color="black",capsize=2,markersize=3,lw=1)
ax.set_xticks(range(6),short,rotation=35,ha="right");ax.set_ylabel("Power above preceding idle (mW)")
ax.set_title("R2: variable load");ax.spines[["top","right"]].set_visible(False);ax.grid(axis="y",alpha=.2)
panel = BytesIO();fig4.savefig(panel, format="pdf")
# Unchanged original R1 vector half, retained locally for reproducible plotting.
leftdoc = pymupdf.open("figures/r1_idle_panel_source.pdf")
rightdoc = pymupdf.open(stream=panel.getvalue(), filetype="pdf");rect=leftdoc[0].rect
combined=pymupdf.open();page=combined.new_page(width=2*rect.width,height=rect.height)
half=rect.width
# Rasterize only the unchanged R1 source panel at 600 dpi to enforce its crop.
# A PDF CropBox alone allowed hidden historical R2 content to overlay the new panel.
left_image = leftdoc[0].get_pixmap(matrix=pymupdf.Matrix(600/72, 600/72), clip=leftdoc[0].rect, alpha=False)
page.insert_image(pymupdf.Rect(0,0,half,rect.height), pixmap=left_image)
page.show_pdf_page(pymupdf.Rect(half,0,2*half,rect.height),rightdoc,0)
combined.save("figures/revision_drift_adjusted_power.pdf")
