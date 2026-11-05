`timescale 1ns/1ps
// Noise generator check: mean ~ 0 and std-dev ~ target. Also level 0 must pass the signal unchanged.
module tb_awgn_gen;
    localparam NS = 50000;
    localparam real SIGMA = 1000.0;
    reg        clk = 0, rst_n = 0, in_valid = 0;
    reg [15:0] level = 0;
    reg  signed [15:0] in_re = 0, in_im = 0;
    wire       out_valid;
    wire signed [15:0] out_re, out_im;
    real sum = 0, sumsq = 0, mean, sd;
    integer n = 0, pass_err = 0, k, f;
    reg measuring = 0;

    awgn_gen dut (.clk(clk), .rst_n(rst_n), .noise_level(level), .in_valid(in_valid),
                  .in_re(in_re), .in_im(in_im), .out_valid(out_valid), .out_re(out_re), .out_im(out_im));
    always #5 clk = ~clk;

    always @(posedge clk) if (out_valid) begin
        if (measuring) begin
            sum = sum + out_re + out_im;
            sumsq = sumsq + 1.0 * out_re * out_re + 1.0 * out_im * out_im;
            n = n + 2;
            if (n <= 20000) $fdisplay(f, "%0d\n%0d", out_re, out_im);
        end else if (out_re !== 16'sd1234 || out_im !== -16'sd4321) pass_err = pass_err + 1;
    end

    initial begin
        f = $fopen("sim/noise_samples.txt", "w");
        $dumpfile("sim/tb_awgn_gen.vcd");
        $dumpvars(0, tb_awgn_gen);
        $dumpoff;
        repeat (3) @(posedge clk);
        rst_n <= 1;
        // 1) level 0: pass-through
        in_re <= 1234; in_im <= -4321; in_valid <= 1;
        repeat (100) @(posedge clk);
        in_valid <= 0;
        repeat (2) @(posedge clk);
        // 2) noise only
        level <= $rtoi(SIGMA * 4096.0 / 2364.8 + 0.5);
        in_re <= 0; in_im <= 0;
        @(posedge clk);
        $dumpon;
        measuring <= 1; in_valid <= 1;
        repeat (NS / 2) @(posedge clk);
        in_valid <= 0;
        repeat (2) @(posedge clk);
        $fclose(f);
        mean = sum / n;
        sd = $sqrt(sumsq / n - mean * mean);
        if (pass_err == 0) $display("PASS  awgn_gen (off)  : noise level 0 passes the signal unchanged");
        else               $display("FAIL  awgn_gen (off)  : %0d samples changed", pass_err);
        if (mean < 20 && mean > -20 && sd > 0.97 * SIGMA && sd < 1.03 * SIGMA)
             $display("PASS  awgn_gen (noise): mean = %0.1f, std-dev = %0.1f (target %0.0f) over %0d samples", mean, sd, SIGMA, n);
        else $display("FAIL  awgn_gen (noise): mean = %0.1f, std-dev = %0.1f (target %0.0f)", mean, sd, SIGMA);
        $finish;
    end
endmodule
