`timescale 1ns/1ps
// Full modem: TX -> AWGN -> RX.
//  1) Noise-free: TX samples must match Python exactly and RX bits must equal TX bits.
//  2) BER sweep, Eb/N0 = 0..10 dB  ->  docs/hw_ber.csv
module tb_ofdm_top;
    parameter MAX_SYM = 1500;               // max OFDM symbols per Eb/N0 point
    parameter MIN_ERR = 300;                // stop a point early after this many bit errors
    localparam NS = 4;                      // symbols in the Python vector test
    localparam real P = 2.0 * 23170.0 * 23170.0 / 64.0;   // TX sample power (LSB^2)

    reg        clk = 0, rst_n = 0, in_valid = 0;
    reg [15:0] level = 0;
    reg  [1:0] in_bits = 0;
    wire       in_ready, out_valid, tx_valid;
    wire [1:0] out_bits;
    wire signed [15:0] tx_re, tx_im;

    reg  [3:0]  vbits [0:NS*64-1];
    reg  [31:0] vtx   [0:NS*80-1];
    reg  [1:0]  sent  [0:63];
    integer phase = 1, ntx = 0, tx_err = 0, nrx = 0, bit_err = 0, k, s, e, f, cf;
    integer errs, bits;
    real sigma, ebn0;
    reg log_const = 0;

    ofdm_top dut (.clk(clk), .rst_n(rst_n), .noise_level(level), .in_valid(in_valid), .in_bits(in_bits),
                  .in_ready(in_ready), .out_valid(out_valid), .out_bits(out_bits),
                  .tx_valid(tx_valid), .tx_re(tx_re), .tx_im(tx_im));
    always #5 clk = ~clk;    // 100 MHz

    // Check TX samples against Python (phase 1 only)
    always @(posedge clk) if (tx_valid && phase == 1) begin
        if ({tx_re, tx_im} !== vtx[ntx]) tx_err = tx_err + 1;
        ntx = ntx + 1;
    end
    // Count bit errors at the receiver output
    always @(posedge clk) if (out_valid) begin
        e = out_bits ^ sent[nrx % 64];
        bit_err = bit_err + e[1] + e[0];
        nrx = nrx + 1;
    end
    // Save received constellation points (FFT output inside the receiver)
    always @(posedge clk) if (log_const && dut.u_rx.fft_valid)
        $fdisplay(cf, "%0.0f,%0d,%0d", ebn0, dut.u_rx.fft_re, dut.u_rx.fft_im);

    // Send one OFDM symbol (64 bit pairs) and wait until the receiver has output it
    task send_symbol(input integer from_vectors, input integer sym);
        begin
            for (k = 0; k < 64; k = k + 1)
                sent[k] = from_vectors ? vbits[sym*64 + k][1:0] : $random;
            @(posedge clk);
            while (!in_ready) @(posedge clk);
            for (k = 0; k < 64; k = k + 1) begin
                in_valid <= 1; in_bits <= sent[k];
                @(posedge clk);
            end
            in_valid <= 0;
        end
    endtask

    initial begin
        $readmemh("tb/vectors/qpsk_in.hex", vbits);
        $readmemh("tb/vectors/cp_out.hex", vtx);
        $dumpfile("sim/tb_ofdm_top.vcd");
        $dumpvars(0, tb_ofdm_top);
        repeat (3) @(posedge clk);
        rst_n <= 1;

        // ---- 1) noise-free ----
        for (s = 0; s < NS; s = s + 1) begin
            send_symbol(1, s);
            while (nrx < (s + 1) * 64) @(posedge clk);
        end
        $dumpoff;
        if (ntx == NS*80 && tx_err == 0) $display("PASS  ofdm_tx         : %0d/%0d transmitted samples match Python exactly", ntx, NS*80);
        else                             $display("FAIL  ofdm_tx         : %0d mismatches, %0d/%0d samples", tx_err, ntx, NS*80);
        if (nrx == NS*64 && bit_err == 0) $display("PASS  ofdm_top        : noise-free loopback, %0d bits, 0 bit errors", nrx*2);
        else                              $display("FAIL  ofdm_top        : noise-free loopback, %0d bit errors in %0d bits", bit_err, nrx*2);
        phase = 2;

        // ---- 2) BER sweep ----
        f  = $fopen("docs/hw_ber.csv", "w");
        cf = $fopen("sim/rx_constellation.csv", "w");
        $fdisplay(f, "ebn0_db,bit_errors,bits,ber");
        $fdisplay(cf, "ebn0_db,re,im");
        $display("\nHardware BER sweep (up to %0d OFDM symbols per point):", MAX_SYM);
        for (ebn0 = 0; ebn0 <= 10.01; ebn0 = ebn0 + 1) begin
            // Same Eb/N0 definition as the Python model (CP energy counted)
            sigma = $sqrt(P * 80.0 / 128.0 / $pow(10.0, ebn0 / 10.0) / 2.0);
            level = $rtoi(sigma * 4096.0 / 2364.8 + 0.5);
            bit_err = 0; nrx = 0; errs = 0;
            for (s = 0; s < MAX_SYM && !(bit_err >= MIN_ERR && s >= 20); s = s + 1) begin
                log_const = (s < 8) && (ebn0 == 4.0 || ebn0 == 10.0);
                send_symbol(0, s);
                while (nrx < (s + 1) * 64) @(posedge clk);
            end
            log_const = 0;
            bits = nrx * 2;
            $display("  Eb/N0 = %4.1f dB   BER = %e   (%0d errors in %0d bits, noise level %0d)",
                     ebn0, 1.0 * bit_err / bits, bit_err, bits, level);
            $fdisplay(f, "%0.0f,%0d,%0d,%e", ebn0, bit_err, bits, 1.0 * bit_err / bits);
        end
        $fclose(f);
        $fclose(cf);
        $display("PASS  BER sweep       : results written to docs/hw_ber.csv");
        $finish;
    end
endmodule
