// QPSK demapper, hard decision: a negative I or Q means bit 1 (sign bit).
// out_bits = {b0, b1}, matching qpsk_mapper.
module qpsk_demapper (
    input                    clk,
    input                    rst_n,
    input                    in_valid,
    input      signed [15:0] in_i,
    input      signed [15:0] in_q,
    output reg               out_valid,
    output reg        [1:0]  out_bits
);
    always @(posedge clk) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            out_bits  <= 2'b00;
        end else begin
            out_valid <= in_valid;
            if (in_valid)
                out_bits <= {in_i[15], in_q[15]};
        end
    end
endmodule
