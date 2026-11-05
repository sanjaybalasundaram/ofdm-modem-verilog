"""
OFDM modem - fixed-point model (bit-exact with the Verilog in rtl/)

Every function here does exactly the same integer arithmetic as the matching
Verilog block, so the hex test vectors it writes to tb/vectors/ must match the
hardware output with ZERO mismatches.

Number format: Q1.15 (16-bit signed, value = integer / 32768).
  QPSK symbol   : +-23170 on I and Q  (= 0.7071, so |symbol| = 1.0)
  Twiddles      : round(cos/sin * 32767)
  FFT / IFFT    : radix-2 DIT, 6 stages, each butterfly divides by 2
                  (so the total scale is 1/64 and nothing can overflow)

Usage:
  python ofdm_fixed.py           export vectors + fixed vs float BER plot
  python ofdm_fixed.py vectors   export vectors only (fast, used by run.sh)
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VEC_DIR = os.path.join(ROOT, "tb", "vectors")
DOCS = os.path.join(ROOT, "docs")

N_FFT = 64
LOG2N = 6
N_CP = 16
ONE = 32767                 # largest Q1.15 value (~1.0)
QPSK_A = 23170              # round(32767 / sqrt(2))
EBN0_DB = np.arange(0, 11)  # BER sweep points


# ---------------- Helpers ----------------
def sat16(v):
    """Saturate to the 16-bit signed range, like the hardware."""
    return np.clip(v, -32768, 32767)


def twiddles():
    """W_64^k = cos(2*pi*k/64) - j*sin(2*pi*k/64) in Q1.15, k = 0..31."""
    k = np.arange(N_FFT // 2)
    wr = np.round(np.cos(2 * np.pi * k / N_FFT) * ONE).astype(np.int64)
    wi = np.round(-np.sin(2 * np.pi * k / N_FFT) * ONE).astype(np.int64)
    return wr, wi


BITREV = np.array([int(f"{n:06b}"[::-1], 2) for n in range(N_FFT)])


# ---------------- Blocks (one function per Verilog module) ----------------
def qpsk_map_fx(bits):
    """bits shape (..., 2*n) -> I, Q shape (..., n). Bit 0 -> +A, bit 1 -> -A (Gray)."""
    b0, b1 = bits[..., 0::2], bits[..., 1::2]
    return np.where(b0 == 0, QPSK_A, -QPSK_A), np.where(b1 == 0, QPSK_A, -QPSK_A)


def qpsk_demap_fx(re, im):
    """Hard decision: negative -> bit 1."""
    bits = np.empty(re.shape[:-1] + (re.shape[-1] * 2,), dtype=np.int64)
    bits[..., 0::2] = (re < 0)
    bits[..., 1::2] = (im < 0)
    return bits


def butterfly_fx(ar, ai, br, bi, wr, wi):
    """Same as rtl/butterfly_r2.v: t = b*w (rounded), x = (a+t)/2, y = (a-t)/2 (rounded, saturated)."""
    tr = (br * wr - bi * wi + 16384) >> 15
    ti = (br * wi + bi * wr + 16384) >> 15
    return (sat16((ar + tr + 1) >> 1), sat16((ai + ti + 1) >> 1),
            sat16((ar - tr + 1) >> 1), sat16((ai - ti + 1) >> 1))


def fft_fx(re, im, inverse=False):
    """Same as rtl/fft64.v. Works on the last axis (64 samples). Output = FFT/64 (or IFFT)."""
    wr, wi = twiddles()
    if inverse:
        wi = -wi                                    # conjugate twiddles -> inverse transform
    xr = np.empty_like(re)
    xi = np.empty_like(im)
    xr[..., BITREV] = re                            # samples are written in bit-reversed order
    xi[..., BITREV] = im
    for s in range(LOG2N):
        half = 1 << s
        for bf in range(N_FFT // 2):
            j = bf & (half - 1)
            ia = ((bf >> s) << (s + 1)) | j
            ib = ia | half
            k = j << (LOG2N - 1 - s)
            out = butterfly_fx(xr[..., ia].copy(), xi[..., ia].copy(),
                               xr[..., ib].copy(), xi[..., ib].copy(), wr[k], wi[k])
            xr[..., ia], xi[..., ia], xr[..., ib], xi[..., ib] = out
    return xr, xi


def cp_insert_fx(x):
    return np.concatenate([x[..., -N_CP:], x], axis=-1)


def cp_remove_fx(x):
    return x[..., N_CP:]


def tx_sample_power():
    """Mean |x|^2 of one time-domain sample after the IFFT (2*A^2 / 64)."""
    return 2 * QPSK_A ** 2 / N_FFT


def noise_sigma(ebn0_db):
    """Noise std-dev per I/Q component in LSBs, same Eb/N0 definition as ofdm_model.py (CP counted)."""
    eb = tx_sample_power() * (N_FFT + N_CP) / (N_FFT * 2)
    return np.sqrt(eb / 10 ** (ebn0_db / 10) / 2)


# ---------------- Whole chain ----------------
def run_chain(bits, sigma=0.0, rng=None):
    """bits (nsym, 128) -> (tx samples re/im, rx FFT output re/im, rx bits)."""
    i, q = qpsk_map_fx(bits)
    tr, ti = fft_fx(i, q, inverse=True)
    txr, txi = cp_insert_fx(tr), cp_insert_fx(ti)
    rxr, rxi = txr, txi
    if sigma > 0:
        rxr = sat16(txr + np.round(rng.standard_normal(txr.shape) * sigma).astype(np.int64))
        rxi = sat16(txi + np.round(rng.standard_normal(txi.shape) * sigma).astype(np.int64))
    fr, fi = fft_fx(cp_remove_fx(rxr), cp_remove_fx(rxi))
    return (txr, txi), (fr, fi), qpsk_demap_fx(fr, fi)


def ber_fixed(ebn0_list, nsym=4000, seed=7):
    rng = np.random.default_rng(seed)
    out = []
    for e in ebn0_list:
        bits = rng.integers(0, 2, (nsym, 2 * N_FFT))
        *_, rx = run_chain(bits, noise_sigma(e), rng)
        err = int(np.count_nonzero(rx != bits))
        out.append(err / bits.size)
        print(f"  fixed  Eb/N0 = {e:4.1f} dB   BER = {err / bits.size:.2e}   ({err} errors)")
    return np.array(out)


# ---------------- Test vectors ----------------
def hex_iq(re, im):
    return [f"{int(r) & 0xFFFF:04x}{int(i) & 0xFFFF:04x}" for r, i in zip(re.ravel(), im.ravel())]


def write(name, lines):
    with open(os.path.join(VEC_DIR, name), "w") as f:
        f.write("\n".join(lines) + "\n")


def export_vectors(nsym=4, seed=1):
    """Write hex vectors for every block to tb/vectors/ (one value per line)."""
    os.makedirs(VEC_DIR, exist_ok=True)
    rng = np.random.default_rng(seed)
    bits = rng.integers(0, 2, (nsym, 2 * N_FFT))
    i, q = qpsk_map_fx(bits)
    tr, ti = fft_fx(i, q, inverse=True)
    # FFT test input: transmitted samples plus some noise, so all bits get exercised
    nr = sat16(tr + np.round(rng.standard_normal(tr.shape) * 600).astype(np.int64))
    ni = sat16(ti + np.round(rng.standard_normal(ti.shape) * 600).astype(np.int64))
    fr, fi = fft_fx(nr, ni)

    pairs = [f"{b0 * 2 + b1:x}" for b0, b1 in zip(bits.ravel()[0::2], bits.ravel()[1::2])]
    write("qpsk_in.hex", pairs)                             # {b0,b1}
    write("qpsk_out.hex", hex_iq(i, q))                     # {I,Q}
    write("ifft64_in.hex", hex_iq(i, q))
    write("ifft64_out.hex", hex_iq(tr, ti))
    write("fft64_in.hex", hex_iq(nr, ni))
    write("fft64_out.hex", hex_iq(fr, fi))
    write("cp_in.hex", hex_iq(tr, ti))
    write("cp_out.hex", hex_iq(cp_insert_fx(tr), cp_insert_fx(ti)))
    write("demap_in.hex", hex_iq(fr, fi))
    db = qpsk_demap_fx(fr, fi).ravel()
    write("demap_out.hex", [f"{a * 2 + b:x}" for a, b in zip(db[0::2], db[1::2])])

    # How close is the fixed-point FFT to an ideal floating-point FFT?
    ideal = np.fft.fft((nr + 1j * ni) / 32768, axis=-1) / N_FFT
    got = (fr + 1j * fi) / 32768
    sqnr = 10 * np.log10(np.sum(np.abs(ideal) ** 2) / np.sum(np.abs(got - ideal) ** 2))
    print(f"Wrote test vectors for {nsym} OFDM symbols to tb/vectors/  (fixed-point FFT SQNR = {sqnr:.1f} dB)")
    return sqnr


# ---------------- Main ----------------
if __name__ == "__main__":
    export_vectors()
    if len(sys.argv) > 1 and sys.argv[1] == "vectors":
        sys.exit(0)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sys.path.insert(0, HERE)
    import ofdm_model as fl

    print("\nFloating-point model:")
    ber_float = fl.run_ber(EBN0_DB, frames=20)
    print("\nFixed-point model:")
    ber_fx = ber_fixed(EBN0_DB)
    theory = fl.theory_qpsk_ber(EBN0_DB)

    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(DOCS, "python_ber.csv"), "w") as f:
        f.write("ebn0_db,ber_float,ber_fixed,ber_theory\n")
        for row in zip(EBN0_DB, ber_float, ber_fx, theory):
            f.write(",".join(f"{v:.6g}" for v in row) + "\n")

    plt.figure(figsize=(7, 5))
    plt.semilogy(EBN0_DB, theory, "k-", label="Theory (QPSK, CP loss)")
    plt.semilogy(EBN0_DB, ber_float, "bo", label="Python floating point")
    plt.semilogy(EBN0_DB, np.maximum(ber_fx, 1e-7), "r^", mfc="none", label="Python fixed point (Q1.15)")
    plt.grid(True, which="both", alpha=0.4)
    plt.xlabel("Eb/N0 (dB)")
    plt.ylabel("Bit Error Rate")
    plt.title("Fixed point vs floating point")
    plt.legend()
    plt.ylim(1e-6, 1)
    plt.tight_layout()
    plt.savefig(os.path.join(DOCS, "ber_fixed_vs_float.png"), dpi=150)
    print("\nSaved docs/ber_fixed_vs_float.png and docs/python_ber.csv")
