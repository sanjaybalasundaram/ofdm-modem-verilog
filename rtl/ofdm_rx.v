// OFDM receiver: cyclic prefix removal -> 64-point FFT -> QPSK demapper.
module ofdm_rx (
    input                clk,
    input                rst_n,
    input                in_valid,
    input  signed [15:0] in_re,
    input  signed [15:0] in_im,
    output               out_valid,
    output        [1:0]  out_bits
);
    wire               cp_valid, fft_valid;
    wire signed [15:0] cp_re, cp_im, fft_re, fft_im;

    cp_remove u_cp (
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_re(in_re), .in_im(in_im),
        .out_valid(cp_valid), .out_re(cp_re), .out_im(cp_im)
    );
    fft64 u_fft (
        .clk(clk), .rst_n(rst_n), .inverse(1'b0),
        .in_valid(cp_valid), .in_re(cp_re), .in_im(cp_im), .in_ready(),
        .out_valid(fft_valid), .out_re(fft_re), .out_im(fft_im)
    );
    qpsk_demapper u_demap (
        .clk(clk), .rst_n(rst_n), .in_valid(fft_valid), .in_i(fft_re), .in_q(fft_im),
        .out_valid(out_valid), .out_bits(out_bits)
    );
endmodule
