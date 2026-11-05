"""
OFDM Baseband Modem - Python Golden Reference Model
Project : OFDM Baseband Modem on FPGA, RTL-to-GDSII
Week 1  : Floating-point model + BER vs Eb/N0 verification

Chain:
  bits -> QPSK mapper -> IFFT (64) -> add cyclic prefix -> add preamble
       -> AWGN channel
       -> frame sync (preamble correlation) -> remove CP -> FFT -> QPSK demapper -> bits

This model is the "golden reference": later every Verilog block is checked
against the outputs of the matching function in this file.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.special import erfc

# ---------------- System parameters ----------------
N_FFT = 64          # number of subcarriers (FFT size)
N_CP = 16           # cyclic prefix length (1/4 of symbol)
BITS_PER_SYM = 2    # QPSK -> 2 bits per subcarrier
N_SYMBOLS = 200     # OFDM symbols per frame
RNG = np.random.default_rng(42)


# ---------------- Transmitter blocks ----------------
def qpsk_map(bits):
    """Gray-coded QPSK: bit pair (b0,b1) -> ((1-2*b0) + j(1-2*b1)) / sqrt(2)."""
    b = bits.reshape(-1, 2)
    return ((1 - 2 * b[:, 0]) + 1j * (1 - 2 * b[:, 1])) / np.sqrt(2)


def ofdm_modulate(symbols):
    """Map QPSK symbols onto subcarriers and apply IFFT (one row = one OFDM symbol)."""
    grid = symbols.reshape(-1, N_FFT)
    return np.fft.ifft(grid, axis=1) * np.sqrt(N_FFT)   # unitary scaling keeps power = 1


def add_cyclic_prefix(time_syms):
    """Copy the last N_CP samples of each symbol to its front (protects against multipath / ISI)."""
    return np.hstack([time_syms[:, -N_CP:], time_syms])


def make_preamble():
    """Known preamble: two identical halves of a QPSK sequence, used for frame sync."""
    half = qpsk_map(RNG.integers(0, 2, N_FFT))           # 32 QPSK symbols
    return np.tile(np.fft.ifft(half) * np.sqrt(N_FFT // 2), 2)


PREAMBLE = make_preamble()


def transmitter(bits):
    syms = qpsk_map(bits)
    tx = add_cyclic_prefix(ofdm_modulate(syms)).ravel()
    return np.concatenate([PREAMBLE, tx])


# ---------------- Channel ----------------
def awgn(signal, ebn0_db, delay=0):
    """Add white Gaussian noise for a given Eb/N0, plus an unknown start delay."""
    ebn0 = 10 ** (ebn0_db / 10)
    # energy per bit after CP overhead: each data sample carries power 1
    eb = (N_FFT + N_CP) / (N_FFT * BITS_PER_SYM)
    n0 = eb / ebn0
    sig = np.concatenate([np.zeros(delay, complex), signal, np.zeros(10, complex)])
    noise = np.sqrt(n0 / 2) * (RNG.standard_normal(sig.size) + 1j * RNG.standard_normal(sig.size))
    return sig + noise


# ---------------- Receiver blocks ----------------
def frame_sync(rx, search=200):
    """Find frame start by cross-correlating with the known preamble."""
    corr = np.abs(np.correlate(rx[: search + PREAMBLE.size], PREAMBLE, mode="valid"))
    return int(np.argmax(corr))


def remove_cyclic_prefix(rx_data):
    blocks = rx_data[: N_SYMBOLS * (N_FFT + N_CP)].reshape(-1, N_FFT + N_CP)
    return blocks[:, N_CP:]


def ofdm_demodulate(time_syms):
    return (np.fft.fft(time_syms, axis=1) / np.sqrt(N_FFT)).ravel()


def qpsk_demap(symbols):
    """Hard decision: sign of real part -> b0, sign of imaginary part -> b1."""
    bits = np.empty(symbols.size * 2, dtype=int)
    bits[0::2] = (symbols.real < 0).astype(int)
    bits[1::2] = (symbols.imag < 0).astype(int)
    return bits


def receiver(rx):
    start = frame_sync(rx) + PREAMBLE.size
    data = remove_cyclic_prefix(rx[start:])
    return qpsk_demap(ofdm_demodulate(data)), start


# ---------------- Simulation ----------------
def run_ber(ebn0_list, frames=20):
    ber = []
    for ebn0 in ebn0_list:
        errors = total = 0
        for _ in range(frames):
            bits = RNG.integers(0, 2, N_SYMBOLS * N_FFT * BITS_PER_SYM)
            delay = int(RNG.integers(0, 100))            # receiver does not know this
            rx_bits, _ = receiver(awgn(transmitter(bits), ebn0, delay))
            errors += np.count_nonzero(rx_bits != bits)
            total += bits.size
        ber.append(max(errors / total, 1e-7))
        print(f"Eb/N0 = {ebn0:4.1f} dB   BER = {errors / total:.2e}   ({errors} errors)")
    return np.array(ber)


def theory_qpsk_ber(ebn0_db):
    """Theoretical QPSK BER in AWGN, with CP energy loss included."""
    loss = N_FFT / (N_FFT + N_CP)
    return 0.5 * erfc(np.sqrt(10 ** (np.asarray(ebn0_db) / 10) * loss))


if __name__ == "__main__":
    # 1. Noise-free sanity check: output must equal input exactly
    bits = RNG.integers(0, 2, N_SYMBOLS * N_FFT * BITS_PER_SYM)
    rx_bits, start = receiver(awgn(transmitter(bits), 100, delay=37))
    print(f"Sanity check: sync found frame at sample {start - PREAMBLE.size} (true 37), "
          f"bit errors = {np.count_nonzero(rx_bits != bits)}\n")

    # 2. BER vs Eb/N0
    ebn0_db = np.arange(0, 11, 1)
    sim = run_ber(ebn0_db)
    theory = theory_qpsk_ber(ebn0_db)

    plt.figure(figsize=(7, 5))
    plt.semilogy(ebn0_db, theory, "k-", label="Theory (QPSK, with CP loss)")
    plt.semilogy(ebn0_db, sim, "ro", label="Simulated OFDM model")
    plt.grid(True, which="both", alpha=0.4)
    plt.xlabel("Eb/N0 (dB)")
    plt.ylabel("Bit Error Rate")
    plt.title(f"OFDM-QPSK, {N_FFT}-point FFT, CP = {N_CP}")
    plt.legend()
    plt.ylim(1e-6, 1)
    plt.tight_layout()
    plt.savefig("ber_curve.png", dpi=150)
    print("\nSaved BER plot to ber_curve.png")
