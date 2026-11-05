`timescale 1ns/1ps
// cp_insert vs Python vectors, then cp_remove must give back the original samples.
module tb_cp;
    localparam NS = 4, NV = NS * 64, NO = NS * 80;
    reg        clk = 0, rst_n = 0, in_valid = 0;
    reg  signed [15:0] in_re = 0, in_im = 0;
    wire       in_ready, ins_valid, rem_valid;
    wire signed [15:0] ins_re, ins_im, rem_re, rem_im;
    reg  [31:0] vin [0:NV-1], vout [0:NO-1];
    integer a = 0, b = 0, aerr = 0, berr = 0, s, k;

    cp_insert u_ins (.clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_re(in_re), .in_im(in_im),
                     .in_ready(in_ready), .out_valid(ins_valid), .out_re(ins_re), .out_im(ins_im));
    cp_remove u_rem (.clk(clk), .rst_n(rst_n), .in_valid(ins_valid), .in_re(ins_re), .in_im(ins_im),
                     .out_valid(rem_valid), .out_re(rem_re), .out_im(rem_im));
    always #5 clk = ~clk;

    always @(posedge clk) begin
        if (ins_valid) begin
            if ({ins_re, ins_im} !== vout[a]) aerr = aerr + 1;
            a = a + 1;
        end
        if (rem_valid) begin
            if ({rem_re, rem_im} !== vin[b]) berr = berr + 1;
            b = b + 1;
        end
    end

    initial begin
        $readmemh("tb/vectors/cp_in.hex", vin);
        $readmemh("tb/vectors/cp_out.hex", vout);
        $dumpfile("sim/tb_cp.vcd");
        $dumpvars(0, tb_cp);
        repeat (3) @(posedge clk);
        rst_n <= 1;
        for (s = 0; s < NS; s = s + 1) begin
            @(posedge clk);
            while (!in_ready) @(posedge clk);
            for (k = 0; k < 64; k = k + 1) begin
                in_valid <= 1; {in_re, in_im} <= vin[s*64 + k];
                @(posedge clk);
            end
            in_valid <= 0;
        end
        while (b < NV) @(posedge clk);
        repeat (3) @(posedge clk);
        if (a == NO && aerr == 0) $display("PASS  cp_insert       : %0d/%0d samples match Python (16 + 64 per symbol)", a, NO);
        else                      $display("FAIL  cp_insert       : %0d mismatches, %0d/%0d samples", aerr, a, NO);
        if (b == NV && berr == 0) $display("PASS  cp_remove       : %0d/%0d samples equal the original symbols", b, NV);
        else                      $display("FAIL  cp_remove       : %0d mismatches, %0d/%0d samples", berr, b, NV);
        $finish;
    end
    initial begin #200000 $display("FAIL  cp: timeout"); $finish; end
endmodule
