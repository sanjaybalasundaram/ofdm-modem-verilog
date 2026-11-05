#!/usr/bin/env python3
"""Plot the project results from the simulation outputs.

  docs/ber_final.png        hardware BER vs Python float, Python fixed point and theory
  docs/constellation.png    received QPSK points from the hardware FFT (4 dB and 10 dB)
  docs/noise_histogram.png  hardware noise generator vs an ideal Gaussian
  docs/ber_summary.md       table + loss vs theory in dB
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.special import erfc, erfcinv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
SIM = os.path.join(ROOT, "sim")
CP_LOSS = 64 / 80

# Validated categorical colours (fixed order) + distinct markers so colour is never the only cue
C_FLOAT, C_FIXED, C_HW, C_THEORY = "#2a78d6", "#eb6834", "#1baf7a", "#3d3d3a"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#b5b4ad", "axes.labelcolor": "#3d3d3a",
                     "xtick.color": "#5f5e58", "ytick.color": "#5f5e58", "axes.spines.top": False,
                     "axes.spines.right": False, "grid.color": "#e4e3dd", "grid.linewidth": 0.6})


def theory(ebn0_db):
    return 0.5 * erfc(np.sqrt(10 ** (np.asarray(ebn0_db) / 10) * CP_LOSS))


def read_csv(path):
    return np.genfromtxt(path, delimiter=",", names=True)


def loss_db(ebn0, ber, target=1e-3):
    """Extra Eb/N0 (dB) needed vs ideal QPSK without CP, at the target BER."""
    ok = ber > 0
    if not np.any(ber[ok] <= target):
        return None
    needed = np.interp(np.log10(target), np.log10(ber[ok])[::-1], ebn0[ok][::-1])
    ideal = 10 * np.log10(erfcinv(2 * target) ** 2)
    return needed - ideal


def main():
    hw = read_csv(os.path.join(DOCS, "hw_ber.csv"))
    py = read_csv(os.path.join(DOCS, "python_ber.csv")) if os.path.exists(os.path.join(DOCS, "python_ber.csv")) else None
    e_fine = np.linspace(0, 10, 101)

    # ---- BER ----
    fig, ax = plt.subplots(figsize=(7.2, 5))
    ax.semilogy(e_fine, theory(e_fine), "-", color=C_THEORY, lw=2, label="Theory (QPSK, with CP loss)")
    if py is not None:
        ax.semilogy(py["ebn0_db"], py["ber_float"], "o", color=C_FLOAT, ms=8, mfc="none", mew=2, label="Python floating point")
        ax.semilogy(py["ebn0_db"], np.where(py["ber_fixed"] > 0, py["ber_fixed"], np.nan), "^", color=C_FIXED, ms=8,
                    mfc="none", mew=2, label="Python fixed point (Q1.15)")
    m = hw["bit_errors"] > 0
    ax.semilogy(hw["ebn0_db"][m], hw["ber"][m], "s-", color=C_HW, ms=8, lw=2, label="Verilog hardware (Icarus)")
    ax.grid(True, which="both")
    ax.set_xlabel("Eb/N0 (dB)")
    ax.set_ylabel("Bit error rate")
    ax.set_title("OFDM-QPSK, 64-point FFT, CP = 16", loc="left", fontsize=12)
    ax.set_ylim(1e-6, 0.5)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "ber_final.png"), dpi=150)
    plt.close(fig)

    # ---- Constellation ----
    cpath = os.path.join(SIM, "rx_constellation.csv")
    if os.path.exists(cpath):
        c = read_csv(cpath)
        pts = sorted(set(c["ebn0_db"]))
        fig, axes = plt.subplots(1, len(pts), figsize=(4.2 * len(pts), 4.2))
        for a, e in zip(np.atleast_1d(axes), pts):
            s = c[c["ebn0_db"] == e]
            a.scatter(s["re"], s["im"], s=9, color=C_FLOAT, alpha=0.6, linewidths=0)
            a.axhline(0, color="#b5b4ad", lw=0.8)
            a.axvline(0, color="#b5b4ad", lw=0.8)
            lim = 1.6 * np.max(np.abs(np.concatenate([s["re"], s["im"]])))
            a.set_xlim(-lim, lim)
            a.set_ylim(-lim, lim)
            a.set_aspect("equal")
            a.set_title(f"Received points, Eb/N0 = {e:g} dB", loc="left", fontsize=11)
            a.set_xlabel("I (LSB)")
            a.set_ylabel("Q (LSB)")
        fig.tight_layout()
        fig.savefig(os.path.join(DOCS, "constellation.png"), dpi=150)
        plt.close(fig)

    # ---- Noise histogram ----
    npath = os.path.join(SIM, "noise_samples.txt")
    if os.path.exists(npath):
        n = np.loadtxt(npath)
        fig, ax = plt.subplots(figsize=(7.2, 4))
        ax.hist(n, bins=60, density=True, color=C_FLOAT, alpha=0.85, rwidth=0.9, label="Hardware noise (awgn_gen)")
        x = np.linspace(n.min(), n.max(), 300)
        sd = n.std()
        ax.plot(x, np.exp(-x ** 2 / (2 * sd ** 2)) / (sd * np.sqrt(2 * np.pi)), color=C_FIXED, lw=2,
                label=f"Ideal Gaussian (std-dev {sd:.0f})")
        ax.set_xlabel("Noise value (LSB)")
        ax.set_ylabel("Probability density")
        ax.set_title("Hardware noise generator", loc="left", fontsize=12)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(DOCS, "noise_histogram.png"), dpi=150)
        plt.close(fig)

    # ---- Summary ----
    lines = ["# BER results", "",
             "| Eb/N0 (dB) | Theory | Python float | Python fixed | Hardware | HW errors / bits |",
             "|---|---|---|---|---|---|"]
    for k, e in enumerate(hw["ebn0_db"]):
        pf = f"{py['ber_float'][k]:.2e}" if py is not None else "-"
        px = f"{py['ber_fixed'][k]:.2e}" if py is not None else "-"
        lines.append(f"| {e:g} | {theory(e):.2e} | {pf} | {px} | {hw['ber'][k]:.2e} | "
                     f"{int(hw['bit_errors'][k])} / {int(hw['bits'][k])} |")
    l_hw = loss_db(hw["ebn0_db"], hw["ber"])
    cp_db = -10 * np.log10(CP_LOSS)
    if l_hw is not None:
        lines += ["", f"At BER = 1e-3 the hardware needs {l_hw:.2f} dB more Eb/N0 than ideal QPSK.",
                  f"- {cp_db:.2f} dB of this is expected: the cyclic prefix uses 16 of every 80 samples for no new data.",
                  f"- The remaining {l_hw - cp_db:+.2f} dB is implementation loss (fixed-point rounding in the FFTs,",
                  "  noise made from 4 uniform numbers instead of true Gaussian noise) plus statistical spread from",
                  "  the limited number of simulated bits. Close to 0 dB means the hardware performs like the ideal model."]
    else:
        lines += ["", "Not enough errors to measure the loss at BER = 1e-3."]
    open(os.path.join(DOCS, "ber_summary.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[lines.index("") + 1 + len(hw) + 1:]))
    print("Saved docs/ber_final.png, docs/constellation.png, docs/noise_histogram.png, docs/ber_summary.md")


if __name__ == "__main__":
    sys.exit(main())
