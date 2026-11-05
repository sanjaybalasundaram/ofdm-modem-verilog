// OFDM modem top level: transmitter -> AWGN channel -> receiver.
module ofdm_top (
    input                clk,
    input                rst_n,
    input         [15:0] noise_level,   // 0 = no noise
    input                in_valid,
    input         [1:0]  in_bits,
    output               in_ready,
    output               out_valid,
    output        [1:0]  out_bits,
    // transmitted samples, brought out for checking
    output               tx_valid,
    output signed [15:0] tx_re,
    output signed [15:0] tx_im
);
    wire               ch_valid;
    wire signed [15:0] ch_re, ch_im;

    ofdm_tx u_tx (
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_bits(in_bits), .in_ready(in_ready),
        .out_valid(tx_valid), .out_re(tx_re), .out_im(tx_im)
    );
    awgn_gen u_ch (
        .clk(clk), .rst_n(rst_n), .noise_level(noise_level),
        .in_valid(tx_valid), .in_re(tx_re), .in_im(tx_im),
        .out_valid(ch_valid), .out_re(ch_re), .out_im(ch_im)
    );
    ofdm_rx u_rx (
        .clk(clk), .rst_n(rst_n), .in_valid(ch_valid), .in_re(ch_re), .in_im(ch_im),
        .out_valid(out_valid), .out_bits(out_bits)
    );
endmodule
