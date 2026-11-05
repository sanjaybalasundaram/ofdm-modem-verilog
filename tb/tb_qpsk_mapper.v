`timescale 1ns/1ps
// Checks qpsk_mapper against the Python vectors (tb/vectors/qpsk_*.hex)
module tb_qpsk_mapper;
    localparam NV = 256;
    reg        clk = 0, rst_n = 0, in_valid = 0;
    reg  [1:0] in_bits = 0;
    wire       out_valid;
    wire signed [15:0] out_i, out_q;
    reg  [3:0]  vin  [0:NV-1];
    reg  [31:0] vout [0:NV-1];
    integer n = 0, errors = 0, k;

    qpsk_mapper dut (.clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_bits(in_bits),
                     .out_valid(out_valid), .out_i(out_i), .out_q(out_q));
    always #5 clk = ~clk;

    always @(posedge clk) if (out_valid) begin
        if ({out_i, out_q} !== vout[n]) begin
            errors = errors + 1;
            if (errors <= 5) $display("  mismatch at %0d: got %h expected %h", n, {out_i, out_q}, vout[n]);
        end
        n = n + 1;
    end

    initial begin
        $readmemh("tb/vectors/qpsk_in.hex", vin);
        $readmemh("tb/vectors/qpsk_out.hex", vout);
        $dumpfile("sim/tb_qpsk_mapper.vcd");
        $dumpvars(0, tb_qpsk_mapper);
        repeat (3) @(posedge clk);
        rst_n <= 1;
        for (k = 0; k < NV; k = k + 1) begin
            @(posedge clk);
            in_valid <= 1; in_bits <= vin[k][1:0];
        end
        @(posedge clk) in_valid <= 0;
        repeat (4) @(posedge clk);
        if (n == NV && errors == 0) $display("PASS  qpsk_mapper     : %0d/%0d outputs match Python", n, NV);
        else                        $display("FAIL  qpsk_mapper     : %0d mismatches, %0d/%0d outputs", errors, n, NV);
        $finish;
    end
endmodule
