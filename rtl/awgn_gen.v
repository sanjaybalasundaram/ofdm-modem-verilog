// AWGN channel: y = x + noise.
// Noise = sum of 4 uniform random numbers (central limit theorem -> nearly
// Gaussian), from 8 xorshift32 generators (4 for I, 4 for Q).
// noise = sum * noise_level / 4096.  Sum std-dev = 2364.8, so
// noise_level = sigma * 4096 / 2364.8 gives a noise std-dev of sigma LSBs.
// noise_level = 0 -> the channel passes the signal through unchanged.
module awgn_gen (
    input                    clk,
    input                    rst_n,
    input             [15:0] noise_level,
    input                    in_valid,
    input      signed [15:0] in_re,
    input      signed [15:0] in_im,
    output reg               out_valid,
    output reg signed [15:0] out_re,
    output reg signed [15:0] out_im
);
    reg [31:0] s [0:7];

    function [31:0] xorshift(input [31:0] x);
        reg [31:0] t;
        begin
            t = x ^ (x << 13);
            t = t ^ (t >> 17);
            xorshift = t ^ (t << 5);
        end
    endfunction

    // Top 12 bits of each generator as a signed uniform number in -2048..2047
    wire signed [11:0] u0 = s[0][31:20], u1 = s[1][31:20], u2 = s[2][31:20], u3 = s[3][31:20];
    wire signed [11:0] u4 = s[4][31:20], u5 = s[5][31:20], u6 = s[6][31:20], u7 = s[7][31:20];
    wire signed [13:0] sum_i = u0 + u1 + u2 + u3;
    wire signed [13:0] sum_q = u4 + u5 + u6 + u7;

    wire signed [30:0] prod_i = sum_i * $signed({1'b0, noise_level});
    wire signed [30:0] prod_q = sum_q * $signed({1'b0, noise_level});
    wire signed [18:0] noise_i = prod_i[30:12];
    wire signed [18:0] noise_q = prod_q[30:12];
    wire signed [19:0] y_re = in_re + noise_i;
    wire signed [19:0] y_im = in_im + noise_q;

    function signed [15:0] sat16(input signed [19:0] v);
        if (v > 20'sd32767)       sat16 = 16'sd32767;
        else if (v < -20'sd32768) sat16 = -16'sd32768;
        else                      sat16 = v[15:0];
    endfunction

    integer k;
    always @(posedge clk) begin
        if (!rst_n) begin
            s[0] <= 32'h1234_5678; s[1] <= 32'h9ABC_DEF1; s[2] <= 32'h0F1E_2D3C; s[3] <= 32'h4B5A_6978;
            s[4] <= 32'hDEAD_BEEF; s[5] <= 32'hC0FF_EE11; s[6] <= 32'h1357_9BDF; s[7] <= 32'h2468_ACE0;
            out_valid <= 1'b0;
            out_re    <= 16'sd0;
            out_im    <= 16'sd0;
        end else begin
            for (k = 0; k < 8; k = k + 1)
                s[k] <= xorshift(s[k]);
            out_valid <= in_valid;
            if (in_valid) begin
                out_re <= sat16(y_re);
                out_im <= sat16(y_im);
            end
        end
    end
endmodule
