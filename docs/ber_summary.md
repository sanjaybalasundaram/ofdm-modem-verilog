# BER results

| Eb/N0 (dB) | Theory | Python float | Python fixed | Hardware | HW errors / bits |
|---|---|---|---|---|---|
| 0 | 1.03e-01 | 1.03e-01 | 1.03e-01 | 1.02e-01 | 313 / 3072 |
| 1 | 7.79e-02 | 7.81e-02 | 7.78e-02 | 7.47e-02 | 306 / 4096 |
| 2 | 5.56e-02 | 5.63e-02 | 5.57e-02 | 5.51e-02 | 303 / 5504 |
| 3 | 3.70e-02 | 3.69e-02 | 3.70e-02 | 3.28e-02 | 302 / 9216 |
| 4 | 2.25e-02 | 2.23e-02 | 2.22e-02 | 2.04e-02 | 301 / 14720 |
| 5 | 1.22e-02 | 1.21e-02 | 1.24e-02 | 1.26e-02 | 301 / 23808 |
| 6 | 5.80e-03 | 5.81e-03 | 5.91e-03 | 5.29e-03 | 203 / 38400 |
| 7 | 2.31e-03 | 2.27e-03 | 2.37e-03 | 2.27e-03 | 87 / 38400 |
| 8 | 7.43e-04 | 7.56e-04 | 7.30e-04 | 6.77e-04 | 26 / 38400 |
| 9 | 1.82e-04 | 1.56e-04 | 1.62e-04 | 3.13e-04 | 12 / 38400 |
| 10 | 3.17e-05 | 4.30e-05 | 3.13e-05 | 0.00e+00 | 0 / 38400 |

At BER = 1e-3 the hardware needs 0.89 dB more Eb/N0 than ideal QPSK.
- 0.97 dB of this is expected: the cyclic prefix uses 16 of every 80 samples for no new data.
- The remaining -0.08 dB is implementation loss (fixed-point rounding in the FFTs,
  noise made from 4 uniform numbers instead of true Gaussian noise) plus statistical spread from
  the limited number of simulated bits. Close to 0 dB means the hardware performs like the ideal model.
