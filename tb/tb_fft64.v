`timescale 1ns/1ps
// Checks fft64 in FFT mode and in IFFT mode against the Python fixed-point model.
module tb_fft64;
    localparam NV = 256;                    // 4 OFDM symbols of 64 samples
    reg        clk = 0, rst_n = 0;
    reg        f_valid = 0, i_valid = 0;
    reg  signed [15:0] f_re = 0, f_im = 0, i_re = 0, i_im = 0;
    wire       f_ready, i_ready, f_ovalid, i_ovalid;
    wire signed [15:0] f_ore, f_oim, i_ore, i_oim;
    reg  [31:0] fin [0:NV-1], fout [0:NV-1], iin [0:NV-1], iout [0:NV-1];
    integer fn = 0, in_ = 0, ferr = 0, ierr = 0, fmax = 0, imax = 0, s, k, e;

    fft64 u_fft  (.clk(clk), .rst_n(rst_n), .inverse(1'b0), .in_valid(f_valid), .in_re(f_re), .in_im(f_im),
                  .in_ready(f_ready), .out_valid(f_ovalid), .out_re(f_ore), .out_im(f_oim));
    fft64 u_ifft (.clk(clk), .rst_n(rst_n), .inverse(1'b1), .in_valid(i_valid), .in_re(i_re), .in_im(i_im),
                  .in_ready(i_ready), .out_valid(i_ovalid), .out_re(i_ore), .out_im(i_oim));
    always #5 clk = ~clk;

    function integer absdiff(input signed [15:0] a, input signed [15:0] b);
        absdiff = (a > b) ? a - b : b - a;
    endfunction

    always @(posedge clk) begin
        if (f_ovalid) begin
            e = absdiff(f_ore, fout[fn][31:16]); if (absdiff(f_oim, fout[fn][15:0]) > e) e = absdiff(f_oim, fout[fn][15:0]);
            if (e > fmax) fmax = e;
            if (e != 0) ferr = ferr + 1;
            fn = fn + 1;
        end
        if (i_ovalid) begin
            e = absdiff(i_ore, iout[in_][31:16]); if (absdiff(i_oim, iout[in_][15:0]) > e) e = absdiff(i_oim, iout[in_][15:0]);
            if (e > imax) imax = e;
            if (e != 0) ierr = ierr + 1;
            in_ = in_ + 1;
        end
    end

    initial begin
        $readmemh("tb/vectors/fft64_in.hex", fin);
        $readmemh("tb/vectors/fft64_out.hex", fout);
        $readmemh("tb/vectors/ifft64_in.hex", iin);
        $readmemh("tb/vectors/ifft64_out.hex", iout);
        $dumpfile("sim/tb_fft64.vcd");
        $dumpvars(0, tb_fft64);
        repeat (3) @(posedge clk);
        rst_n <= 1;
        for (s = 0; s < NV / 64; s = s + 1) begin
            @(posedge clk);
            while (!(f_ready && i_ready)) @(posedge clk);
            for (k = 0; k < 64; k = k + 1) begin
                f_valid <= 1; {f_re, f_im} <= fin[s*64 + k];
                i_valid <= 1; {i_re, i_im} <= iin[s*64 + k];
                @(posedge clk);
            end
            f_valid <= 0; i_valid <= 0;
        end
        while (fn < NV || in_ < NV) @(posedge clk);
        repeat (3) @(posedge clk);
        if (ferr == 0) $display("PASS  fft64 (FFT)     : %0d/%0d outputs match Python exactly (max error %0d LSB)", fn, NV, fmax);
        else           $display("FAIL  fft64 (FFT)     : %0d mismatches (max error %0d LSB)", ferr, fmax);
        if (ierr == 0) $display("PASS  fft64 (IFFT)    : %0d/%0d outputs match Python exactly (max error %0d LSB)", in_, NV, imax);
        else           $display("FAIL  fft64 (IFFT)    : %0d mismatches (max error %0d LSB)", ierr, imax);
        $finish;
    end
    initial begin #2000000 $display("FAIL  fft64: timeout"); $finish; end
endmodule
