// OFDM transmitter: QPSK mapper -> 64-point IFFT -> cyclic prefix insertion.
// Send 64 bit-pairs (one OFDM symbol) while in_ready is high; out = 80 samples.
module ofdm_tx (
    input                clk,
    input                rst_n,
    input                in_valid,
    input         [1:0]  in_bits,
    output               in_ready,
    output               out_valid,
    output signed [15:0] out_re,
    output signed [15:0] out_im
);
    wire               map_valid, ifft_valid;
    wire signed [15:0] map_i, map_q, ifft_re, ifft_im;

    qpsk_mapper u_map (
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_bits(in_bits),
        .out_valid(map_valid), .out_i(map_i), .out_q(map_q)
    );
    fft64 u_ifft (
        .clk(clk), .rst_n(rst_n), .inverse(1'b1),
        .in_valid(map_valid), .in_re(map_i), .in_im(map_q), .in_ready(in_ready),
        .out_valid(ifft_valid), .out_re(ifft_re), .out_im(ifft_im)
    );
    cp_insert u_cp (
        .clk(clk), .rst_n(rst_n),
        .in_valid(ifft_valid), .in_re(ifft_re), .in_im(ifft_im), .in_ready(),
        .out_valid(out_valid), .out_re(out_re), .out_im(out_im)
    );
endmodule
