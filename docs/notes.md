# Viva notes

## Fixed point (Q1.15)
Hardware has no decimals, so every value is a 16-bit integer meaning value/32768.
QPSK points are ±23170 (= 0.7071), so each symbol has magnitude 1. The Python
fixed-point model does exactly the same integer maths as the Verilog, so the
testbenches can demand a perfect match (0 LSB error), not just "close".

## QPSK mapper / demapper
Two bits pick one of four points: first bit sets the sign of I, second the sign of Q
(Gray code: neighbouring points differ by one bit, so a small noise error costs only one bit).
The demapper just reads the sign bits back. Loopback with 2000 random pairs gives 0 errors.

## Butterfly and bit growth
An FFT is built from butterflies: x = a + b·w and y = a − b·w, where w is a twiddle
(a point on the unit circle, stored in a ROM). Adding two numbers can need one more bit,
so after 6 stages values could grow 64×. We divide by 2 in every butterfly, which keeps
everything in 16 bits with no overflow. Cost: the output is FFT/64 and a little rounding noise
(SQNR ≈ 54 dB, far below the channel noise).

## 64-point FFT / IFFT
One block does both. Samples are written at bit-reversed addresses, then 6 stages × 32
butterflies run one per clock (192 clocks), then results come out in natural order.
The IFFT is the same circuit with conjugated twiddles (sin sign flipped).

## Cyclic prefix
The last 16 samples are copied in front of each 64-sample symbol. A multipath channel smears
each symbol into the next; the prefix absorbs that smear, and because the prefix is a copy of the
end, the channel's linear convolution looks like circular convolution to the FFT — so every
subcarrier just gets multiplied by one complex number. Cost: 16/80 of the energy → 0.97 dB.

## AWGN generator
Adding several uniform random numbers gives a bell curve (central limit theorem). 4 uniform
numbers from xorshift generators per I and Q, scaled by a noise-level register chosen from Eb/N0.
Measured: mean ≈ 0, std-dev 999.5 for a target of 1000.

## Result
Hardware BER sits on the theory curve (QPSK with CP loss) from 0 to 10 dB, together with
the Python floating- and fixed-point models. So the fixed-point design loses essentially nothing.
