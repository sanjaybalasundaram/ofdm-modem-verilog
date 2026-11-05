#!/bin/sh
# Run every OFDM test, then build sim/output.html (results + BER graph + circuit + waveform) and open it.
#   ./run.sh         quick BER sweep (300 OFDM symbols per Eb/N0 point, ~1 min)
#   ./run.sh full    long BER sweep  (3000 symbols per point, ~10 min, smoother curve)
cd "$(dirname "$0")"
PY=python_model/.venv/bin/python
[ -x "$PY" ] || PY=python3
MAX_SYM=300
[ "$1" = "full" ] && MAX_SYM=3000
mkdir -p sim docs

# Only one run at a time: two runs write the same result files and mix them up
LOCK=sim/.run.lock
if ! mkdir "$LOCK" 2>/dev/null; then
    OTHER=$(cat "$LOCK/pid" 2>/dev/null)
    if [ -n "$OTHER" ] && kill -0 "$OTHER" 2>/dev/null; then
        echo "Another simulation run is still going (process $OTHER). Wait for it to finish, then run again."
        exit 1
    fi
    rm -rf "$LOCK" && mkdir "$LOCK" || exit 1     # left over from a run that was stopped
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT INT TERM

echo "== Python: test vectors + twiddle ROM"
$PY python_model/ofdm_fixed.py vectors || exit 1
$PY scripts/gen_twiddle.py || exit 1
[ -f docs/python_ber.csv ] || $PY python_model/ofdm_fixed.py > /dev/null

: > sim/sim_log.txt
for t in tb_qpsk_mapper tb_qpsk_demapper tb_fft64 tb_cp tb_awgn_gen tb_ofdm_top; do
    echo "== $t"
    iverilog -g2005 -Ptb_ofdm_top.MAX_SYM=$MAX_SYM -o sim/$t.vvp rtl/*.v tb/$t.v 2>/dev/null \
        || iverilog -g2005 -o sim/$t.vvp rtl/*.v tb/$t.v || exit 1
    vvp -n sim/$t.vvp | grep -v '^VCD info\|\$finish called' | tee -a sim/sim_log.txt
done

PASSES=$(grep -c '^PASS' sim/sim_log.txt)
FAILS=$(grep -c 'FAIL' sim/sim_log.txt)
if [ "$FAILS" -eq 0 ] && [ "$PASSES" -gt 0 ]; then
    printf '\nALL TESTS PASSED (%s checks)\n' "$PASSES" | tee -a sim/sim_log.txt
else
    printf '\n%s TEST(S) FAILED\n' "$FAILS" | tee -a sim/sim_log.txt
fi

echo "== Plots and output page"
$PY scripts/plot_ber.py > /dev/null
$PY tools/make_output.py && open sim/output.html
