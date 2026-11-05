`timescale 1ns/1ps
// 1) qpsk_demapper vs Python vectors   2) mapper -> demapper loopback with random bits
module tb_qpsk_demapper;
    localparam NV = 256, NL = 2000;
    reg        clk = 0, rst_n = 0, in_valid = 0, lb_valid = 0;
    reg  signed [15:0] in_i = 0, in_q = 0;
    reg  [1:0] lb_bits = 0;
    wire       out_valid, m_valid, lb_out_valid;
    wire [1:0] out_bits, lb_out_bits;
    wire signed [15:0] m_i, m_q;
    reg  [31:0] vin  [0:NV-1];
    reg  [3:0]  vout [0:NV-1];
    reg  [1:0]  sent [0:NL-1];
    integer n = 0, errors = 0, m = 0, lb_errors = 0, k;

    qpsk_demapper dut (.clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_i(in_i), .in_q(in_q),
                       .out_valid(out_valid), .out_bits(out_bits));
    // loopback
    qpsk_mapper   u_map (.clk(clk), .rst_n(rst_n), .in_valid(lb_valid), .in_bits(lb_bits),
                         .out_valid(m_valid), .out_i(m_i), .out_q(m_q));
    qpsk_demapper u_dem (.clk(clk), .rst_n(rst_n), .in_valid(m_valid), .in_i(m_i), .in_q(m_q),
                         .out_valid(lb_out_valid), .out_bits(lb_out_bits));
    always #5 clk = ~clk;

    always @(posedge clk) begin
        if (out_valid) begin
            if (out_bits !== vout[n][1:0]) errors = errors + 1;
            n = n + 1;
        end
        if (lb_out_valid) begin
            if (lb_out_bits !== sent[m]) lb_errors = lb_errors + 1;
            m = m + 1;
        end
    end

    initial begin
        $readmemh("tb/vectors/demap_in.hex", vin);
        $readmemh("tb/vectors/demap_out.hex", vout);
        $dumpfile("sim/tb_qpsk_demapper.vcd");
        $dumpvars(0, tb_qpsk_demapper);
        for (k = 0; k < NL; k = k + 1) sent[k] = $random(k);
        repeat (3) @(posedge clk);
        rst_n <= 1;
        for (k = 0; k < NL; k = k + 1) begin
            @(posedge clk);
            in_valid <= (k < NV);
            if (k < NV) {in_i, in_q} <= vin[k];
            lb_valid <= 1; lb_bits <= sent[k];
        end
        @(posedge clk) begin in_valid <= 0; lb_valid <= 0; end
        repeat (4) @(posedge clk);
        if (n == NV && errors == 0) $display("PASS  qpsk_demapper   : %0d/%0d outputs match Python", n, NV);
        else                        $display("FAIL  qpsk_demapper   : %0d mismatches, %0d/%0d outputs", errors, n, NV);
        if (m == NL && lb_errors == 0) $display("PASS  mapper->demapper: %0d random bit pairs, 0 errors", NL);
        else                           $display("FAIL  mapper->demapper: %0d errors, %0d/%0d outputs", lb_errors, m, NL);
        $finish;
    end
endmodule
