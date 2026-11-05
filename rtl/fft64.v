// 64-point FFT / IFFT, in-place radix-2 DIT, one butterfly per clock.
//
//   LOAD : accept 64 samples (in_valid), stored at bit-reversed addresses
//   CALC : 6 stages x 32 butterflies = 192 clocks
//   OUT  : stream 64 results in natural order (out_valid)
//
// inverse = 0 -> FFT,  inverse = 1 -> IFFT (conjugate twiddles).
// Output is scaled by 1/64 (each butterfly divides by 2).
module fft64 (
    input                    clk,
    input                    rst_n,
    input                    inverse,
    input                    in_valid,
    input      signed [15:0] in_re,
    input      signed [15:0] in_im,
    output                   in_ready,
    output reg               out_valid,
    output reg signed [15:0] out_re,
    output reg signed [15:0] out_im
);
    localparam LOAD = 2'd0, CALC = 2'd1, OUT = 2'd2;

    reg signed [15:0] mem_re [0:63];
    reg signed [15:0] mem_im [0:63];
    reg [1:0] state;
    reg [5:0] cnt;      // sample counter (LOAD / OUT)
    reg [2:0] stage;    // 0..5
    reg [4:0] bf;       // butterfly 0..31 inside a stage

    assign in_ready = (state == LOAD);

    // Butterfly addresses for this stage
    wire [5:0] half = 6'd1 << stage;                       // 1, 2, 4 ... 32
    wire [5:0] bf6  = {1'b0, bf};
    wire [5:0] j    = bf6 & (half - 6'd1);                 // position inside a group
    wire [5:0] ia   = ((bf6 >> stage) << (stage + 3'd1)) | j;
    wire [5:0] ib   = ia | half;
    wire [5:0] tk   = j << (3'd5 - stage);                 // twiddle index

    wire signed [15:0] wr, wi, xr, xi, yr, yi;
    twiddle_rom u_rom (.k(tk[4:0]), .inverse(inverse), .wr(wr), .wi(wi));
    butterfly_r2 u_bf (
        .ar(mem_re[ia]), .ai(mem_im[ia]), .br(mem_re[ib]), .bi(mem_im[ib]),
        .wr(wr), .wi(wi), .xr(xr), .xi(xi), .yr(yr), .yi(yi)
    );

    function [5:0] bitrev(input [5:0] v);
        bitrev = {v[0], v[1], v[2], v[3], v[4], v[5]};
    endfunction

    always @(posedge clk) begin
        if (!rst_n) begin
            state     <= LOAD;
            cnt       <= 6'd0;
            stage     <= 3'd0;
            bf        <= 5'd0;
            out_valid <= 1'b0;
            out_re    <= 16'sd0;
            out_im    <= 16'sd0;
        end else begin
            case (state)
                LOAD: begin
                    out_valid <= 1'b0;
                    if (in_valid) begin
                        mem_re[bitrev(cnt)] <= in_re;
                        mem_im[bitrev(cnt)] <= in_im;
                        cnt <= cnt + 6'd1;
                        if (cnt == 6'd63) begin
                            state <= CALC;
                            stage <= 3'd0;
                            bf    <= 5'd0;
                        end
                    end
                end
                CALC: begin
                    mem_re[ia] <= xr;  mem_im[ia] <= xi;
                    mem_re[ib] <= yr;  mem_im[ib] <= yi;
                    bf <= bf + 5'd1;
                    if (bf == 5'd31) begin
                        stage <= stage + 3'd1;
                        if (stage == 3'd5) begin
                            state <= OUT;
                            cnt   <= 6'd0;
                        end
                    end
                end
                OUT: begin
                    out_valid <= 1'b1;
                    out_re    <= mem_re[cnt];
                    out_im    <= mem_im[cnt];
                    cnt <= cnt + 6'd1;
                    if (cnt == 6'd63) state <= LOAD;
                end
                default: state <= LOAD;
            endcase
        end
    end
endmodule
